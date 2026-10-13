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
            self.assertIn('Voucher', login)
            self.assertIn('ချိတ်ဆက်ရန်', login)
            self.assertIn('$(chap-id)', login)
            self.assertIn('$(chap-challenge)', login)
            self.assertIn('$(username)', login)
            self.assertNotIn('http-pap', login)
            self.assertNotRegex(login, r'<input[^>]*type="password"', 'single voucher field only')
            self.assertIn('$(error)', flogin)
            self.assertIn('ကုဒ် မှားနေပါသည်', flogin)
            self.assertIn('Too many devices', flogin)
            self.assertEqual(manifest.get('guest_ui'), 'burmese_first_single_voucher_field')
            self.assertIn('router_compatibility_verified', manifest)
            self.assertFalse(manifest['router_compatibility_verified'])
            self.assertLess(len(package), 128_000)
            self.assertLess(len(archive.read('login.html')), 32_000)

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


if __name__ == '__main__': unittest.main()
