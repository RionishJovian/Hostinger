import time
import unittest

from backend.models import FinancialEvent, MagicHub, RouterDevice, RouterPlan, Site, SiteIncident, User
import test_backend
from backend.owner_api import redact_sensitive_keys


class OwnerOverviewTests(unittest.TestCase):
    setUp = test_backend.AccountPaymentTests.setUp
    tearDown = test_backend.AccountPaymentTests.tearDown
    login = test_backend.AccountPaymentTests.login

    def add_overview_data(self):
        now = int(time.time())
        with self.app.state.factory() as s:
            owner = s.get(User, self.users['owner'])
            other = s.get(User, self.users['other'])
            mine = Site(tenant_id=owner.tenant_id, name='Owner shop', timezone='Asia/Yangon', created=now)
            foreign = Site(tenant_id=other.tenant_id, name='Other shop', timezone='Asia/Yangon', created=now)
            s.add_all([mine, foreign])
            s.flush()
            mine_router = RouterDevice(tenant_id=owner.tenant_id, site_id=mine.id, name='Owner router', registered_by=owner.id, created=now)
            foreign_router = RouterDevice(tenant_id=other.tenant_id, site_id=foreign.id, name='Other router', registered_by=other.id, created=now)
            s.add_all([mine_router, foreign_router])
            s.flush()
            hub = MagicHub(name='Overview test hub', endpoint='overview.invalid', port=51999, pool='10.91.0.0/24', public_key='A' * 43 + '=', interface_name='wg-test', next_host=3, created=now)
            s.add(hub)
            s.flush()
            s.add(RouterPlan(tenant_id=owner.tenant_id, router_id=mine_router.id, hub_id=hub.id, router_public_key='B' * 43 + '=', address='10.91.0.2', snapshot={}, created=now, lifecycle_state='connected', handshake_verified_at=now, management_read_verified_at=now))
            s.add(SiteIncident(tenant_id=owner.tenant_id, site_id=mine.id, scope='gateway', status='open', started=now, detection_source='owner_report', symptoms='Offline', created_by=owner.id, created=now))
            s.add(SiteIncident(tenant_id=other.tenant_id, site_id=foreign.id, scope='gateway', status='open', started=now, detection_source='owner_report', symptoms='Foreign', created_by=other.id, created=now))
            s.add(FinancialEvent(tenant_id=owner.tenant_id, site_id=mine.id, source='voucher_sale', source_id='sale-owner', kind='collection', amount=7000, currency='MMK', service='internet', package_name='Day', method='Cash', reference='owner-ref', actor_id=owner.id, occurred_at=now, timestamp_basis='recorded_event'))
            s.add(FinancialEvent(tenant_id=other.tenant_id, site_id=foreign.id, source='voucher_sale', source_id='sale-other', kind='collection', amount=99000, currency='MMK', service='internet', package_name='Foreign', method='Cash', reference='other-ref', actor_id=other.id, occurred_at=now, timestamp_basis='recorded_event'))
            s.commit()
            return mine.id, mine_router.id

    def test_overview_is_authenticated_and_tenant_scoped(self):
        self.assertEqual(self.client.get('/v1/owner/overview').status_code, 401)
        site_id, router_id = self.add_overview_data()
        response = self.client.get('/v1/owner/overview', headers=self.login('owner'))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['shops'], [{'id': site_id, 'name': 'Owner shop'}])
        self.assertEqual(body['routers'], [{'id': router_id, 'name': 'Owner router', 'connected': True, 'last_seen': body['routers'][0]['last_seen']}])
        self.assertEqual(body['open_incidents'], 1)
        self.assertEqual(body['today_revenue'], {'amount': 7000, 'currency': 'MMK'})
        self.assertEqual(body['subscription_status'], 'active')
        self.assertNotIn('Other shop', response.text)
        self.assertNotIn('Other router', response.text)
        self.assertNotIn('99000', response.text)
        other = self.client.get('/v1/owner/overview', headers=self.login('other')).json()
        self.assertEqual([shop['name'] for shop in other['shops']], ['Other shop'])
        self.assertEqual([router['name'] for router in other['routers']], ['Other router'])


class OwnerOverviewRedactionTests(unittest.TestCase):
    def test_recursive_redaction_removes_sensitive_key_names(self):
        value = {'safe': [{'password': 'x', 'nested': {'wireguard_private_key': 'y', 'name': 'router'}}], 'apiCredentials': 'z', 'token_hash': 'q'}
        self.assertEqual(redact_sensitive_keys(value), {'safe': [{'nested': {'name': 'router'}}]})


if __name__ == '__main__':
    unittest.main()
