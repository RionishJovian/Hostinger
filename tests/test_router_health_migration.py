import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class RouterHealthMigrationTests(unittest.TestCase):
    def test_060_adds_health_observations_and_refuses_lossy_downgrade(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'router-health.sqlite3'
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + str(database))
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
            try:
                command.upgrade(cfg, 'head')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '061')
                    cols = {row[1] for row in db.execute('PRAGMA table_info(router_health_observations)')}
                    self.assertTrue({'router_id', 'metrics', 'status', 'observed_at'} <= cols)
                    db.execute(
                        "INSERT INTO router_health_observations "
                        "(router_id,tenant_id,site_id,observed_at,status,metrics,updated) "
                        "VALUES ('r','t','s',1,'verified','{}',1)"
                    )
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '059')
                with sqlite3.connect(database) as db:
                    db.execute('DELETE FROM router_health_observations')
                command.downgrade(cfg, '059')
                with sqlite3.connect(database) as db:
                    self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='router_health_observations'").fetchone())
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '059')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
