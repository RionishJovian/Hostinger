import os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config

class RouterEvidenceMigrationTests(unittest.TestCase):
 def test_evidence_schema_and_preservation_guard(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'evidence.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):
    command.upgrade(cfg,'head')
    with sqlite3.connect(file) as db:
     db.execute("INSERT INTO tenants VALUES ('t','Cafe')")
     db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u','owner','hash','sme','t',1,0,NULL)")
     db.execute("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Site','Asia/Yangon',1)")
     db.execute("INSERT INTO router_devices VALUES ('r','t','s','Gateway','RB5009','7.20','u',1)")
     db.execute("INSERT INTO router_evidence VALUES ('e','t','r','preflight',1,'routeros_rest_live_read','{}','u',1)")
     self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
    with self.assertRaisesRegex(RuntimeError,'Router acceptance evidence exists'):command.downgrade(cfg,'025')
    with sqlite3.connect(file) as db:self.assertEqual(db.execute('SELECT source FROM router_evidence').fetchone()[0],'routeros_rest_live_read')

if __name__=='__main__':unittest.main()
