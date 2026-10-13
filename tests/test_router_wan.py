"""Router WAN / PPPoE monitoring reads against simulated RouterOS."""
import time
import unittest
from unittest.mock import patch

import test_hubs
from backend.models import MagicConnectEnrollment, RouterPlan, RouterWanObservation
from backend.routeros_adapter import RouterOSCredential, RouterOSError
from backend.router_wan import FRESH_SECONDS, observation_json


class FakeWanRouter:
    def __init__(self):
        self.fail = None
        self.interfaces = [
            {'.id': '*1', 'name': 'ether1', 'type': 'ether', 'running': 'true'},
            {'.id': '*2', 'name': 'pppoe-out1', 'type': 'pppoe-out', 'running': 'true'},
        ]
        self.dhcp = [{
            '.id': '*1', 'interface': 'ether1', 'disabled': 'false',
            'status': 'bound', 'address': '203.0.113.10/24', 'gateway': '203.0.113.1',
        }]
        self.pppoe = [{
            '.id': '*1', 'name': 'pppoe-out1', 'interface': 'ether1', 'disabled': 'false',
            'running': 'true', 'user': 'shop@isp', 'service': 'isp',
        }]
        self.routes = [
            {'.id': '*1', 'dst-address': '0.0.0.0/0', 'gateway': '203.0.113.1', 'active': 'true', 'disabled': 'false', 'distance': '1'},
            {'.id': '*2', 'dst-address': '10.0.0.0/8', 'gateway': '10.0.0.1', 'active': 'true', 'disabled': 'false'},
        ]

    def client(self, credential, router_id=None, **kwargs):
        return FakeWanClient(self)


class FakeWanClient:
    def __init__(self, router):
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, path, optional=False):
        if self.router.fail:
            raise RouterOSError(self.router.fail, 'simulated')
        menu, _, _query = path.partition('?')
        if menu == 'interface':
            return list(self.router.interfaces)
        if menu == 'ip/dhcp-client':
            return list(self.router.dhcp)
        if menu == 'interface/pppoe-client':
            return list(self.router.pppoe)
        if menu == 'ip/route':
            return list(self.router.routes)
        if optional:
            return None
        raise AssertionError(path)


class RouterWanTests(unittest.TestCase):
    H = test_hubs.HubTests
    setUp = H.setUp
    tearDown = H.tearDown
    login = H.login
    setup_hub = H.setup_hub
    router = H.router
    plan = H.plan

    def managed(self, owner, hub, site, n=2, name='Gateway'):
        router = self.router(owner, site, name)
        plan = self.plan(owner, hub, router, n).json()['id']
        attempt = self.client.post(f'/v1/sites/{site}/magic-connect/attempts', headers=owner, json={'router_name': name}).json()['id']
        with self.app.state.factory() as s:
            p = s.get(RouterPlan, plan)
            now = int(time.time())
            p.lifecycle_state = 'connected'
            p.handshake_verified_at = now - 30
            p.management_read_verified_at = now - 20
            s.add(MagicConnectEnrollment(
                plan_id=plan, attempt_id=attempt, tenant_id=p.tenant_id, site_id=site,
                owner_id=self.users['owner'], created=now - 40, management_identities_at=now - 25,
            ))
            s.commit()
        return router

    def test_collect_requires_managed_router_and_stores_verified_wan(self):
        _, owner, hub, site, _ = self.setup_hub()
        plain = self.router(owner, site, 'Plain')
        self.assertEqual(self.client.post(f'/v1/routers/{plain}/wan/collect', headers=owner).json()['detail']['code'], 'router_not_managed')
        self.assertFalse(self.client.get(f'/v1/routers/{plain}/wan', headers=owner).json()['managed'])
        router = self.managed(owner, hub, site)
        before = self.client.get(f'/v1/routers/{router}/wan', headers=owner).json()
        self.assertTrue(before['managed'])
        self.assertEqual(before['status'], 'unable_to_verify')
        self.assertIsNone(before['metrics'])
        fake = FakeWanRouter()
        self.app.state.router_wan_client_factory = fake.client
        with patch('backend.router_wan.load_routeros_monitoring_credential', return_value=RouterOSCredential(
                 base_url='https://10.90.1.2', username='mm-monitor-xxxxxxxx', password='x', verify=False,
             )):
            done = self.client.post(f'/v1/routers/{router}/wan/collect', headers=owner)
            self.assertEqual(done.status_code, 200, done.text)
            body = done.json()
            self.assertTrue(body['collected'])
            self.assertEqual(body['status'], 'verified')
            self.assertEqual(body['metrics']['dhcp_client_count'], 1)
            self.assertEqual(body['metrics']['pppoe_client_count'], 1)
            self.assertEqual(body['metrics']['active_default_route_count'], 1)
            self.assertEqual(body['metrics']['dhcp_clients'][0]['address'], '203.0.113.10/24')
            self.assertEqual(body['metrics']['pppoe_clients'][0]['user'], 'shop@isp')
        status = self.client.get(f'/v1/routers/{router}/wan', headers=owner).json()
        self.assertEqual(status['status'], 'verified')
        self.assertEqual(status['metrics']['default_route_count'], 1)

    def test_unreachable_and_stale_are_unable_to_verify(self):
        _, owner, hub, site, _ = self.setup_hub()
        router = self.managed(owner, hub, site)
        fake = FakeWanRouter()
        self.app.state.router_wan_client_factory = fake.client
        with patch('backend.router_wan.load_routeros_monitoring_credential', return_value=RouterOSCredential(
                 base_url='https://10.90.1.2', username='mm-monitor-xxxxxxxx', password='x', verify=False,
             )):
            self.assertTrue(self.client.post(f'/v1/routers/{router}/wan/collect', headers=owner).json()['collected'])
            fake.fail = 'unreachable'
            failed = self.client.post(f'/v1/routers/{router}/wan/collect', headers=owner).json()
            self.assertFalse(failed['collected'])
            self.assertEqual(failed['status'], 'unable_to_verify')
            self.assertIsNone(failed['metrics'])
            self.assertEqual(failed['aborted'], 'unreachable')
        with self.app.state.factory() as s:
            row = s.get(RouterWanObservation, router)
            row.observed_at = int(time.time()) - (FRESH_SECONDS + 30)
            s.commit()
        stale = self.client.get(f'/v1/routers/{router}/wan', headers=owner).json()
        self.assertEqual(stale['status'], 'unable_to_verify')
        self.assertEqual(stale['freshness'], 'stale')
        self.assertIsNone(stale['metrics'])
        self.assertIsNone(observation_json(None)['metrics'])


if __name__ == '__main__':
    unittest.main()
