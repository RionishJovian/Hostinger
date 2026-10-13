import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config


class HotspotPortalPublishMigrationTests(unittest.TestCase):
    def test_053_widens_operation_and_refuses_lossy_downgrade(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'portal-publish.sqlite3'
            cfg = Config(str(root / 'alembic.ini'))
            cfg.set_main_option('script_location', str(root / 'backend/migrations'))
            cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + str(database))
            old = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = 'sqlite:///' + str(database)
            try:
                command.upgrade(cfg, '052')
                with sqlite3.connect(database) as db:
                    db.execute("INSERT INTO tenants VALUES ('t','Cafe')")
                    db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u','owner','hash','sme','t',1,0,NULL)")
                    db.execute("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Site','Asia/Yangon',1)")
                    db.execute("INSERT INTO router_devices VALUES ('r','t','s','Gateway','RB5009','7.20','u',1)")
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,expected,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,gateway_deadline,last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,resolution_choice,rollback_attempted,created_by,created,updated,error_code) VALUES ('c','t','r','hotspot_portal_publish','*A','high','previewed',1,'{}','{}',NULL,NULL,'{}','digest',NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'u',1,1,NULL)")
                command.upgrade(cfg, 'head')
                with sqlite3.connect(database) as db:
                    head = db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
                    self.assertGreaterEqual(head, '055')
                    db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,expected,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,gateway_deadline,last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,resolution_choice,rollback_attempted,created_by,created,updated,error_code) VALUES ('c','t','r','hotspot_portal_publish','*A','high','previewed',1,'{}','{}',NULL,NULL,'{}','digest',NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'u',1,1,NULL)")
                    db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,expected,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,gateway_deadline,last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,resolution_choice,rollback_attempted,created_by,created,updated,error_code) VALUES ('w','t','r','wireguard_peer_keepalive','*B','high','previewed',1,'{}','{}',NULL,NULL,'{}','digest',NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'u',1,1,NULL)")
                with self.assertRaises(RuntimeError):
                    command.downgrade(cfg, '052')
                with sqlite3.connect(database) as db:
                    db.execute("DELETE FROM router_changes WHERE operation='hotspot_portal_publish'")
                    db.execute("DELETE FROM router_changes WHERE operation in ('guest_wifi_settings','guest_network_addressing')")
                command.downgrade(cfg, '052')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0], '052')
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,expected,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,gateway_deadline,last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,resolution_choice,rollback_attempted,created_by,created,updated,error_code) VALUES ('c2','t','r','hotspot_portal_publish','*A','high','previewed',1,'{}','{}',NULL,NULL,'{}','digest',NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,'u',1,1,NULL)")
                command.upgrade(cfg, 'head')
            finally:
                if old is None:
                    os.environ.pop('DATABASE_URL', None)
                else:
                    os.environ['DATABASE_URL'] = old


if __name__ == '__main__':
    unittest.main()
