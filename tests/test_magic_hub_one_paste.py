"""One-paste Magic Hub connect: token lifecycle, script safety, redeem contract."""
import re
import time
import unittest
from unittest.mock import patch

import test_hubs
from test_hubs import key
from backend import magic_hub_script as script_mod
from backend.models import MagicHubConnectToken, RouterDevice, RouterPlan, RouterPlanRetirement
from sqlalchemy import select


def _sample_script():
  return script_mod.generate_enroll_script(
   token='TESTTOKEN123', base_url='https://megamagic.tech',
   router_id='97546f1a-1111-2222-3333-444444444444', hub_endpoint='156.67.216.128',
  )


class ScriptUnitTests(unittest.TestCase):
 def test_script_has_no_admin_password_or_hardcoded_ifaces(self):
  script = _sample_script()
  self.assertIn('TESTTOKEN123', script)
  self.assertIn('check-certificate=yes-without-crl', script)
  self.assertIn('/tool fetch', script)
  self.assertIn('Upgrade RouterOS to v7', script)
  self.assertIn('Connect the router to the internet first', script)
  self.assertNotIn('ether1', script)
  self.assertNotIn('wifi1', script)
  self.assertNotIn('/user set admin', script)
  self.assertNotIn('password=', script.split('enroll')[0])  # no password before enroll reply handling
  # Enrollment password is applied from server reply variable, not a literal admin password
  self.assertIn('password=$mmEnrollPass', script)
  script_mod.assert_script_safe(script, token='TESTTOKEN123')

 def test_script_passes_values_into_helpers_not_outer_locals(self):
  """RouterOS :local f do={} cannot read the caller's locals."""
  script = _sample_script()
  self.assertNotIn('mmAdded', script)
  # Fail helper uses globals (or named params), not bare outer locals for cleanup.
  self.assertIn(':global mmGStatusUrl', script)
  self.assertIn(':global mmGComment', script)
  self.assertIn(':global mmGId8', script)
  self.assertIn(':global mmGWwwChanged', script)
  self.assertIn(':global mmGWwwDisabled', script)
  self.assertIn(':global mmGWwwCert', script)
  self.assertIn(':global mmGWwwAddress', script)
  # mmGet must take reply/key as named parameters — not read $mmReply from outer scope.
  self.assertIn('$"reply"', script)
  self.assertIn('$"key"', script)
  self.assertIn('[$mmGet reply=$mmReply key="hub_public_key"]', script)
  # Fail body must not reference undefined outer locals like $mmStatusUrl without global.
  fail_block = script.split(':local mmFail do={')[1].split(':put "MM: Checking RouterOS')[0]
  self.assertNotRegex(fail_block, r'\$mmStatusUrl\b')
  self.assertNotRegex(fail_block, r'\$mmComment\b')
  self.assertNotRegex(fail_block, r'\$mmId8\b')
  self.assertIn('$mmGStatusUrl', fail_block)
  self.assertIn('$mmGComment', fail_block)
  self.assertIn('$mmGId8', fail_block)
  self.assertIn('$mmGWwwChanged', fail_block)

 def test_mmfail_does_not_unconditionally_reset_www_ssl(self):
  """Failure cleanup must not wipe owner www-ssl unless this run changed it."""
  script = _sample_script()
  fail_block = script.split(':local mmFail do={')[1].split(':put "MM: Checking RouterOS')[0]
  self.assertNotIn(
   '/ip service set www-ssl disabled=yes certificate=none address=""',
   fail_block,
  )
  self.assertIn(':if ($mmGWwwChanged) do={', fail_block)
  self.assertIn(
   '/ip service set www-ssl disabled=$mmGWwwDisabled certificate=$mmGWwwCert address=$mmGWwwAddress',
   fail_block,
  )
  # Flag starts false; previous values saved only right before MikroMagic's www-ssl write.
  self.assertIn(':set mmGWwwChanged false', script)
  save_disabled = script.index(':set mmGWwwDisabled [/ip service get www-ssl disabled]')
  save_cert = script.index(':set mmGWwwCert [/ip service get www-ssl certificate]')
  save_addr = script.index(':set mmGWwwAddress [/ip service get www-ssl address]')
  flag_true = script.index(':set mmGWwwChanged true')
  www_write = script.index('/ip service set www-ssl certificate=$mmCert')
  self.assertLess(save_disabled, flag_true)
  self.assertLess(save_cert, flag_true)
  self.assertLess(save_addr, flag_true)
  self.assertLess(flag_true, www_write)

 def test_preflight_failure_cannot_reach_www_ssl_change(self):
  """www-ssl already-enabled preflight fails before any www-ssl write or flag set."""
  script = _sample_script()
  precheck = script.index('Pre-checks before any write')
  www_enabled_fail = script.index('www-ssl is already enabled')
  flag_true = script.index(':set mmGWwwChanged true')
  www_write = script.index('/ip service set www-ssl certificate=$mmCert')
  self.assertLess(precheck, www_enabled_fail)
  self.assertLess(www_enabled_fail, flag_true)
  self.assertLess(www_enabled_fail, www_write)
  # Between preflight www-ssl check and flag=true there is no www-ssl service set.
  between = script[www_enabled_fail:flag_true]
  self.assertNotIn('/ip service set www-ssl', between)

 def test_script_find_uses_typeof_nil_not_numeric_compare(self):
  script = _sample_script()
  self.assertNotRegex(script, r'\[:find[^\]]*\]\s*>=\s*0')
  self.assertNotRegex(script, r'\[:find[^\]]*\]\s*<\s*0')
  self.assertIn('[:typeof $mmErrPos] != "nil"', script)
  self.assertIn('[:typeof $mmOkPos] = "nil"', script)
  self.assertIn('[:typeof $mmDot] = "nil"', script)

 def test_script_version_uses_tonum(self):
  script = _sample_script()
  self.assertIn('[:tonum $mmMajor] < 7', script)
  self.assertNotRegex(script, r'\$mmMajor\s*<\s*"7"')

 def test_script_fetch_uses_output_user_as_value(self):
  script = _sample_script()
  self.assertIn('output=user as-value', script)
  self.assertIn('($mmFetch->"data")', script)
  self.assertNotIn('dst-path=', script)
  self.assertNotIn('/file get', script)
  self.assertNotIn('/file remove', script)

 def test_script_error_syntax_and_urlencode_failure(self):
  script = _sample_script()
  self.assertIn(':error ("MM-FAIL: " . $mmMsg)', script)
  self.assertNotIn(':error message=', script)
  self.assertIn(':convert to=url', script)
  self.assertIn('?phase=failed&message=" . $mmEnc)', script)

 def test_script_certificate_wait_before_www_ssl(self):
  script = _sample_script()
  self.assertIn('/certificate sign $mmCert', script)
  self.assertIn('Certificate was not signed in time', script)
  sign_idx = script.index('/certificate sign $mmCert')
  wait_idx = script.index('while (!$mmSigned')
  www_idx = script.index('/ip service set www-ssl certificate=$mmCert')
  self.assertLess(sign_idx, wait_idx)
  self.assertLess(wait_idx, www_idx)

 def test_script_writes_wrapped_in_do_on_error(self):
  script = _sample_script()
  for fragment in (
   '/interface wireguard add name=$mmIface',
   '/interface wireguard peers add interface=$mmIface',
   '/ip address add address=$mmRAddr',
   '/ip route add dst-address=($mmHubAddr . "/32")',
   '/certificate add name=$mmCert',
   '/certificate sign $mmCert',
   '/ip service set www-ssl certificate=$mmCert',
   '/user add name=$mmEnrollUser',
  ):
   self.assertIn(fragment, script)
   # Each write sits inside a :do { ... } on-error={ [$mmFail ...] } block
   pos = script.index(fragment)
   window = script[max(0, pos - 80):pos]
   self.assertIn(':do {', window, msg=f'{fragment} missing :do wrapper nearby')

 def test_script_prechecks_www_ssl_mm_users_and_pool(self):
  script = _sample_script()
  self.assertIn('www-ssl is already enabled', script)
  self.assertIn('name~"^mm-"', script)
  self.assertIn('A user starting with mm- already exists', script)
  self.assertIn('A group starting with mm- already exists', script)
  self.assertIn('hub_pool', script)
  self.assertIn('overlaps hub pool', script)
  self.assertIn('Pre-checks before any write', script)

 def test_enroll_response_round_trip(self):
  body = script_mod.format_enroll_response({
   'status': 'ok', 'hub_public_key': key(1), 'endpoint': 'hub.example.com',
   'endpoint_port': '51820', 'hub_address': '10.90.1.1', 'router_address': '10.90.1.2/32',
   'hub_pool': '10.90.1.0/24', 'keepalive': '25', 'interface': 'mm-abcd1234', 'listen_port': '13239',
   'enroll_user': 'mm-enroll-abcd1234', 'enroll_password': 'secret-once',
   'certificate': 'mm-mgmt-abcd1234',
  })
  parsed = script_mod.parse_enroll_request(body)
  self.assertEqual(parsed['status'], 'ok')
  self.assertEqual(parsed['hub_public_key'], key(1))
  self.assertEqual(parsed['enroll_password'], 'secret-once')
  self.assertEqual(parsed['hub_pool'], '10.90.1.0/24')
  form = 'public_key=' + key(9) + '&board=C52iG&version=7.24.2&serial=HEJ08NYV0M1'
  self.assertEqual(script_mod.parse_enroll_request(form)['board'], 'C52iG')

 def test_parse_preserves_plus_and_slash_in_public_key(self):
  """unquote (not unquote_plus) must keep base64 +; %2B/%2F decode correctly."""
  # 32 zero-ish bytes engineered so base64 contains both '+' and '/'.
  special = '+/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
  self.assertEqual(len(special), 44)
  self.assertIn('+', special)
  self.assertIn('/', special)
  self.assertTrue(script_mod.WG_PUBLIC_KEY_RE.fullmatch(special))
  # Literal + in the body must stay '+' (unquote_plus would turn it into space).
  literal = f'public_key={special}&board=RB'
  parsed = script_mod.parse_enroll_request(literal)
  self.assertEqual(parsed['public_key'], special)
  self.assertNotIn(' ', parsed['public_key'])
  # URL-encoded form from the RouterOS mmUrlEnc helper.
  encoded = (
   'public_key=' + special.replace('+', '%2B').replace('/', '%2F').replace('=', '%3D')
   + '&board=RB'
  )
  self.assertEqual(script_mod.parse_enroll_request(encoded)['public_key'], special)
  # Reject non-44 / non-base64 public keys.
  self.assertEqual(script_mod.parse_enroll_request('public_key=not-a-key&board=RB')['public_key'], '')
  self.assertEqual(
   script_mod.parse_enroll_request('public_key=AAAA+with+spaces+not+44chars=&board=RB')['public_key'], ''
  )

 def test_script_url_encodes_enroll_http_data_values(self):
  script = _sample_script()
  self.assertIn(':local mmUrlEnc do={', script)
  self.assertIn('%2B', script)
  self.assertIn('%2F', script)
  self.assertIn('[$mmUrlEnc $mmPub]', script)
  self.assertIn('"public_key=" . $mmEncPub', script)
  # Raw unencoded $mmPub must not be concatenated into http-data.
  self.assertNotIn('"public_key=" . $mmPub', script)

 def test_script_if_expressions_have_no_bareword_yes_no(self):
  """Unquoted yes/no inside :if (...) is not a RouterOS boolean and breaks paste."""
  script = _sample_script()
  self.assertNotIn('$mmWwwDisabled = no', script)
  for match in re.finditer(r':if\s*\((.*?)\)\s*do=', script, re.S):
   cond = match.group(1)
   self.assertIsNone(
    re.search(r'(?<!["\w/=])\b(yes|no)\b(?!["\w])', cond),
    msg=f'bareword yes/no in :if condition: {cond[:120]!r}',
   )

 def test_rollback_script_targets_mikromagic_only(self):
  rb = script_mod.rollback_script()
  self.assertIn('MikroMagic', rb)
  self.assertNotIn('ether1', rb)
  # Reset www-ssl only when the current certificate is MikroMagic's mm-mgmt-* cert.
  self.assertIn('[:find $mmCertName "mm-mgmt-"]', rb)
  self.assertIn('/ip service set www-ssl disabled=yes certificate=none address=""', rb)
  # The reset must sit inside the mm-mgmt- prefix gate, not as a bare unconditional line.
  reset_pos = rb.index('/ip service set www-ssl disabled=yes certificate=none address=""')
  gate_pos = rb.index('[:find $mmCertName "mm-mgmt-"]')
  self.assertLess(gate_pos, reset_pos)
  before_reset = rb[:reset_pos]
  self.assertIn('$mmHit = 0', before_reset)


