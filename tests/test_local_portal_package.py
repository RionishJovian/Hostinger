import hashlib
import io
import json
import re
import shutil
import subprocess
import unittest
import zipfile

from backend.local_portal_package import build_local_hotspot_package, validate_local_hotspot_package
from backend.schemas import PortalConfig


class LocalPortalPackageTests(unittest.TestCase):
    def setUp(self):
        self.settings = PortalConfig(
            business_name='Café <North>', welcome='Welcome <guest>',
            terms='Use fairly & safely', contact='help@example.test',
        )

    def test_builds_deterministic_self_contained_chap_package(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=7)
        self.assertEqual(package, build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=7))
        report = validate_local_hotspot_package(package)
        self.assertTrue(report['valid'])
        self.assertFalse(report['installation_performed'])
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read('portal-manifest.json'))
            self.assertEqual(set(archive.namelist()), set(manifest['files']) | {'portal-manifest.json', 'README.txt'})
            self.assertEqual(manifest['scope'], {'tenant_id':'tenant_01','site_id':'site_01','published_revision':7})
            login = archive.read('login.html').decode()
            flogin = archive.read('flogin.html').decode()
            self.assertIn('Café &lt;North&gt;', login)
            self.assertIn('Welcome &lt;guest&gt;', login)
            self.assertIn('lang="my"', login)
            self.assertIn('data-lang="my"', login)
            self.assertIn('data-lang="en"', login)
            self.assertIn('Wi-Fi ကုဒ်', login)
            self.assertIn('ချိတ်ဆက်ရန်', login)
            self.assertIn('class="sheet"', login)
            self.assertIn('class="seal"', login)
            self.assertIn('lantern', manifest.get('theme', ''))
            self.assertIn('$(chap-id)', login)
            self.assertIn('$(chap-challenge)', login)
            self.assertIn('$(username)', login)
            self.assertNotIn('http-pap', login)
            self.assertNotIn('https://', login)
            self.assertNotRegex(login, r'<input[^>]*type="password"', 'single voucher field only')
            self.assertIn('$(error)', flogin)
            self.assertIn('ကုဒ် မှားနေပါသည်', flogin)
            self.assertIn('Too many devices', flogin)
            self.assertEqual(manifest.get('guest_ui'), 'lantern_leaf_burmese_first_single_voucher_field')
            self.assertEqual(manifest.get('guest_language'), 'both')
            self.assertEqual(manifest.get('theme'), 'lantern_leaf')
            self.assertIn('router_compatibility_verified', manifest)
            self.assertFalse(manifest['router_compatibility_verified'])
            self.assertLess(len(package), 128_000)
            self.assertLess(len(archive.read('login.html')), 32_000)

    def test_myanmar_only_package_has_no_language_toggle(self):
        settings = PortalConfig(business_name='Shop', language='my')
        package = build_local_hotspot_package(settings, tenant_id='tenant_01', site_id='site_01', revision=2)
        report = validate_local_hotspot_package(package)
        self.assertEqual(report['guest_language'], 'my')
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read('portal-manifest.json'))
            login = archive.read('login.html').decode()
            flogin = archive.read('flogin.html').decode()
            self.assertEqual(manifest['guest_language'], 'my')
            self.assertEqual(manifest['guest_ui'], 'lantern_leaf_myanmar_only_single_voucher_field')
            self.assertIn('lang="my"', login)
            self.assertNotIn('data-lang', login)
            self.assertIn('ချိတ်ဆက်ရန်', login)
            self.assertNotIn('Connect', login)
            self.assertIn('ကုဒ် မှားနေပါသည်', flogin)
            self.assertNotIn('Wrong code', flogin)
            self.assertIn('el.textContent=msg', flogin)

    def test_english_only_package_has_no_language_toggle(self):
        settings = PortalConfig(business_name='Shop', language='en')
        package = build_local_hotspot_package(settings, tenant_id='tenant_01', site_id='site_01', revision=3)
        report = validate_local_hotspot_package(package)
        self.assertEqual(report['guest_language'], 'en')
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read('portal-manifest.json'))
            login = archive.read('login.html').decode()
            flogin = archive.read('flogin.html').decode()
            self.assertEqual(manifest['guest_language'], 'en')
            self.assertEqual(manifest['guest_ui'], 'lantern_leaf_english_only_single_voucher_field')
            self.assertIn('lang="en"', login)
            self.assertNotIn('data-lang', login)
            self.assertIn('Connect', login)
            self.assertNotIn('ချိတ်ဆက်ရန်', login)
            self.assertIn('Wrong code', flogin)
            self.assertNotIn('ကုဒ် မှားနေပါသည်', flogin)
            self.assertIn('el.textContent=msg', flogin)

    def test_midnight_studio_layout_and_page_hierarchy(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=7)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            pages = {name: archive.read(name).decode() for name in (
                'login.html', 'alogin.html', 'flogin.html', 'status.html',
                'logout.html', 'fstatus.html', 'flogout.html', 'error.html',
            )}
        login = pages['login.html']
        self.assertIn('linear-gradient(180deg,#0B1014 0%,#121A1F 100%)', login)
        self.assertIn('background:rgba(22,30,36,.78);border:1px solid rgba(200,205,212,.14);border-radius:20px', login)
        self.assertIn('color:#E6E9ED', login)
        self.assertIn('color:#A8B0B8', login)
        self.assertIn('color:#7A838C', login)
        self.assertIn('linear-gradient(180deg,#1F8F68,#147A56)', login)
        self.assertIn('.seal{width:48px;height:48px', login)
        self.assertIn('border:1px solid rgba(200,205,212,.72)', login)
        self.assertIn('font:16px/1.6', login)
        self.assertIn('padding:20px 16px', login)
        self.assertNotRegex(login, r'#D98A32|rgba\(242,179,90,|#F2C27B')
        self.assertNotIn('<h1', login)
        self.assertLess(login.index('class="seal"'), login.index('class="langs"'))
        self.assertLess(login.index('class="langs"'), login.index('class="brand"'))
        self.assertLess(login.index('class="brand"'), login.index('class="lead"'))
        self.assertLess(login.index('class="lead"'), login.index('class="sheet"'))
        self.assertIn('class="secondary" href="$(link-status)"', pages['alogin.html'])
        self.assertIn('class="secondary" href="$(link-login-only)"', pages['flogin.html'])
        for name in ('logout.html', 'fstatus.html', 'flogout.html', 'error.html'):
            self.assertIn('class="secondary" href="$(link-login-only)"', pages[name])
        for name in ('flogin.html', 'status.html', 'logout.html', 'fstatus.html', 'flogout.html', 'error.html'):
            self.assertNotIn('class="lead"', pages[name])
        status = pages['status.html']
        self.assertEqual(status.count('class="stat"'), 2)
        self.assertIn('<span class="stat-label"><span class="my">ကျန်အချိန်</span><span class="en">Time left</span></span>', status)
        self.assertIn('<span class="stat-value">$(session-time-left)</span>', status)
        self.assertIn('<span class="stat-label"><span class="my">ကျန်ဒေတာ</span><span class="en">Data left</span></span>', status)
        self.assertIn('<span class="stat-value">$(remain-bytes-total)</span>', status)
        self.assertIn('class="status-logout"', status)
        self.assertIn('.status-logout{margin-top:24px}', status)
        self.assertIn('.status-logout .primary{min-height:52px', status)
        self.assertIn('.secondary{display:flex;width:100%;min-height:44px', login)

    def test_rejects_invalid_scope(self):
        with self.assertRaises(ValueError):
            build_local_hotspot_package(self.settings, tenant_id='tenant', site_id='../other', revision=1)
        with self.assertRaises(ValueError):
            build_local_hotspot_package(self.settings, tenant_id='tenant', site_id='site', revision=0)

    def test_validator_rejects_remote_assets_and_checksum_tampering(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=1)
        with zipfile.ZipFile(io.BytesIO(package)) as source:
            files = {name: source.read(name) for name in source.namelist()}
        files['login.html'] = files['login.html'].replace(b'<head>', b'<head><script src="https://cdn.example/x.js"></script>')
        forged = io.BytesIO()
        with zipfile.ZipFile(forged, 'w', zipfile.ZIP_DEFLATED) as target:
            for name, value in files.items(): target.writestr(name, value)
        with self.assertRaises(ValueError):
            validate_local_hotspot_package(forged.getvalue())

    def test_validator_rejects_path_traversal(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=1)
        forged = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(package)) as source, zipfile.ZipFile(forged, 'w') as target:
            for name in source.namelist(): target.writestr(name, source.read(name))
            target.writestr('../evil', b'x')
        with self.assertRaises(ValueError):
            validate_local_hotspot_package(forged.getvalue())

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the CHAP digest vector check')
    def test_chap_md5_implementation_matches_rfc_vector(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=1)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            login = archive.read('login.html').decode()
        start = login.index('function md5(s){')
        end = login.index('function doLogin()', start)
        script = login[start:end]
        result = subprocess.run(['node', '-e', script + ';process.stdout.write(md5("abc"))'], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, '900150983cd24fb0d6963f7d28e17f72')

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for the code normalization check')
    def test_typed_code_is_normalized_like_issued_codes(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=1)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            login = archive.read('login.html').decode()
        start = login.index('function norm(v){')
        script = login[start:login.index('function doLogin()', start)]
        result = subprocess.run(['node', '-e', script + ';process.stdout.write(norm(" ym-fv ln\\t"))'], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, 'YMFVLN')
        self.assertIn('text-transform:uppercase', login)
        self.assertIn('MikroMagic', login)

    def test_chap_md5_hashes_router_challenge_bytes_like_routeros(self):
        package = build_local_hotspot_package(self.settings, tenant_id='tenant_01', site_id='site_01', revision=1)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            login = archive.read('login.html').decode()
        start = login.index('function md5(s){')
        script = login[start:login.index('function norm(v){', start)]
        chap_id, challenge = '\xa7', '\x01\x80\xff\x10abc\x9e\x00z'
        result = subprocess.run(['node', '-e', script + ';process.stdout.write(md5(%s+"6ZYRPM"+%s))' % (json.dumps(chap_id), json.dumps(challenge))], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, hashlib.md5((chap_id + '6ZYRPM' + challenge).encode('latin-1')).hexdigest())

    def test_payment_card_uses_customizable_bank_fields_without_remote_links(self):
        settings = PortalConfig(
            business_name='မင်းလှ Teashop',
            language='both',
            direct_purchase=True,
            voucher_login=True,
            payment_destination='KBZPay 09 123 456 789',
            payment_instructions='Send exact amount. Then tell the counter your transaction ID. See also https://example.com/pay',
            payment_methods=['KBZPay', 'WavePay'],
        )
        package = build_local_hotspot_package(settings, tenant_id='tenant_01', site_id='site_01', revision=4)
        report = validate_local_hotspot_package(package)
        self.assertTrue(report['valid'])
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read('portal-manifest.json'))
            login = archive.read('login.html').decode()
            self.assertTrue(manifest['payment_card'])
            self.assertIn('class="pay"', login)
            self.assertIn('KBZPay 09 123 456 789', login)
            self.assertIn('Send exact amount', login)
            self.assertIn('example.com/pay', login)
            self.assertNotIn('https://', login)
            self.assertIn('KBZPay', login)
            self.assertIn('WavePay', login)
            self.assertIn('ကုဒ် မရှိသေးဘူးလား', login)

    def test_payment_card_hidden_when_direct_purchase_off(self):
        settings = PortalConfig(business_name='Shop', direct_purchase=False, voucher_login=True)
        package = build_local_hotspot_package(settings, tenant_id='tenant_01', site_id=None, revision=1)
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            manifest = json.loads(archive.read('portal-manifest.json'))
            login = archive.read('login.html').decode()
            self.assertFalse(manifest['payment_card'])
            self.assertNotIn('class="pay"', login)


if __name__ == '__main__': unittest.main()
