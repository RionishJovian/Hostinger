"""HotSpot session/accounting reads (step 6) against simulated RouterOS."""
import os
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy import select

import test_hubs
from backend.hotspot_accounting import FRESH_SECONDS, collect, observation_json, tenant_summary
from backend.hotspot_sync import USER_COMMENT
from backend.models import Entitlement, HotspotSessionObservation, MagicConnectEnrollment, RouterPlan, Voucher
from backend.routeros_adapter import RouterOSCredential, RouterOSError
from backend.vouchers import voucher_json


class FakeAccountingRouter:
    """List-all HotSpot active/users stand-in for monitoring reads."""

    def __init__(self):
        self.users = {}
        self.active = []
        self.fail = None
        self.next = 1

    def client(self, credential):
        return FakeAccountingClient(self)

    def add_user(self, name, *, comment=None, bytes_in=0, bytes_out=0, uptime='0s'):
        resource = f'*{self.next:X}'
        self.next += 1
        self.users[resource] = {
            '.id': resource,
            'name': name,
            'comment': comment if comment is not None else USER_COMMENT,
            'disabled': 'false',
            'bytes-in': str(bytes_in),
            'bytes-out': str(bytes_out),
            'uptime': uptime,
        }
        return resource

    def add_active(self, user, *, mac='AA:BB:CC:DD:EE:01', address='10.5.50.10', uptime='5m', bytes_in=1000, bytes_out=2000):
        resource = f'*S{self.next:X}'
        self.next += 1
        self.active.append({
            '.id': resource,
            'user': user,
            'mac-address': mac,
            'address': address,
            'server': 'hs-main',
            'uptime': uptime,
            'bytes-in': str(bytes_in),
            'bytes-out': str(bytes_out),
        })


class FakeAccountingClient:
    def __init__(self, router):
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, path, optional=False):
        if self.router.fail:
            raise RouterOSError(self.router.fail, 'simulated')
        menu, _, query = path.partition('?')
        if menu == 'ip/hotspot/user':
            rows = [dict(item) for item in self.router.users.values()]
        elif menu == 'ip/hotspot/active':
            rows = [dict(item) for item in self.router.active]
        else:
            raise AssertionError(path)
        if not query:
            return rows
        key, _, value = query.partition('=')
        return [item for item in rows if item.get(key) == value]


