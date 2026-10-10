import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MagicHubPackageTests(unittest.TestCase):
    def test_authenticated_pairing_bundle_is_explicit_code_only_and_reproducible(self):
        spec=importlib.util.spec_from_file_location('hub_package',ROOT/'scripts/package-magic-hub-test.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            one=Path(folder)/'one.tar';two=Path(folder)/'two.tar'
            self.assertEqual(module.make_bundle(ROOT,one,module.PAIRING_FILES),module.make_bundle(ROOT,two,module.PAIRING_FILES))
            self.assertEqual(one.read_bytes(),two.read_bytes())
            with tarfile.open(one) as archive:
                self.assertEqual(set(archive.getnames()),set(module.PAIRING_FILES))
                for member in archive.getmembers():
                    self.assertTrue(member.isfile());self.assertEqual(member.mode,0o600)
                    self.assertFalse(any(x in member.name for x in ('.sqlite','.db','.env','.pem','.key')))
                    self.assertFalse('safe_change_worker' in member.name)
    def test_code_only_bundle_is_deterministic_and_excludes_private_artifacts(self):
        spec=importlib.util.spec_from_file_location('hub_package',ROOT/'scripts/package-magic-hub-test.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            one=Path(folder)/'one.tar';two=Path(folder)/'two.tar'
            self.assertEqual(module.make_bundle(ROOT,one),module.make_bundle(ROOT,two))
            self.assertEqual(one.read_bytes(),two.read_bytes())
            with tarfile.open(one) as archive:
                self.assertEqual(set(archive.getnames()),set(module.FILES))
                for name in archive.getnames():
                    self.assertFalse(any(x in name for x in ('.sqlite','.db','.env','.pem','.key')))
                self.assertTrue(all(x.isfile() and x.mode==0o600 for x in archive.getmembers()))
