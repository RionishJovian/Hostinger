import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class HotspotAccountingMigrationTests(unittest.TestCase):
    def test_054_creates_observation_table_and_refuses_lossy_downgrade(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'hotspot-accounting.sqlite3'
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + str(database))
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
            try:
                command.upgrade(cfg, '053')
                with sqlite3.connect(database) as db:
                    self.assertNotIn(
                        'hotspot_session_observations',
                        {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                    )
                    db.execute("INSERT INTO tenants VALUES ('t','Cafe')")
                    db.execute(
                        "INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) "
                        "VALUES ('u','owner','hash','sme','t',1,0,NULL)"
                    )
                    db.execute("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Site','Asia/Yangon',1)")
                    db.execute("INSERT INTO router_devices VALUES ('r','t','s','Gateway','RB5009','7.20','u',1)")
                command.upgrade(cfg, 'head')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '054')
                    db.execute(
                        "INSERT INTO hotspot_session_observations "
                        "(router_id,tenant_id,site_id,observed_at,status,active_count,guests,activations_applied,usage_updated,last_error,updated) "
                        "VALUES ('r','t','s',1,'verified',1,'[]',0,0,NULL,1)"
                    )
                    db.execute('DELETE FROM hotspot_session_observations')
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(
                            "INSERT INTO hotspot_session_observations "
                            "(router_id,tenant_id,site_id,observed_at,status,active_count,guests,activations_applied,usage_updated,last_error,updated) "
                            "VALUES ('r','t','s',1,'live',0,'[]',0,0,NULL,1)"
                        )
                    db.execute(
                        "INSERT INTO hotspot_session_observations "
                        "(router_id,tenant_id,site_id,observed_at,status,active_count,guests,activations_applied,usage_updated,last_error,updated) "
                        "VALUES ('r','t','s',1,'verified',1,'[]',0,0,NULL,1)"
                    )
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '053')
                with sqlite3.connect(database) as db:
                    db.execute('DELETE FROM hotspot_session_observations')
                command.downgrade(cfg, '053')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '053')
                    self.assertNotIn(
                        'hotspot_session_observations',
                        {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                    )
                command.upgrade(cfg, 'head')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
