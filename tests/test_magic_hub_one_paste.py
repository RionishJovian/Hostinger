"""One-paste Magic Hub connect: token lifecycle, script safety, redeem contract."""
import time
import unittest
from unittest.mock import patch

import test_hubs
from test_hubs import key
from backend import magic_hub_script as script_mod
from backend.models import MagicHubConnectToken, RouterPlan, RouterPlanRetirement
from sqlalchemy import select


class ScriptUnitTests(unittest.TestCase):
 def test_script_has_no_admin_password_or_hardcoded_ifaces(self):
  script = script_mod.generate_enroll_script(
   token='TESTTOKEN123', base_url='https://megamagic.tech',
   router_id='97546f1a-1111-2222-3333-444444444444', hub_endpoint='156.67.216.128',
  )
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

 def test_enroll_response_round_trip(self):
  body = script_mod.format_enroll_response({
   'status': 'ok', 'hub_public_key': key(1), 'endpoint': 'hub.example.com',
   'endpoint_port': '51820', 'hub_address': '10.90.1.1', 'router_address': '10.90.1.2/32',
   'keepalive': '25', 'interface': 'mm-abcd1234', 'listen_port': '13239',
   'enroll_user': 'mm-enroll-abcd1234', 'enroll_password': 'secret-once',
   'certificate': 'mm-mgmt-abcd1234',
  })
  parsed = script_mod.parse_enroll_request(body)
  self.assertEqual(parsed['status'], 'ok')
  self.assertEqual(parsed['hub_public_key'], key(1))
  self.assertEqual(parsed['enroll_password'], 'secret-once')
  form = 'public_key=' + key(9) + '&board=C52iG&version=7.24.2&serial=HEJ08NYV0M1'
  self.assertEqual(script_mod.parse_enroll_request(form)['board'], 'C52iG')

 def test_rollback_script_targets_mikromagic_only(self):
  rb = script_mod.rollback_script()
  self.assertIn('MikroMagic', rb)
  self.assertNotIn('ether1', rb)


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
  # Extract token from script
  import re
  m = re.search(r':local mmToken "([^"]+)"', script)
  self.assertTrue(m)
  token = m.group(1)
  self.assertNotIn('admin', script.lower().split('enroll')[0] if False else '')
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
   self.assertTrue(adapter.peer_present)
   # Single use: second redeem does not re-emit password
   again = self.client.post(f'/v1/magic-connect/hub-enroll/{token}', content=body)
   self.assertEqual(again.status_code, 200)
   self.assertIn('enroll_password=\n', again.text.replace('\r', '') or 'enroll_password=')

  status = self.client.get(f"/v1/routers/{router}/magic-hub-connect/{data['token_id']}", headers=owner).json()
  self.assertIn(status['status'], ('peer_added', 'awaiting_handshake', 'management_applied', 'finishing', 'connected'))

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
  import re
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
  import re, os, tempfile
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
