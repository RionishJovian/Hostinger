import os,sqlite3,tempfile,time,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config

class FrozenV1AuthPolicyMigrationTests(unittest.TestCase):
 def test_029_backfills_session_gate_and_lockout_without_discarding_history(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'auth-policy.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):command.upgrade(cfg,'028')
   now=int(time.time())
   with sqlite3.connect(file) as db:
    db.execute("INSERT INTO tenants VALUES ('t','Acceptance tenant')")
    db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u1','forced','hash','sme','t',1,1,9999999999)")
    db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active,must_change_password,temporary_password_expires) VALUES ('u2','normal','hash','sme','t',1,0,NULL)")
    db.execute("INSERT INTO sessions VALUES ('session-forced','u1',9999999999)")
    db.execute("INSERT INTO sessions VALUES ('session-normal','u2',9999999999)")
    db.execute("INSERT INTO audit_events VALUES ('audit-1','t','u1','password_changed','u1',?)",(now,))
    key=lambda value:hashlib.sha256(value.encode()).hexdigest()
    db.execute("INSERT INTO login_attempts VALUES (?,?,?)",(key('account:forced'),5,now))
    db.execute("INSERT INTO login_attempts VALUES (?,?,?)",(key('account:normal'),4,now))
    db.execute("INSERT INTO login_attempts VALUES (?,?,?)",(key('ip:192.0.2.10'),5,now))
    db.execute("INSERT INTO login_attempts VALUES (?,?,?)",(key('password-change:u1'),3,now))
    db.execute("INSERT INTO account_mfa VALUES ('u1',1,'encrypted-legacy',NULL,7,'[\"legacy-hash\"]',?)",(now,))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):command.upgrade(cfg,'head')
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):command.upgrade(cfg,'head')
   with sqlite3.connect(file) as db:
    self.assertEqual(db.execute('SELECT token_hash,must_change_password FROM sessions ORDER BY token_hash').fetchall(),[('session-forced',1),('session-normal',0)])
    self.assertEqual(db.execute('SELECT count(*) FROM audit_events').fetchone()[0],1)
    failures,locked_until,scope=db.execute('SELECT failures,locked_until,scope FROM login_attempts WHERE key=?',(key('account:forced'),)).fetchone();self.assertEqual((failures,scope),(5,'account'));self.assertGreaterEqual(locked_until,now+299);self.assertLessEqual(locked_until,now+301)
    self.assertEqual(db.execute('SELECT failures,locked_until,scope FROM login_attempts WHERE key=?',(key('account:normal'),)).fetchone(),(4,None,'account'))
    self.assertEqual(db.execute('SELECT failures,locked_until,scope FROM login_attempts WHERE key=?',(key('ip:192.0.2.10'),)).fetchone(),(5,None,'ip'))
    self.assertEqual(db.execute('SELECT failures,locked_until,scope FROM login_attempts WHERE key=?',(key('password-change:u1'),)).fetchone(),(3,None,'other'))
    self.assertEqual(db.execute('SELECT enabled,encrypted_secret,last_step,recovery_hashes FROM account_mfa WHERE user_id="u1"').fetchone(),(1,'encrypted-legacy',7,'["legacy-hash"]'))
