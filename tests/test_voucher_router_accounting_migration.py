"""Migration 055: additive router-only activation/usage columns on vouchers."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class VoucherRouterAccountingMigrationTests(unittest.TestCase):
    def test_055_adds_accounting_columns_and_refuses_lossy_downgrade(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'voucher-router-accounting.sqlite3'
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + str(database))
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
            try:
                command.upgrade(cfg, '054')
                with sqlite3.connect(database) as db:
                    cols = {row[1] for row in db.execute('PRAGMA table_info(vouchers)')}
                    self.assertNotIn('activated', cols)
                    self.assertNotIn('used_bytes', cols)
                    self.assertNotIn('connected_seconds', cols)
                    db.execute("INSERT INTO tenants VALUES ('t','Cafe')")
                    db.execute(
                        "INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) "
                        "VALUES ('u','owner','hash','sme','t',1,0,NULL)"
                    )
                    db.execute(
                        "INSERT INTO packages (id,tenant_id,policy,active) "
                        "VALUES ('p','t','{\"name\":\"Day\",\"service\":\"internet\"}',1)"
                    )
                    db.execute(
                        "INSERT INTO vouchers "
                        "(id,tenant_id,package_id,policy,code_hash,code_hint,code_format,issued_by,request_key,created,expires,revoked) "
                        "VALUES ('v','t','p','{}','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','AB','standard','u','req-key-00000001',1,999999,0)"
                    )
                command.upgrade(cfg, '055')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '055')
                    row = db.execute(
                        'SELECT activated, used_bytes, connected_seconds FROM vouchers WHERE id=? ',
                        ('v',),
                    ).fetchone()
                    self.assertEqual(row, (None, 0, 0))
                    db.execute('UPDATE vouchers SET activated=100, used_bytes=50 WHERE id=?', ('v',))
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '054')
                with sqlite3.connect(database) as db:
                    db.execute('UPDATE vouchers SET activated=NULL, used_bytes=0, connected_seconds=0 WHERE id=?', ('v',))
                command.downgrade(cfg, '054')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '054')
                    cols = {row[1] for row in db.execute('PRAGMA table_info(vouchers)')}
                    self.assertNotIn('activated', cols)
                command.upgrade(cfg, 'head')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
