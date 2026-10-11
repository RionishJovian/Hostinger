import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class VoucherCodeMigrationTests(unittest.TestCase):
    def test_035_marks_existing_codes_legacy_without_touching_hashes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'voucher-codes.sqlite3'
            url = 'sqlite:///' + str(database)
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', url)
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = url
            try:
                command.upgrade(cfg, '034')
                with sqlite3.connect(database) as db:
                    db.execute("INSERT INTO tenants (id, name) VALUES ('t', 'Shop')")
                    db.execute("INSERT INTO users (id, username, role, tenant_id, password_hash, active, must_change_password) VALUES ('u', 'owner', 'sme', 't', 'x', 1, 0)")
                    db.execute("INSERT INTO packages (id, tenant_id, policy, active) VALUES ('p', 't', '{}', 1)")
                    db.execute("INSERT INTO vouchers (id, tenant_id, package_id, policy, code_hash, code_hint, issued_by, request_key, created, expires, revoked) VALUES ('v', 't', 'p', '{}', 'legacy-hash', 'WXYZ', 'u', 'key', 1, 2, 0)")
                command.upgrade(cfg, 'head')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '047')
                    self.assertEqual(db.execute("SELECT code_hash, code_hint, code_format, code_prefix FROM vouchers WHERE id='v'").fetchone(), ('legacy-hash', 'WXYZ', 'legacy', None))
                    self.assertEqual(db.execute("SELECT disabled_at, deleted_at, router_sync FROM vouchers WHERE id='v'").fetchone(), (None, None, None))
                    self.assertEqual(db.execute("SELECT serial_no, production_job_id, sheet_no FROM vouchers WHERE id='v'").fetchone(), (None, None, None))
                    self.assertEqual(db.execute("SELECT dealer_id, dealer_price FROM vouchers WHERE id='v'").fetchone(), (None, None))
                    db.execute("INSERT INTO voucher_sales (id, voucher_id, tenant_id, snapshot, amount, currency, method, reference, evidence, recorded_by, created, cancelled_at, cancelled_by, cancel_reason) VALUES ('s', 'v', 't', '{}', 1000, 'MMK', 'Cash', '', '', 'u', 1, 2, 'u', 'Wrong card')")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '038')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute("SELECT cancel_reason FROM voucher_sales WHERE id='s'").fetchone()[0], 'Wrong card')
                    db.execute("DELETE FROM voucher_sales")
                    db.execute("INSERT INTO dealers (id, tenant_id, name, settlement, created_by, created) VALUES ('d', 't', 'Ko Aung', 'credit', 'u', 1)")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '037')
                with sqlite3.connect(database) as db:
                    db.execute("DELETE FROM dealers")
                    db.execute("INSERT INTO voucher_templates (id, tenant_id, name, settings, created_by, created) VALUES ('tp', 't', 'Cafe', '{}', 'u', 1)")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '036')
                with sqlite3.connect(database) as db:
                    db.execute("DELETE FROM voucher_templates")
                    db.execute("UPDATE vouchers SET disabled_at=5 WHERE id='v'")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '035')
                with sqlite3.connect(database) as db:
                    db.execute("UPDATE vouchers SET disabled_at=NULL WHERE id='v'")
                command.downgrade(cfg, '034')
                command.upgrade(cfg, 'head')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
