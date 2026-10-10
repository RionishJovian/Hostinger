import hashlib
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "release" / "mikromagic-build21-public-test.zip"


class PublicTestPackageTests(unittest.TestCase):
    def test_hub_tmpfs_options_are_one_quoted_compose_entry(self):
        compose = (ROOT / "compose.hostinger-public-test.yaml").read_text()
        self.assertIn('tmpfs: ["/tmp:rw,noexec,nosuid,nodev,size=16m"]', compose)

    def test_hub_udp_port_can_be_published_and_database_secret_is_split(self):
        compose = (ROOT / "compose.hostinger-public-test.yaml").read_text()
        hub = compose.split("\n  magic-hub:\n", 1)[1].split("\n  web:\n", 1)[0]
        self.assertIn("ports:", hub)
        self.assertIn("networks: [private, hub_uplink]", hub)
        self.assertIn("\n  hub_uplink: {}\n", compose)
        self.assertIn("\n  private:\n    internal: true\n", compose)
        self.assertEqual(compose.count("hub_uplink"), 2)
        self.assertEqual(compose.count("    secrets: [postgres_password]\n"), 1)
        self.assertIn("{source: postgres_password_api, target: postgres_password}", compose)
        self.assertEqual(compose.count("secrets: *api_secrets"), 1)
        self.assertNotIn("[postgres_password, backup_key", compose)

    def test_package_is_deterministic_and_contains_current_head(self):
        command = [sys.executable, str(ROOT / "scripts/package-hostinger-public-test.py")]
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        first = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        self.assertEqual(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(), first)
        with zipfile.ZipFile(ARTIFACT) as archive:
            names = archive.namelist()
            self.assertIn("compose.hostinger-public-test.yaml", names)
            self.assertIn("Dockerfile.hub", names)
            self.assertIn("requirements.hub.txt", names)
            self.assertIn("backend/hub_agent.py", names)
            self.assertIn("backend/migrations/versions/034_hotspot_portal_plans.py", names)
            self.assertNotIn("compose.hostinger-rc.yaml", names)
            self.assertTrue(all(not PurePosixPath(name).is_absolute() for name in names))
            self.assertTrue(all(".." not in PurePosixPath(name).parts for name in names))
            self.assertFalse(any("secret" in part.lower() for name in names for part in PurePosixPath(name).parts))


if __name__ == "__main__":
    unittest.main()
