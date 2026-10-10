import time
import unittest

from sqlalchemy import select

import test_backend as fixture
from backend.models import Entitlement


class AccessDiagnosisTests(unittest.TestCase):
    setUp = fixture.AccountPaymentTests.setUp
    tearDown = fixture.AccountPaymentTests.tearDown
    login = fixture.AccountPaymentTests.login
    package = fixture.AccountPaymentTests.package
    order = fixture.AccountPaymentTests.order

    def test_guest_sees_only_owned_order_diagnosis(self):
        owner = self.login('owner')
        guest = self.login('guest')
        other_guest = self.login('guest2')
        package = self.package(owner)
        order = self.order(guest, package).json()
        result = self.client.get('/v1/my-access/diagnosis', headers=guest)
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body['network_evidence']['status'], 'unavailable')
        self.assertEqual(body['network_evidence']['freshness'], 'none')
        self.assertEqual(body['items'][0]['id'], order['id'])
        self.assertEqual(body['items'][0]['state'], 'awaiting_review')
        self.assertEqual(self.client.get('/v1/my-access/diagnosis', headers=other_guest).json()['items'], [])
        self.assertEqual(self.client.get('/v1/my-access/diagnosis', headers=owner).status_code, 403)

    def test_approved_pass_is_not_claimed_live_and_exhaustion_is_local_only(self):
        owner = self.login('owner')
        guest = self.login('guest')
        package = self.package(owner)
        order = self.order(guest, package).json()
        self.client.post('/v1/orders/' + order['id'] + '/decision', headers=owner, json={'decision': 'approved'})
        first = self.client.get('/v1/my-access/diagnosis', headers=guest).json()['items'][0]
        self.assertEqual(first['state'], 'provisioning_pending')
        self.assertEqual(first['quota']['source'], 'mikromagic_record_not_router_verified')
        self.assertNotIn('code_hash', str(first))
        with self.app.state.factory() as session:
            entitlement = session.scalar(select(Entitlement).where(Entitlement.order_id == order['id']))
            entitlement.activated = int(time.time()) - 60
            entitlement.used_bytes = 5_000_000_000
            session.commit()
        exhausted = self.client.get('/v1/my-access/diagnosis', headers=guest).json()['items'][0]
        self.assertEqual(exhausted['state'], 'quota_exhausted')
        self.assertEqual(exhausted['quota']['data']['remaining_bytes'], 0)
        self.assertEqual(exhausted['quota']['observed_at'], None)


if __name__ == '__main__':
    unittest.main()
