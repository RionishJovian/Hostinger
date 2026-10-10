"""Seed one synthetic platform login in a fresh, isolated acceptance database.

The password is written only to a caller-supplied private evidence directory.
Never use this helper against an existing or production database.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
from urllib.parse import unquote

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app import HASHER
from backend.models import User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True)
    args = parser.parse_args()
    folder = Path(args.evidence_dir).resolve(strict=True)
    if not str(folder).startswith('/private/tmp/mm-build21-rc.') or folder.stat().st_mode & 0o077:
        raise SystemExit('A private, new Build 21 RC evidence directory is required')
    url = os.environ.get('DATABASE_URL', '')
    if 'mm_rc_20261009' not in url or '/private/tmp/mm-build21-rc.' not in unquote(url):
        raise SystemExit('Refusing to seed a non-isolated RC database')
    os.umask(0o077)
    username = 'rc-platform-' + secrets.token_hex(4)
    password = secrets.token_urlsafe(32)
    with Session(create_engine(url)) as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            raise SystemExit('Refusing to seed a database that already has accounts')
        session.add(User(username=username, role='platform', tenant_id=None,
                         password_hash=HASHER.hash(password), active=True))
        session.commit()
    output = folder / 'login.json'
    with output.open('x') as handle:
        json.dump({'username': username, 'password': password}, handle)
    output.chmod(0o600)
    print(f'Synthetic platform account created; credential file: {output}')


if __name__ == '__main__':
    main()
