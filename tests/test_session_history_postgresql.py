"""Opt-in real PostgreSQL acceptance for frozen-v1 account history."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from sqlalchemy import select,text
from fastapi.testclient import TestClient
from backend.app import make_app,HASHER
from backend.models import Tenant,User,LoginHistory,SessionToken


class PostgreSQLSessionHistoryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.url=os.environ.get('MM_TEST_DB_URL')
  if not cls.url:raise unittest.SkipTest('MM_TEST_DB_URL is not set')
  if not cls.url.startswith(('postgresql://','postgresql+psycopg://')):raise RuntimeError('MM_TEST_DB_URL must identify PostgreSQL')
  database=cls.url.rsplit('/',1)[-1].split('?',1)[0]
  if not database.startswith('mm_test_'):raise RuntimeError('Refusing non-isolated PostgreSQL database; name must start mm_test_')
  root=Path(__file__).resolve().parents[1];cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
  with patch.dict(os.environ,{'DATABASE_URL':cls.url}):command.upgrade(cfg,'head')
  cls.app=make_app(cls.url)
  with cls.app.state.factory() as db:
   if db.scalar(text('SELECT count(*) FROM tenants')):raise RuntimeError('Refusing non-empty PostgreSQL integration database')
   first=Tenant(name='Synthetic PostgreSQL A');second=Tenant(name='Synthetic PostgreSQL B');db.add_all([first,second]);db.flush()
   cls.owner_a='pg-owner-a';cls.owner_b='pg-owner-b'
   db.add_all([User(id=cls.owner_a,username=cls.owner_a,password_hash=HASHER.hash('synthetic-pass-a'),role='sme',tenant_id=first.id),User(id=cls.owner_b,username=cls.owner_b,password_hash=HASHER.hash('synthetic-pass-b'),role='sme',tenant_id=second.id)]);db.commit()
  cls.client=TestClient(cls.app,client=('203.0.113.42',52000))

 @classmethod
 def tearDownClass(cls):
  if hasattr(cls,'client'):cls.client.close()
  if hasattr(cls,'app'):cls.app.state.engine.dispose()

 def login(self,username,password,agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'):
  response=self.client.post('/v1/auth/login',json={'username':username,'password':password},headers={'user-agent':agent})
  self.assertEqual(response.status_code,200,response.text)
  return {'Authorization':'Bearer '+response.json()['access_token']}

 def test_postgresql_migration_login_history_scope_and_session_revocation(self):
  self.assertEqual(self.client.get('/v1/ready').status_code,200)
  self.assertEqual(self.client.post('/v1/auth/login',json={'username':self.owner_a,'password':'bad-secret'},headers={'user-agent':'Mozilla/5.0 (iPhone; Mobile) Chrome/130'}).status_code,401)
  owner=self.login(self.owner_a,'synthetic-pass-a','Mozilla/5.0 (iPhone; Mobile) CriOS/130 Safari/604.1')
  other=self.login(self.owner_b,'synthetic-pass-b')
  history=self.client.get('/v1/account/login-history',headers=owner)
  self.assertEqual(history.status_code,200);self.assertEqual({event['outcome'] for event in history.json()},{'success','failure'})
  self.assertEqual(history.json()[0]['device'],'Reported mobile');self.assertEqual(history.json()[0]['browser'],'Chrome')
  self.assertEqual(history.json()[0]['approximate_source'],'203.0.113.0/24')
  other_history=self.client.get('/v1/account/login-history',headers=other).json()
  self.assertEqual(len(other_history),1);self.assertEqual(other_history[0]['outcome'],'success')
  second=self.login(self.owner_a,'synthetic-pass-a')
  owner_sessions=self.client.get('/v1/account/sessions',headers=owner).json()
  self.assertEqual(len(owner_sessions),2);target=next(item for item in owner_sessions if not item['current'])
  self.assertEqual(self.client.post('/v1/account/sessions/revoke',headers=other,json={'session_ref':target['session_ref']}).status_code,404)
  self.assertEqual(self.client.post('/v1/account/sessions/revoke',headers=owner,json={'session_ref':target['session_ref']}).status_code,200)
  self.assertEqual(self.client.get('/v1/me',headers=second).status_code,401)
  with self.app.state.factory() as db:
   self.assertEqual(db.scalar(text("SELECT version_num FROM alembic_version")),'043')
   self.assertEqual(db.scalar(select(LoginHistory.outcome).where(LoginHistory.user_id==self.owner_a,LoginHistory.outcome=='failure')),'failure')
   self.assertEqual(db.scalar(text("SELECT count(*) FROM login_history WHERE user_id='pg-owner-a'")),3)
   self.assertEqual(db.scalar(text("SELECT count(*) FROM sessions WHERE user_id='pg-owner-a'")),1)
