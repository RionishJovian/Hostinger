import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from backend.models import Tenant,RouterDevice,MagicHub,RouterPlan,MagicConnectAttempt,MagicConnectEnrollment


class EnrollmentMigrationTests(unittest.TestCase):
    def test_additive_032_idempotency_and_evidence_preserving_downgrade_guard(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'new-scratch.sqlite3';url='sqlite:///'+str(database)
            cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
            with patch.dict(os.environ,{'DATABASE_URL':url}):
                command.upgrade(cfg,'031')
                engine=create_engine(url)
                with Session(engine) as session:
                    session.add(Tenant(id='t',name='Synthetic'));session.flush()
                    session.execute(text("INSERT INTO users (id,username,password_hash,role,tenant_id,active) VALUES ('u','synthetic','disabled','sme','t',1)"))
                    session.execute(text("INSERT INTO sites (id,tenant_id,name,timezone,created) VALUES ('s','t','Synthetic','UTC',1)"))
                    session.add_all([
                        RouterDevice(id='r',tenant_id='t',site_id='s',name='Synthetic',model='unknown',reported_routeros='',registered_by='u',created=1),
                        MagicHub(id='h',name='Synthetic',endpoint='test.invalid',port=51820,pool='10.90.1.0/24',public_key='synthetic-not-used',next_host=3,created=1),
                        RouterPlan(id='p',tenant_id='t',router_id='r',hub_id='h',router_public_key='synthetic-not-used',address='10.90.1.2',snapshot={},created=1),
                        MagicConnectAttempt(id='a',tenant_id='t',site_id='s',owner_id='u',router_name='Synthetic',code_hash='d'*64,comparison_code='000000',status='approved',created=1,expires=601,approved_at=2),
                    ]);session.commit()
                command.upgrade(cfg,'032');command.upgrade(cfg,'head')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0],'041')
                    self.assertEqual(db.execute('SELECT status FROM magic_connect_attempts').fetchone()[0],'approved')
                    self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)
                with Session(engine) as session:
                    session.add(MagicConnectEnrollment(plan_id='p',attempt_id='a',tenant_id='t',site_id='s',owner_id='u',created=2));session.commit()
                with self.assertRaisesRegex(RuntimeError,'preserve and roll forward'):command.downgrade(cfg,'031')
                with sqlite3.connect(database) as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM magic_connect_enrollments').fetchone()[0],1)
                    self.assertEqual(db.execute('SELECT version_num FROM alembic_version').fetchone()[0],'032')
                engine.dispose()
