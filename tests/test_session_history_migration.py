import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config


class SessionHistoryMigrationTests(unittest.TestCase):
 def test_033_adds_owner_history_without_inventing_old_session_metadata(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'session-history.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):
    command.upgrade(cfg,'032')
    with sqlite3.connect(file) as db:
     db.execute("INSERT INTO tenants (id,name) VALUES ('t','Synthetic')")
     db.execute("INSERT INTO users (id,username,password_hash,role,tenant_id,active) VALUES ('u','owner','hash','sme','t',1)")
     db.execute("INSERT INTO sessions (token_hash,user_id,expires,must_change_password) VALUES ('digest-only','u',9999999999,0)")
    command.upgrade(cfg,'033')
    with sqlite3.connect(file) as db:
     self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0],'033')
     self.assertEqual(db.execute('SELECT token_hash,user_id,login_at,last_active,device,browser,source FROM sessions').fetchone(),('digest-only','u',None,None,None,None,None))
     self.assertIn('login_history',{row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")})
     self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
     self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_login_history_user_created'").fetchone()[0],'ix_login_history_user_created')
