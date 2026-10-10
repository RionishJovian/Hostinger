"""Real PostgreSQL transactions; counting Hub adapter is explicitly MOCK.

Opt-in dedicated local lab URL only. Never use an application database here.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
import threading
import time
import secrets
import unittest
import uuid
from sqlalchemy import create_engine,select,text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.engine import make_url
from backend.models import Tenant,User,Site,RouterDevice,MagicHub,HubAssignment,RouterPlan,MagicConnectAttempt,MagicConnectEnrollment,MagicConnectEvent
from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy,HubOrchestrationError
from backend.app import make_app,HASHER
from fastapi.testclient import TestClient


class CountingAdapter:
    def __init__(self):
        self.peers=set();self.adds=0;self.removes=0
        self.entered=threading.Event();self.release=threading.Event();self.hold=False
        self.mutex=threading.Lock()
    def verify_hub_identity(self,*args):return True
    def provision_peer(self,interface,key,*args):
        self.entered.set()
        if self.hold and not self.release.wait(5):raise RuntimeError('test_release_timeout')
        with self.mutex:self.peers.add(key);self.adds+=1
        return {'result':'provisioned'}
    def revoke_peer(self,interface,key,*args):
        with self.mutex:self.peers.discard(key);self.removes+=1
        return {'result':'revoked'}
    def observe_peer(self,interface,key,*args):return {'peer_found':key in self.peers,'allowed_address_match':key in self.peers}


@unittest.skipUnless(os.environ.get('MM_ENROLLMENT_TEST_URL'),'Dedicated PostgreSQL lab not enabled')
class PostgreSQLEnrollmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url=make_url(os.environ['MM_ENROLLMENT_TEST_URL'])
        assert url.drivername=='postgresql+psycopg' and url.database=='mm_enrollment_test'
        assert url.username=='mm_enrollment_test' and url.host in (None,'')
        assert url.query.get('host','').startswith('/private/tmp/mm-enroll-pg-')
        cls.engine=create_engine(url,pool_size=8,max_overflow=0,connect_args={'options':'-c statement_timeout=10000 -c lock_timeout=8000'})
    @classmethod
    def tearDownClass(cls):cls.engine.dispose()
    def setUp(self):
        self.n=uuid.uuid4().hex[:12];self.now=int(time.time());self.adapter=CountingAdapter()
        type(self).sequence=getattr(type(self),'sequence',0)+1
        self.pool=f'10.90.{type(self).sequence}.0/24'
        self.service=HubPeerOrchestrator(self.adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'),clock=lambda:self.now)
        self.t='t'+self.n;self.u='u'+self.n;self.s='s'+self.n;self.h='h'+self.n;self.r='r'+self.n;self.p='p'+self.n;self.a='a'+self.n
        with Session(self.engine) as db:
            db.add(Tenant(id=self.t,name='Synthetic'));db.flush()
            db.add(User(id=self.u,username=self.u,password_hash='not-a-login',role='sme',tenant_id=self.t,active=True));db.flush()
            db.add(Site(id=self.s,tenant_id=self.t,name='Synthetic',timezone='UTC',created=self.now));db.flush()
            db.add(RouterDevice(id=self.r,tenant_id=self.t,site_id=self.s,name='Synthetic',model='synthetic',reported_routeros='',registered_by=self.u,created=self.now))
            db.add(MagicHub(id=self.h,name=self.h,endpoint=self.h+'.example.com',port=51820,pool=self.pool,public_key=self.key(),interface_name='wg-mm',next_host=3,created=self.now));db.flush()
            db.add(HubAssignment(hub_id=self.h,tenant_id=self.t,created=self.now))
            db.add(RouterPlan(id=self.p,tenant_id=self.t,router_id=self.r,hub_id=self.h,router_public_key=self.key(),address='10.90.1.2',snapshot={},created=self.now,reviewed_at=self.now,lifecycle_state='awaiting_bootstrap'))
            db.add(MagicConnectAttempt(id=self.a,tenant_id=self.t,site_id=self.s,owner_id=self.u,router_name='Synthetic',code_hash=hashlib.sha256(self.a.encode()).hexdigest(),comparison_code='000000',status='approved',created=self.now,expires=self.now+600,approved_at=self.now));db.flush()
            db.add(MagicConnectEnrollment(plan_id=self.p,attempt_id=self.a,tenant_id=self.t,site_id=self.s,owner_id=self.u,created=self.now));db.commit()
    @staticmethod
    def key():return base64.b64encode(os.urandom(32)).decode()
    def operation(self,operation='provision',key='same-operation-001',tenant=None):
        with Session(self.engine,expire_on_commit=False) as db:
            p=db.get(RouterPlan,self.p);h=db.get(MagicHub,self.h)
            try:
                if operation=='provision':result=self.service.provision(db,p,h,tenant or self.t,confirmed=True,idempotency_key=self.n+'-'+key)
                elif operation=='revoke':result=self.service.emergency_lock(db,p,h,self.t,actor_id=self.u,reason='Synthetic lab emergency',confirmed=True)
                else:result=self.service.recover(db,p,h,self.t,confirmed=True)
                db.commit();return result
            except HubOrchestrationError as exc:db.rollback();return {'error':exc.code}
    def race(self,left,right):
        gate=threading.Barrier(2)
        def run(fn):gate.wait(timeout=5);return fn()
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(run,left);b=pool.submit(run,right)
            return [a.result(timeout=15),b.result(timeout=15)]
    def test_same_key_concurrent_provision_single_effect_and_durable_claim(self):
        outcomes=self.race(self.operation,self.operation)
        self.assertEqual(self.adapter.adds,1)
        self.assertTrue(any(x.get('state')=='awaiting_handshake' for x in outcomes))
        self.assertFalse(self.operation().get('error'));self.assertEqual(self.adapter.adds,1)
        with Session(self.engine) as db:
            self.assertIsNotNone(db.get(MagicConnectEnrollment,self.p).consumed_at)
            self.assertEqual(len(list(db.scalars(select(MagicConnectEvent).where(MagicConnectEvent.attempt_id==self.a,MagicConnectEvent.event=='peer_operation_claimed')))),1)
    def test_different_keys_one_winner(self):
        outcomes=self.race(lambda:self.operation(key='operation-first-001'),lambda:self.operation(key='operation-second-001'))
        self.assertEqual(self.adapter.adds,1);self.assertEqual(sum('error' in x for x in outcomes),1)
    def test_expiry_boundary_and_wrong_tenant_no_effect(self):
        self.assertIn('error',self.operation(tenant='wrong-tenant'))
        self.now+=600
        self.assertEqual(self.operation().get('error'),'valid_owner_approved_enrollment_required')
        self.assertEqual(self.adapter.adds,0)
    def test_closed_attempts_cannot_be_consumed(self):
        for status in ('cancelled','denied','expired'):
            with Session(self.engine) as db:db.get(MagicConnectAttempt,self.a).status=status;db.commit()
            self.assertIn('error',self.operation())
        self.assertEqual(self.adapter.adds,0)
    def test_attempt_unique_binding_under_two_connections(self):
        # Existing binding is deleted only in this new synthetic scenario.
        with Session(self.engine) as db:
            db.delete(db.get(MagicConnectEnrollment,self.p));db.commit()
        def insert():
            with Session(self.engine) as db:
                try:
                    db.add(MagicConnectEnrollment(plan_id=self.p,attempt_id=self.a,tenant_id=self.t,site_id=self.s,owner_id=self.u,created=self.now));db.commit();return True
                except IntegrityError:db.rollback();return False
        self.assertEqual(sorted(self.race(insert,insert)),[False,True])
    def test_revocation_cannot_be_undone_by_inflight_peer_write(self):
        self.adapter.hold=True
        with ThreadPoolExecutor(2) as pool:
            provision=pool.submit(self.operation)
            self.assertTrue(self.adapter.entered.wait(3))
            revoke=pool.submit(self.operation,'revoke')
            # Let revocation compete while the adapter's add is in flight.
            time.sleep(.2);self.adapter.release.set()
            provision.result(timeout=12);revoke.result(timeout=12)
        self.assertEqual(self.adapter.peers,set(),'locked peer resurrected by inflight provision')
        with Session(self.engine) as db:self.assertEqual(db.get(RouterPlan,self.p).lifecycle_state,'management_locked')
        self.assertIn('error',self.operation())
    def test_interrupted_durable_claim_recovers_without_new_authority(self):
        original=self.adapter.provision_peer
        def crash(*args):raise RuntimeError('synthetic process interruption')
        self.adapter.provision_peer=crash
        with self.assertRaises(RuntimeError):self.operation()
        self.adapter.provision_peer=original
        self.assertEqual(self.operation().get('error'),'same_peer_operation_in_progress')
        self.assertEqual(self.operation('recover')['recovery_readback'],'peer_absent')
        self.assertFalse(self.operation().get('error'));self.assertEqual(self.adapter.adds,1)

    def authenticated_client(self):
        password=secrets.token_urlsafe(32)
        with Session(self.engine) as db:db.get(User,self.u).password_hash=HASHER.hash(password);db.commit()
        app=make_app(os.environ['MM_ENROLLMENT_TEST_URL'],initialize=False)
        app.state.magic_connect_pairing_enabled=True  # Isolated synthetic PostgreSQL test only.
        app.state.magic_hub_orchestrator=self.service
        client=TestClient(app)
        response=client.post('/v1/auth/login',json={'username':self.u,'password':password})
        self.assertEqual(response.status_code,200)
        return app,client,{'Authorization':'Bearer '+response.json()['access_token']}
    def test_authenticated_cancel_during_consumed_inflight_provision_is_rejected(self):
        app,client,headers=self.authenticated_client();self.adapter.hold=True
        try:
            with ThreadPoolExecutor(2) as pool:
                provision=pool.submit(self.operation);self.assertTrue(self.adapter.entered.wait(3))
                cancelled=client.post(f'/v1/magic-connect/attempts/{self.a}/cancel',headers=headers)
                self.assertEqual(cancelled.status_code,409)
                self.adapter.release.set();provision.result(timeout=12)
            with Session(self.engine) as db:self.assertEqual(db.get(MagicConnectAttempt,self.a).status,'approved')
        finally:self.adapter.release.set();client.close();app.state.engine.dispose()
    def test_authenticated_cancel_vs_consume_race(self):
        app,client,headers=self.authenticated_client()
        try:
            outcomes=self.race(self.operation,lambda:client.post(f'/v1/magic-connect/attempts/{self.a}/cancel',headers=headers).status_code)
            with Session(self.engine) as db:
                e=db.get(MagicConnectEnrollment,self.p);a=db.get(MagicConnectAttempt,self.a)
                if e.consumed_at:self.assertEqual(a.status,'approved');self.assertEqual(outcomes[1],409)
                else:self.assertEqual(a.status,'cancelled');self.assertEqual(self.adapter.adds,0)
        finally:client.close();app.state.engine.dispose()
    def test_authenticated_two_plans_one_attempt_binding_race(self):
        app,client,headers=self.authenticated_client()
        try:
            with Session(self.engine) as db:db.delete(db.get(MagicConnectEnrollment,self.p));db.commit()
            router=client.post('/v1/routers',headers=headers,json={'site_id':self.s,'name':'Alternative synthetic','model':'synthetic','reported_routeros':''})
            self.assertEqual(router.status_code,201)
            p=client.post('/v1/routers/'+router.json()['id']+'/plan',headers=headers,json={'hub_id':self.h,'router_public_key':self.key()})
            self.assertEqual(p.status_code,201);other=p.json()['id']
            self.assertEqual(client.post(f'/v1/router-plans/{other}/review',headers=headers,json={'confirmed_review':True}).status_code,200)
            def bind(plan):return client.post(f'/v1/magic-connect/attempts/{self.a}/enrollment',headers=headers,json={'plan_id':plan}).status_code
            self.assertEqual(sorted(self.race(lambda:bind(self.p),lambda:bind(other))),[201,409])
            with Session(self.engine) as db:self.assertEqual(len(list(db.scalars(select(MagicConnectEnrollment).where(MagicConnectEnrollment.attempt_id==self.a)))),1)
        finally:client.close();app.state.engine.dispose()
    def test_emergency_lock_vs_recovery_preserves_lock_intent(self):
        self.operation()
        with Session(self.engine) as db:db.get(RouterPlan,self.p).lifecycle_state='provisioning_peer';db.commit()
        self.race(lambda:self.operation('recover'),lambda:self.operation('revoke'))
        self.assertEqual(self.adapter.peers,set())
        with Session(self.engine) as db:self.assertEqual(db.get(RouterPlan,self.p).lifecycle_state,'management_locked')