class HotspotAccountingTests(unittest.TestCase):
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
            p.handshake_verified_at = now
            p.management_read_verified_at = now
            s.add(MagicConnectEnrollment(
                plan_id=plan, attempt_id=attempt, tenant_id=p.tenant_id, site_id=site,
                owner_id=self.users['owner'], created=now, management_identities_at=now,
            ))
            s.commit()
        return router

    def package(self, owner, **policy):
        body = {'name': 'Day pass', 'service': 'internet', 'mode': 'both', 'price': 1000, 'gb': 2, 'hours': 24, 'devices': 2, 'speed': 10} | policy
        r = self.client.post('/v1/packages', headers=owner, json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()['id']

    def issue(self, owner, package, site, key):
        r = self.client.post('/v1/vouchers', headers=owner, json={'site_id': site, 'package_id': package, 'request_key': key.ljust(16, 'x')})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def publish(self, owner, site):
        cfg = self.client.get(f'/v1/sites/{site}/portal', headers=owner).json()['draft']
        cfg.update(
            direct_purchase=True, voucher_login=True, payment_destination='Counter',
            payment_instructions='Test', payment_methods=['Cash'],
        )
        self.assertEqual(self.client.post(f'/v1/sites/{site}/portal/draft', headers=owner, json={'expected_revision': 0, 'settings': cfg}).status_code, 200)
        self.assertEqual(self.client.post(f'/v1/sites/{site}/portal/publish', headers=owner, json={'expected_revision': 1}).status_code, 200)

    def redeem(self, guest, site, code):
        r = self.client.post('/v1/vouchers/redeem', headers=guest, json={'site_id': site, 'code': code})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def fixture(self):
        self.env = patch.dict(os.environ, {'MIKROMAGIC_BACKUP_KEY': Fernet.generate_key().decode()})
        self.env.start()
        self.addCleanup(self.env.stop)
        _, owner, hub, site, _ = self.setup_hub()
        self.publish(owner, site)
        return owner, hub, site

    def collect(self, router, fake, now=None):
        credential = RouterOSCredential('https://10.90.1.2', 'mm-monitor-x', 'x')
        with patch('backend.hotspot_accounting.load_routeros_monitoring_credential', return_value=credential):
            with self.app.state.factory() as s:
                result = collect(s, router, fake.client, now=now)
                s.commit()
                return result

    def test_collect_activates_usage_and_counts_only_mikromagic_guests(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        guest = self.login('guest')
        first = self.issue(owner, package, site, 'acct-a')
        second = self.issue(owner, package, site, 'acct-b')
        self.redeem(guest, site, first['code'])
        self.redeem(self.login('guest2'), site, second['code'])
        fake = FakeAccountingRouter()
        fake.add_user(first['code'], bytes_in=1_000_000, bytes_out=2_000_000, uptime='10m')
        fake.add_user(second['code'], comment=USER_COMMENT + '|exp=jan/01/2027 00:00:00', bytes_in=500, bytes_out=500)
        fake.add_user('foreign-user', comment='Owner account', bytes_in=9_999_999, bytes_out=9_999_999)
        fake.add_active(first['code'], bytes_in=100, bytes_out=200)
        fake.add_active('foreign-user', mac='FF:FF:FF:FF:FF:FF')
        now = int(time.time())
        result = self.collect(router, fake, now=now)
        self.assertTrue(result['collected'])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['freshness'], 'fresh')
        self.assertEqual(result['active_count'], 1)
        self.assertEqual(result['activations_applied'], 2)
        self.assertGreaterEqual(result['usage_updated'], 1)
        self.assertEqual(len(result['active_guests']), 1)
        self.assertEqual(result['active_guests'][0]['code_hint'], first['code_hint'])
        self.assertNotIn(first['code'], str(result))
        with self.app.state.factory() as s:
            e1 = s.scalar(select(Entitlement).where(Entitlement.voucher_id == first['id']))
            e2 = s.scalar(select(Entitlement).where(Entitlement.voucher_id == second['id']))
            self.assertEqual(e1.activated, now)
            self.assertEqual(e2.activated, now)
            self.assertEqual(e1.used_bytes, 3_000_000)
            self.assertEqual(e2.used_bytes, 1_000)

    def test_stale_and_unreachable_reads_are_unable_to_verify(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        voucher = self.issue(owner, package, site, 'stale-a')
        self.redeem(self.login('guest'), site, voucher['code'])
        fake = FakeAccountingRouter()
        fake.add_user(voucher['code'], bytes_in=100, bytes_out=100)
        fake.add_active(voucher['code'])
        fresh_at = int(time.time()) - 10
        self.assertEqual(self.collect(router, fake, now=fresh_at)['status'], 'verified')
        with self.app.state.factory() as s:
            stale = observation_json(s.get(HotspotSessionObservation, router), now=fresh_at + FRESH_SECONDS + 1)
        self.assertEqual(stale['status'], 'unable_to_verify')
        self.assertEqual(stale['freshness'], 'stale')
        self.assertIsNone(stale['active_count'])
        self.assertEqual(stale['active_guests'], [])
        fake.fail = 'unreachable'
        failed = self.collect(router, fake, now=fresh_at + 20)
        self.assertFalse(failed['collected'])
        self.assertEqual(failed['aborted'], 'unreachable')
        self.assertEqual(failed['status'], 'unable_to_verify')
        self.assertIsNone(failed['active_count'])
        with self.app.state.factory() as s:
            summary = tenant_summary(s, s.get(HotspotSessionObservation, router).tenant_id, now=fresh_at + FRESH_SECONDS + 5)
        self.assertEqual(summary['status'], 'unable_to_verify')
        self.assertIsNone(summary['active_count'])

    def test_endpoints_require_managed_router_and_use_monitoring_path(self):
        owner, hub, site = self.fixture()
        plain = self.router(owner, site, 'Unmanaged')
        self.assertEqual(self.client.post(f'/v1/routers/{plain}/hotspot-sessions/collect', headers=owner).json()['detail']['code'], 'router_not_managed')
        self.assertFalse(self.client.get(f'/v1/routers/{plain}/hotspot-sessions', headers=owner).json()['managed'])
        router = self.managed(owner, hub, site, 3, 'Managed')
        package = self.package(owner)
        voucher = self.issue(owner, package, site, 'api-a')
        self.redeem(self.login('guest'), site, voucher['code'])
        fake = FakeAccountingRouter()
        fake.add_user(voucher['code'], bytes_in=50, bytes_out=50)
        fake.add_active(voucher['code'])
        self.app.state.hotspot_accounting_client_factory = fake.client
        with patch('backend.hotspot_accounting.load_routeros_monitoring_credential', return_value=RouterOSCredential('https://10.90.1.3', 'mm-monitor-x', 'x')):
            done = self.client.post(f'/v1/routers/{router}/hotspot-sessions/collect', headers=owner)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()['active_count'], 1)
        status = self.client.get(f'/v1/routers/{router}/hotspot-sessions', headers=owner).json()
        self.assertEqual(status['status'], 'verified')
        summary = self.client.get('/v1/hotspot-sessions/summary', headers=owner).json()
        self.assertEqual(summary['status'], 'verified')
        self.assertEqual(summary['active_count'], 1)
        self.assertEqual(self.client.post(f'/v1/routers/{router}/hotspot-sessions/collect', headers=self.login('other')).status_code, 404)
        self.assertEqual(self.client.get('/v1/hotspot-sessions/summary', headers=self.login('guest')).status_code, 403)

    def test_guest_diagnosis_matches_fresh_observation_without_inventing_live_zero(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        voucher = self.issue(owner, package, site, 'diag-a')
        guest = self.login('guest')
        self.redeem(guest, site, voucher['code'])
        before = self.client.get('/v1/my-access/diagnosis', headers=guest).json()['network_evidence']
        self.assertEqual(before['status'], 'unavailable')
        fake = FakeAccountingRouter()
        fake.add_user(voucher['code'])
        fake.add_active(voucher['code'])
        self.collect(router, fake)
        evidence = self.client.get('/v1/my-access/diagnosis', headers=guest).json()['network_evidence']
        self.assertEqual(evidence['status'], 'verified')
        self.assertEqual(evidence['active_for_guest'], 1)
        with self.app.state.factory() as s:
            row = s.get(HotspotSessionObservation, router)
            row.observed_at = int(time.time()) - FRESH_SECONDS - 10
            s.commit()
        stale = self.client.get('/v1/my-access/diagnosis', headers=guest).json()['network_evidence']
        self.assertEqual(stale['status'], 'unable_to_verify')

    def test_router_only_login_activates_voucher_without_entitlement(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner, clock='connected')
        voucher = self.issue(owner, package, site, 'router-only-a')
        self.assertEqual(voucher['status'], 'unused')
        self.assertIsNone(voucher.get('activated'))
        fake = FakeAccountingRouter()
        fake.add_user(voucher['code'], bytes_in=4000, bytes_out=6000, uptime='12m')
        fake.add_active(voucher['code'], bytes_in=10, bytes_out=20)
        now = int(time.time())
        result = self.collect(router, fake, now=now)
        self.assertTrue(result['collected'])
        self.assertEqual(result['activations_applied'], 1)
        self.assertGreaterEqual(result['usage_updated'], 1)
        self.assertEqual(result['active_count'], 1)
        with self.app.state.factory() as s:
            row = s.get(Voucher, voucher['id'])
            self.assertIsNone(s.scalar(select(Entitlement).where(Entitlement.voucher_id == voucher['id'])))
            self.assertEqual(row.activated, now)
            self.assertEqual(row.used_bytes, 10_000)
            self.assertEqual(row.connected_seconds, 720)
            payload = voucher_json(row)
        self.assertEqual(payload['status'], 'active')
        self.assertEqual(payload['activated'], now)
        self.assertEqual(payload['used_bytes'], 10_000)
        listed = {item['id']: item for item in self.client.get('/v1/vouchers', headers=owner).json()}
        self.assertEqual(listed[voucher['id']]['status'], 'active')
        self.assertEqual(listed[voucher['id']]['activated'], now)
        self.assertEqual(listed[voucher['id']]['used_bytes'], 10_000)

    def test_router_only_usage_is_monotonic_and_exp_marker_activates(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        active = self.issue(owner, package, site, 'router-mono-a')
        idle = self.issue(owner, package, site, 'router-mono-b')
        fake = FakeAccountingRouter()
        fake.add_user(active['code'], bytes_in=1000, bytes_out=1000, uptime='1m')
        fake.add_active(active['code'])
        fake.add_user(
            idle['code'],
            comment=USER_COMMENT + '|exp=jan/01/2027 00:00:00',
            bytes_in=250,
            bytes_out=250,
        )
        first_at = int(time.time())
        first = self.collect(router, fake, now=first_at)
        self.assertEqual(first['activations_applied'], 2)
        fake.users = {}
        fake.active = []
        fake.next = 1
        fake.add_user(active['code'], bytes_in=500, bytes_out=500, uptime='2m')
        fake.add_active(active['code'])
        fake.add_user(
            idle['code'],
            comment=USER_COMMENT + '|exp=jan/01/2027 00:00:00',
            bytes_in=100,
            bytes_out=100,
        )
        second = self.collect(router, fake, now=first_at + 30)
        self.assertEqual(second['activations_applied'], 0)
        with self.app.state.factory() as s:
            a = s.get(Voucher, active['id'])
            b = s.get(Voucher, idle['id'])
            self.assertEqual(a.activated, first_at)
            self.assertEqual(b.activated, first_at)
            self.assertEqual(a.used_bytes, 2000)
            self.assertEqual(b.used_bytes, 500)

    def test_foreign_session_and_other_tenant_are_ignored(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        owned = self.issue(owner, package, site, 'router-iso-a')
        other = self.login('other')
        other_site = self.client.post('/v1/sites', headers=other, json={'name': 'Other cafe'}).json()['id']
        other_pkg = self.client.post(
            '/v1/packages', headers=other,
            json={'name': 'Other day', 'service': 'internet', 'mode': 'both', 'price': 1000, 'gb': 2, 'hours': 24, 'devices': 1, 'speed': 10},
        ).json()['id']
        foreign = self.client.post(
            '/v1/vouchers', headers=other,
            json={'site_id': other_site, 'package_id': other_pkg, 'request_key': 'router-iso-other01'},
        ).json()
        fake = FakeAccountingRouter()
        fake.add_user(owned['code'], bytes_in=100, bytes_out=100)
        fake.add_active(owned['code'])
        fake.add_user('foreign-user', comment='Owner account', bytes_in=9_999_999, bytes_out=9_999_999)
        fake.add_active('foreign-user')
        fake.add_user(foreign['code'], bytes_in=8_000_000, bytes_out=8_000_000)
        fake.add_active(foreign['code'])
        now = int(time.time())
        result = self.collect(router, fake, now=now)
        self.assertEqual(result['active_count'], 1)
        self.assertEqual(result['activations_applied'], 1)
        self.assertEqual(result['active_guests'][0]['code_hint'], owned['code_hint'])
        with self.app.state.factory() as s:
            self.assertEqual(s.get(Voucher, owned['id']).activated, now)
            other_row = s.get(Voucher, foreign['id'])
            self.assertIsNone(other_row.activated)
            self.assertEqual(other_row.used_bytes, 0)

    def test_app_redeemed_voucher_stays_on_entitlement_not_voucher_fields(self):
        owner, hub, site = self.fixture()
        router = self.managed(owner, hub, site)
        package = self.package(owner)
        voucher = self.issue(owner, package, site, 'router-app-a')
        self.redeem(self.login('guest'), site, voucher['code'])
        fake = FakeAccountingRouter()
        fake.add_user(voucher['code'], bytes_in=111, bytes_out=222, uptime='3m')
        fake.add_active(voucher['code'])
        now = int(time.time())
        result = self.collect(router, fake, now=now)
        self.assertEqual(result['activations_applied'], 1)
        with self.app.state.factory() as s:
            row = s.get(Voucher, voucher['id'])
            entitlement = s.scalar(select(Entitlement).where(Entitlement.voucher_id == voucher['id']))
            self.assertIsNone(row.activated)
            self.assertEqual(row.used_bytes, 0)
            self.assertEqual(entitlement.activated, now)
            self.assertEqual(entitlement.used_bytes, 333)
            self.assertEqual(voucher_json(row)['status'], 'redeemed')


if __name__ == '__main__':
    unittest.main()
