import os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from alembic import command
from alembic.config import Config
from sqlalchemy import select
import test_hubs
from test_hubs import key
from backend.models import MagicConnectEvent

class RouterSetupTests(unittest.TestCase):
 H=test_hubs.HubTests
 setUp=H.setUp;tearDown=H.tearDown;login=H.login;setup_hub=H.setup_hub;router=H.router;plan=H.plan
 def approved(self,owner,site,router,setup=True):
  self.app.state.magic_connect_router_setup_enabled=setup
  attempt=self.client.post(f'/v1/sites/{site}/magic-connect/attempts',headers=owner,json={'router_name':'Shop gateway'}).json()
  tech={'Authorization':'Bearer '+self.client.post('/v1/magic-connect/claim',json={'code':attempt['manual_code']}).json()['technician_session']}
  return attempt,tech
 def approve(self,owner,attempt,router):
  return self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True,'router_id':router})
 def status(self,tech):return self.client.get('/v1/magic-connect/technician/status',headers=tech).json()

 def test_router_setup_stays_unavailable_while_flag_is_off(self):
  _,owner,_,site,_=self.setup_hub();router=self.router(owner,site)
  attempt,tech=self.approved(owner,site,router,setup=False)
  self.assertFalse(self.client.get('/v1/magic-connect/capability').json()['router_setup_available'])
  self.assertEqual(self.approve(owner,attempt,router).status_code,503)
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/approve",headers=owner,json={'comparison_confirmed':True}).status_code,200)
  status=self.status(tech)
  self.assertEqual(status['setup_access'],'blocked_pending_hardware_verification');self.assertIsNone(status['router_setup']);self.assertFalse(status['setup_instructions_available'])
  self.assertEqual(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(9)}).status_code,503)

 def test_technician_key_drives_plan_review_and_hub_peer_without_claiming_connected(self):
  from backend.hub_orchestrator import HubPeerOrchestrator,HostOperationPolicy
  from test_hub_orchestrator import FakeHubAdapter
  _,owner,hub,site,_=self.setup_hub();router=self.router(owner,site)
  attempt,tech=self.approved(owner,site,router)
  self.assertTrue(self.client.get('/v1/magic-connect/capability').json()['router_setup_available'])
  self.assertEqual(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(9)}).status_code,409)
  approved=self.approve(owner,attempt,router);self.assertEqual(approved.status_code,200,approved.text)
  self.assertEqual(approved.json()['setup_access'],'transport_setup')
  setup=self.status(tech)['router_setup'];iface='mm-'+router[:8]
  self.assertEqual(setup['step'],'generate_key');self.assertEqual(setup['interface'],iface)
  self.assertIn(f'/interface wireguard add name={iface} listen-port=13239 comment="MikroMagic management"',setup['commands']['create_interface'])
  self.assertNotIn('connect_hub',setup['commands']);self.assertTrue(setup['commands']['rollback'])
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/plan",headers=owner,json={'hub_id':hub}).status_code,409)
  submitted=self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(9)})
  self.assertEqual(submitted.status_code,200,submitted.text);self.assertFalse(submitted.json()['replayed'])
  self.assertTrue(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(9)}).json()['replayed'])
  self.assertEqual(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(10)}).status_code,409)
  listed=self.client.get(f'/v1/sites/{site}/magic-connect/attempts',headers=owner).json()[0]
  self.assertEqual((listed['router_id'],listed['router_public_key']),(router,key(9)))
  self.assertEqual(self.status(tech)['router_setup']['step'],'owner_review')
  self.assertEqual(self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/plan",headers=self.login('other'),json={'hub_id':hub}).status_code,404)
  plan=self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/plan",headers=owner,json={'hub_id':hub})
  self.assertEqual(plan.status_code,201,plan.text);plan=plan.json()
  self.assertEqual((plan['router_id'],plan['snapshot']['router']['public_key'],plan['snapshot']['router']['interface']),(router,key(9),iface))
  self.assertEqual(self.status(tech)['router_setup']['step'],'owner_review')
  self.client.post(f"/v1/router-plans/{plan['id']}/review",headers=owner,json={'confirmed_review':True})
  setup=self.status(tech)['router_setup']
  self.assertEqual(setup['step'],'connect_hub')
  self.assertEqual(setup['commands']['connect_hub'][:3],[
   f'/interface wireguard peers add interface={iface} public-key="{key(1)}" endpoint-address=hub.example.com endpoint-port=51820 allowed-address=10.90.1.1/32 persistent-keepalive=25s comment="MikroMagic Hub"',
   f'/ip address add address={plan["address"]}/32 interface={iface} comment="MikroMagic management"',
   f'/ip route add dst-address=10.90.1.1/32 gateway={iface} comment="MikroMagic Hub"'])
  bound=self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/enrollment",headers=owner,json={'plan_id':plan['id']})
  self.assertEqual(bound.status_code,201,bound.text)
  adapter=FakeHubAdapter()
  self.app.state.magic_hub_orchestrator=HubPeerOrchestrator(adapter,HostOperationPolicy('isolated-magic-connect-test',True,True,'wg-mm'))
  provision=self.client.post(f"/v1/router-plans/{plan['id']}/hub-peer/provision",headers=owner,json={'confirmed':True,'idempotency_key':'magic-connect-'+plan['id']})
  self.assertEqual(provision.status_code,200,provision.text);self.assertTrue(adapter.peer_present)
  status=self.status(tech)
  self.assertEqual(status['router_setup']['step'],'awaiting_handshake');self.assertFalse(status['connection_verified']);self.assertFalse(status['router_write_access'])
  with self.app.state.factory() as s:
   self.assertIn('router_key_submitted',{e.event for e in s.scalars(select(MagicConnectEvent))})

 def test_router_link_and_key_guards(self):
  _,owner,hub,site,_=self.setup_hub();router=self.router(owner,site)
  other_site=self.client.post('/v1/sites',headers=owner,json={'name':'Second shop'}).json()['id'];elsewhere=self.router(owner,other_site,'Elsewhere')
  planned=self.router(owner,site,'Planned');self.assertEqual(self.plan(owner,hub,planned,5).status_code,201)
  attempt,tech=self.approved(owner,site,router)
  self.assertEqual(self.approve(owner,attempt,elsewhere).status_code,404)
  self.assertEqual(self.approve(owner,attempt,planned).status_code,409)
  self.assertEqual(self.approve(owner,attempt,router).status_code,200)
  for used in (key(1),key(5)):
   self.assertEqual(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':used}).status_code,409)
  self.assertEqual(self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':'not-a-key'}).status_code,422)
  self.client.post('/v1/magic-connect/technician/router-key',headers=tech,json={'router_public_key':key(9)})
  manual=self.router(owner,site,'Manual');manual_plan=self.plan(owner,hub,manual,6).json()['id']
  self.client.post(f'/v1/router-plans/{manual_plan}/review',headers=owner,json={'confirmed_review':True})
  mismatch=self.client.post(f"/v1/magic-connect/attempts/{attempt['id']}/enrollment",headers=owner,json={'plan_id':manual_plan})
  self.assertEqual(mismatch.status_code,409);self.assertIn('submitted through this pairing',mismatch.text)

 def test_migration_round_trip_refuses_to_discard_router_keys(self):
  root=Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'router-key.sqlite3';cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'backend/migrations'))
   with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(file)}):
    command.upgrade(cfg,'head')
    with sqlite3.connect(file) as db:
     with self.assertRaises(sqlite3.IntegrityError):
      db.execute("INSERT INTO magic_connect_attempts (id,tenant_id,site_id,owner_id,router_name,code_hash,comparison_code,status,created,expires) VALUES ('x','t','site','u','Gateway',?,'123456','bogus',1,601)",('c'*64,))
     db.execute("INSERT INTO magic_connect_attempts (id,tenant_id,site_id,owner_id,router_name,code_hash,comparison_code,status,created,expires,router_public_key) VALUES ('a','t','site','u','Gateway',?,'123456','approved',1,601,?)",('a'*64,key(9)))
     with self.assertRaises(sqlite3.IntegrityError):
      db.execute("INSERT INTO magic_connect_attempts (id,tenant_id,site_id,owner_id,router_name,code_hash,comparison_code,status,created,expires,router_public_key) VALUES ('b','t','site','u','Gateway',?,'123456','approved',1,601,?)",('b'*64,key(9)))
    with self.assertRaisesRegex(RuntimeError,'Router setup records exist'):command.downgrade(cfg,'049')
    with sqlite3.connect(file) as db:db.execute('UPDATE magic_connect_attempts SET router_public_key=NULL')
    command.downgrade(cfg,'049')
    with sqlite3.connect(file) as db:
     self.assertNotIn('router_public_key',{row[1] for row in db.execute('PRAGMA table_info(magic_connect_attempts)')})
     self.assertEqual(db.execute('SELECT id FROM magic_connect_attempts').fetchone(),('a',))
    command.upgrade(cfg,'head')

if __name__=='__main__':unittest.main()
