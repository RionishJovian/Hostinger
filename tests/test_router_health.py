"""Router health monitoring reads against simulated RouterOS."""
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import test_hubs
from backend.models import MagicConnectEnrollment, RouterHealthObservation, RouterPlan
from backend.routeros_adapter import RouterOSCredential, RouterOSError
from backend.router_health import FRESH_SECONDS, observation_json


class FakeHealthRouter:
    def __init__(self):
        self.fail = None
        self.resource = {
            'cpu-load': '12', 'cpu-count': '4', 'total-memory': '268435456', 'free-memory': '134217728',
            'free-hdd-space': '104857600', 'total-hdd-space': '209715200', 'uptime': '1h2m3s',
            'board-name': 'hAP ax2', 'version': '7.24.2', 'architecture-name': 'arm64',
        }
        self.health = [{'name': 'temperature', 'value': '41'}]
        self.dhcp = [{'.id': '*1', 'name': 'dhcp1', 'interface': 'bridge'}]
        self.leases = [{'.id': '*1', 'address': '10.5.50.10', 'status': 'bound', 'server': 'dhcp1'}]

    def client(self, credential, router_id=None, **kwargs):
        return FakeHealthClient(self)


class FakeHealthClient:
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
        if menu == 'system/resource':
            return dict(self.router.resource)
        if menu == 'system/health':
            return list(self.router.health) if self.router.health is not None else None
        if menu == 'ip/dhcp-server':
            return list(self.router.dhcp)
        if menu == 'ip/dhcp-server/lease':
            return list(self.router.leases)
        if optional:
            return None
        raise AssertionError(path)


class RouterHealthTests(unittest.TestCase):
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

    def test_collect_requires_managed_router_and_stores_verified_metrics(self):
        _, owner, hub, site, _ = self.setup_hub()
        plain = self.router(owner, site, 'Plain')
        self.assertEqual(self.client.post(f'/v1/routers/{plain}/health/collect', headers=owner).json()['detail']['code'], 'router_not_managed')
        self.assertFalse(self.client.get(f'/v1/routers/{plain}/health', headers=owner).json()['managed'])
        router = self.managed(owner, hub, site)
        before = self.client.get(f'/v1/routers/{router}/health', headers=owner).json()
        self.assertTrue(before['managed'])
        self.assertEqual(before['status'], 'unable_to_verify')
        self.assertIsNone(before['metrics'])
        fake = FakeHealthRouter()
        self.app.state.router_health_client_factory = fake.client
        with patch('backend.router_health.load_routeros_monitoring_credential', return_value=RouterOSCredential(
                 base_url='https://10.90.1.2', username='mm-monitor-xxxxxxxx', password='x', verify=False,
             )):
            done = self.client.post(f'/v1/routers/{router}/health/collect', headers=owner)
            self.assertEqual(done.status_code, 200, done.text)
            body = done.json()
            self.assertTrue(body['collected'])
            self.assertEqual(body['status'], 'verified')
            self.assertEqual(body['metrics']['cpu_load_percent'], 12)
            self.assertEqual(body['metrics']['temperature_c'], 41.0)
            self.assertEqual(body['metrics']['dhcp_server_count'], 1)
            self.assertEqual(body['metrics']['dhcp_lease_count'], 1)
        status = self.client.get(f'/v1/routers/{router}/health', headers=owner).json()
        self.assertEqual(status['status'], 'verified')
        self.assertEqual(status['metrics']['board_name'], 'hAP ax2')

    def test_unreachable_and_stale_are_unable_to_verify(self):
        _, owner, hub, site, _ = self.setup_hub()
        router = self.managed(owner, hub, site)
        fake = FakeHealthRouter()
        self.app.state.router_health_client_factory = fake.client
        with patch('backend.router_health.load_routeros_monitoring_credential', return_value=RouterOSCredential(
                 base_url='https://10.90.1.2', username='mm-monitor-xxxxxxxx', password='x', verify=False,
             )):
            self.assertTrue(self.client.post(f'/v1/routers/{router}/health/collect', headers=owner).json()['collected'])
            fake.fail = 'unreachable'
            failed = self.client.post(f'/v1/routers/{router}/health/collect', headers=owner).json()
            self.assertFalse(failed['collected'])
            self.assertEqual(failed['status'], 'unable_to_verify')
            self.assertIsNone(failed['metrics'])
            self.assertEqual(failed['aborted'], 'unreachable')
        with self.app.state.factory() as s:
            row = s.get(RouterHealthObservation, router)
            row.observed_at = int(time.time()) - (FRESH_SECONDS + 30)
            s.commit()
        stale = self.client.get(f'/v1/routers/{router}/health', headers=owner).json()
        self.assertEqual(stale['status'], 'unable_to_verify')
        self.assertEqual(stale['freshness'], 'stale')
        self.assertIsNone(stale['metrics'])
        self.assertIsNone(observation_json(None)['metrics'])


if __name__ == '__main__':
    unittest.main()
