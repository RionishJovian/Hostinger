import os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config
class SafeChangeMigrationTests(unittest.TestCase):
 def test_empty_roundtrip_and_history_preservation(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'safe.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):
    command.upgrade(cfg,'head');command.downgrade(cfg,'026');command.upgrade(cfg,'head')
    with sqlite3.connect(file) as db:
     db.execute("INSERT INTO tenants VALUES ('t','Cafe')");db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u','owner','hash','sme','t',1,0,NULL)");db.execute("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Site','Asia/Yangon',1)");db.execute("INSERT INTO router_devices VALUES ('r','t','s','Gateway','RB5009','7.20','u',1)")
     db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,created_by,created,updated,error_code,rollback_attempted) VALUES ('c','t','r','wireguard_peer_keepalive','*A','high','previewed',1,'{}','{}',NULL,'{}','digest',NULL,0,NULL,'u',1,1,NULL,0)")
     db.execute("INSERT INTO backup_artifacts (id,tenant_id,site_id,router_id,kind,version,checksum,encrypted,status,restore_verified,integrity_verified,storage_ref,created,retention_until) VALUES ('b','t','s','r','router_export','1','digest',1,'created',0,1,'encrypted://test',1,2)")
     with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE backup_artifacts SET status='invented'")
    with self.assertRaisesRegex(RuntimeError,'Router change history exists'):command.downgrade(cfg,'026')
    with sqlite3.connect(file) as db:self.assertEqual(db.execute('SELECT status FROM router_changes').fetchone()[0],'previewed')
 def test_recovery_and_conflict_history_block_028_downgrade(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'recovery.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):
    command.upgrade(cfg,'head')
    with sqlite3.connect(file) as db:
     db.execute("INSERT INTO tenants VALUES ('t','Cafe')");db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u','owner','hash','sme','t',1,0,NULL)");db.execute("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Site','Asia/Yangon',1)");db.execute("INSERT INTO router_devices VALUES ('r','t','s','Gateway','RB5009','7.20','u',1)")
     db.execute("INSERT INTO router_changes (id,tenant_id,router_id,operation,resource_id,risk,status,revision,before,desired,actual,expected,diff,before_fingerprint,backup_id,safety_backup_verified,confirmed_at,gateway_deadline,last_probe_at,recovery_evidence,conflict_detected_at,conflict_history_until,resolution_choice,rollback_attempted,created_by,created,updated,error_code) VALUES ('c','t','r','wireguard_peer_keepalive','*A','high','recovery_required',2,'{}','{}','{}','{}','{}','digest',NULL,1,1,301,300,'{\"events\":[]}',NULL,NULL,NULL,1,'u',1,2,'rollback_unconfirmed')")
    with self.assertRaisesRegex(RuntimeError,'recovery/conflict history exists'):command.downgrade(cfg,'027')
    with sqlite3.connect(file) as db:self.assertEqual(db.execute('SELECT status,recovery_evidence FROM router_changes').fetchone()[0],'recovery_required')
if __name__=='__main__':unittest.main()
