import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class HotspotSyncMigrationTests(unittest.TestCase):
    def test_052_is_additive_keeps_voucher_checks_and_refuses_lossy_downgrade(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'hotspot-sync.sqlite3'
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + str(database))
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
            try:
                command.upgrade(cfg, '051')
                with sqlite3.connect(database) as db:
                    before = db.execute("SELECT sql FROM sqlite_master WHERE name='vouchers'").fetchone()[0]
                command.upgrade(cfg, 'head')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '061')
                    after = db.execute("SELECT sql FROM sqlite_master WHERE name='vouchers'").fetchone()[0]
                    self.assertEqual(before.count('CHECK'), after.count('CHECK'))
                    self.assertIn('code_sealed', {row[1] for row in db.execute('PRAGMA table_info(vouchers)')})
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute("INSERT INTO hotspot_voucher_sync (voucher_id,router_id,tenant_id,applied,attempts) VALUES ('v','r','t','gone',0)")
                    db.execute("INSERT INTO hotspot_voucher_sync (voucher_id,router_id,tenant_id,applied,attempts) VALUES ('v','r','t','present',0)")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '051')
                with sqlite3.connect(database) as db:
                    db.execute('DELETE FROM hotspot_voucher_sync')
                command.downgrade(cfg, '051')
                with sqlite3.connect(database) as db:
                    self.assertNotIn('code_sealed', {row[1] for row in db.execute('PRAGMA table_info(vouchers)')})
                command.upgrade(cfg, 'head')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
