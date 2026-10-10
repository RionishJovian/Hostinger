"""Deterministic code-only test bundle. No recursive source distribution.

Explicit allowlist excludes ALL databases, credentials, keys, .env files,
historical artifacts and caches. Creates a NEW protected temporary directory.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import argparse

FILES = (
    'AGENTS.md', 'backend/__init__.py', 'backend/models.py',
    'backend/enrollment.py', 'backend/hub_orchestrator.py', 'backend/wireguard_hub.py',
    'dev/magic-hub/lima.yaml', 'dev/magic-hub/README.md',
    'scripts/verify-real-wireguard.py', 'scripts/package-magic-hub-test.py',
)
PAIRING_MODULES = '''__init__ account_sessions app appearance backups bootstrap_security deliveries
enrollment firmware guest_entry hub_orchestrator hubs incidents knowledge
local_portal_package magic_connect managed_devices media mfa models offline_vouchers
onboarding portal portal_export provider_adapters receipts revenue review_api
routeros_adapter routeros_compatibility routeros_preflight safe_changes schemas
site_planning site_portal sites staff subscription_billing subscriptions
voucher_batch voucher_sales vouchers wireguard_hub'''.split()
PAIRING_FILES = tuple('backend/'+name+'.py' for name in PAIRING_MODULES) + (
    'AGENTS.md', 'requirements.txt', 'scripts/verify-pairing-real-hub.py',
    'scripts/package-magic-hub-test.py', 'scripts/resume-pairing-real-hub.py',
)


def make_bundle(root, output, files=FILES):
    records = []
    with tarfile.open(output, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('Required regular allowlisted file missing')
            data = path.read_bytes()
            records.append(hashlib.sha256(data).hexdigest()+'  '+name+'\n')
            info = tarfile.TarInfo(name)
            info.size = len(data); info.mode = 0o600
            info.uid = info.gid = info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return ''.join(records)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--pairing',action='store_true')
    args=parser.parse_args()
    selected=PAIRING_FILES if args.pairing else FILES
    os.umask(0o077)
    folder = Path(tempfile.mkdtemp(prefix='mikromagic-hub-code-only-'))
    output = folder/'magic-hub-test.tar'
    manifest = make_bundle(Path(__file__).resolve().parents[1], output, selected)
    (folder/'files.sha256').write_text(manifest)
    print(json.dumps({'directory':str(folder),'records':len(selected),
        'manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),
        'deployment_sha256':hashlib.sha256(output.read_bytes()).hexdigest()},indent=2))