class OnePasteApiTests(unittest.TestCase):
 H = test_hubs.HubTests
 setUp = H.setUp
 tearDown = H.tearDown
 login = H.login
 setup_hub = H.setup_hub
 router = H.router

 def enable(self):
  self.app.state.magic_connect_router_setup_enabled = True

 def test_capability_gate_and_token_lifecycle(self):
  _, owner, hub, site, _ = self.setup_hub()
  router = self.router(owner, site)
  self.assertEqual(self.client.post(f'/v1/routers/{router}/magic-hub-connect', headers=owner, json={}).status_code, 503)
  self.enable()
  started = self.client.post(f'/v1/routers/{router}/magic-hub-connect', headers={**owner, 'Origin': 'https://megamagic.tech'}, json={})
  self.assertEqual(started.status_code, 201, started.text)
  data = started.json()
  self.assertIn('script', data)
  self.assertIn('rollback_script', data)
  self.assertEqual(data['progress']['status'], 'waiting')
  script = data['script']
  self.assertNotIn(hub, script)  # hub id not required in script
  self.assertIn('https://megamagic.tech/v1/magic-connect/hub-enroll/', script)
  m = re.search(r':local mmToken "([^"]+)"', script)
  self.assertTrue(m)
  token = m.group(1)
  script_mod.assert_script_safe(script, token=token)

  # Wrong tenant cannot poll
  other = self.login('other')
  self.assertEqual(
   self.client.get(f"/v1/routers/{router}/magic-hub-connect/{data['token_id']}", headers=other).status_code, 404
  )

  # Redeem
  from backend.hub_orchestrator import HubPeerOrchestrator, HostOperationPolicy
  from test_hub_orchestrator import FakeHubAdapter
  adapter = FakeHubAdapter()
  self.app.state.magic_hub_orchestrator = HubPeerOrchestrator(
   adapter, HostOperationPolicy('isolated-magic-connect-test', True, True, 'wg-mm')
  )
  body = (
   f'public_key={key(9)}&board=C52iG-5HaxD2HaxD&version=7.24.2 (stable)'
   f'&architecture=arm64&serial=HEJ08NYV0M1&interface=mm-{router[:8]}'
   f'&listen_port=13239&input_rules=3&interface_count=8'
  )
  import os, tempfile
  from pathlib import Path
  stores = tempfile.TemporaryDirectory(); self.addCleanup(stores.cleanup)
  env = {}
  for role, var in (('m', 'MONITORING'), ('s', 'SAFE_CHANGE'), ('e', 'ENROLL')):
   path = Path(stores.name) / role; path.mkdir(mode=0o700)
   env[f'MIKROMAGIC_ROUTEROS_{var}_SECRETS_DIR'] = str(path)
  with patch.dict(os.environ, env):
   redeem = self.client.post(f'/v1/magic-connect/hub-enroll/{token}', content=body)
   self.assertEqual(redeem.status_code, 200, redeem.text)
   text = redeem.text
   self.assertIn('status=ok', text)
   self.assertIn('hub_public_key=', text)
   self.assertIn('enroll_password=', text)
   self.assertIn('hub_pool=', text)
   self.assertTrue(adapter.peer_present)
   # Single use: second redeem does not re-emit password
   again = self.client.post(f'/v1/magic-connect/hub-enroll/{token}', content=body)
   self.assertEqual(again.status_code, 200)
   self.assertIn('enroll_password=\n', again.text.replace('\r', '') or 'enroll_password=')

  status = self.client.get(f"/v1/routers/{router}/magic-hub-connect/{data['token_id']}", headers=owner).json()
  self.assertIn(status['status'], ('peer_added', 'awaiting_handshake', 'management_applied', 'finishing', 'connected'))
  listed = self.client.get('/v1/routers', headers=owner).json()
  row = next(r for r in listed if r['id'] == router)
  self.assertEqual(row['model'], 'C52iG-5HaxD2HaxD')
  self.assertIn('7.24.2', row['reported_routeros'])
  self.assertEqual(row['architecture'], 'arm64')
  self.assertEqual(row['reported_serial'], 'HEJ08NYV0M1')
  self.assertEqual(row['metadata_source'], 'script_reported')

 def test_name_only_registration(self):
  _, owner, _, site, _ = self.setup_hub()
  created = self.client.post('/v1/routers', headers=owner, json={'site_id': site, 'name': 'Cafe gateway'})
  self.assertEqual(created.status_code, 201, created.text)
  listed = self.client.get('/v1/routers', headers=owner).json()
  row = next(r for r in listed if r['name'] == 'Cafe gateway')
  self.assertIsNone(row['model'])
  self.assertIsNone(row['reported_routeros'])
  self.assertIsNone(row.get('architecture'))
  self.assertEqual(row['metadata_source'], 'name_only')

 def test_expired_and_invalid_token(self):
  _, owner, hub, site, _ = self.setup_hub(); self.enable()
  router = self.router(owner, site)
  started = self.client.post(
   f'/v1/routers/{router}/magic-hub-connect', headers={**owner, 'Origin': 'https://example.test'}, json={}
  ).json()
  bad = self.client.post('/v1/magic-connect/hub-enroll/not-a-real-token', content='public_key=' + key(9))
  self.assertEqual(bad.status_code, 404)
  with self.app.state.factory() as s:
   row = s.get(MagicHubConnectToken, started['token_id'])
   row.created = int(time.time()) - 4000
   row.expires = int(time.time()) - 10
   s.commit()
  token = re.search(r':local mmToken "([^"]+)"', started['script']).group(1)
  expired = self.client.post(f'/v1/magic-connect/hub-enroll/{token}', content='public_key=' + key(9))
  self.assertEqual(expired.status_code, 410)

 def test_replace_existing_retires_plan(self):
  from backend.hub_orchestrator import HubPeerOrchestrator, HostOperationPolicy
  from test_hub_orchestrator import FakeHubAdapter
  _, owner, hub, site, _ = self.setup_hub(); self.enable()
  router = self.router(owner, site)
  adapter = FakeHubAdapter()
  self.app.state.magic_hub_orchestrator = HubPeerOrchestrator(
   adapter, HostOperationPolicy('isolated-magic-connect-test', True, True, 'wg-mm')
  )
  first = self.client.post(
   f'/v1/routers/{router}/magic-hub-connect', headers={**owner, 'Origin': 'https://megamagic.tech'}, json={}
  ).json()
  import os, tempfile
  from pathlib import Path
  token = re.search(r':local mmToken "([^"]+)"', first['script']).group(1)
  stores = tempfile.TemporaryDirectory(); self.addCleanup(stores.cleanup)
  env = {}
  for role, var in (('m', 'MONITORING'), ('s', 'SAFE_CHANGE'), ('e', 'ENROLL')):
   path = Path(stores.name) / role; path.mkdir(mode=0o700)
   env[f'MIKROMAGIC_ROUTEROS_{var}_SECRETS_DIR'] = str(path)
  with patch.dict(os.environ, env):
   self.client.post(
    f'/v1/magic-connect/hub-enroll/{token}',
    content=f'public_key={key(9)}&board=RB&version=7.12&architecture=arm&serial=ABC123456789&interface=mm-{router[:8]}&listen_port=13239&input_rules=0',
   )
  conflict = self.client.post(
   f'/v1/routers/{router}/magic-hub-connect', headers={**owner, 'Origin': 'https://megamagic.tech'}, json={}
  )
  self.assertEqual(conflict.status_code, 409)
  replaced = self.client.post(
   f'/v1/routers/{router}/magic-hub-connect',
   headers={**owner, 'Origin': 'https://megamagic.tech'},
   json={'replace_existing': True, 'reason': 'Router was factory reset'},
  )
  self.assertEqual(replaced.status_code, 201, replaced.text)
  with self.app.state.factory() as s:
   self.assertIsNone(s.scalar(select(RouterPlan).where(RouterPlan.router_id == router)))
   self.assertTrue(s.scalar(select(RouterPlanRetirement).where(RouterPlanRetirement.router_id == router)))


if __name__ == '__main__':
 unittest.main()
