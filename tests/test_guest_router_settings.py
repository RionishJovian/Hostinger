"""Offline simulated RouterOS tests for guest Wi-Fi and addressing Safe Changes."""
import ipaddress
import os
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import test_backend as fixture
from backend.models import RouterChange, RouterEvidence, RouterPlan, User
from backend.routeros_adapter import RouterOSError


def key(n):
    return __import__('base64').b64encode(bytes([n]) * 32).decode()


class FakeGuestRouter:
    def __init__(self):
        self.wifi = {
            '*1': {
                '.id': '*1', 'name': 'wifi1', 'configuration.mode': 'station',
                'configuration.ssid': 'HomeUplink', 'security.authentication-types': 'wpa2-psk',
                'security.passphrase': 'home-secret',
            },
            '*2': {
                '.id': '*2', 'name': 'wifi2', 'configuration.mode': 'ap',
                'configuration.ssid': 'Magic Cafe', 'security.authentication-types': '',
                'security.passphrase': '',
            },
        }
        self.bridge_ports = [{'.id': '*B', 'interface': 'ether2', 'bridge': 'bridge'}]
        self.addresses = {
            '*A1': {'.id': '*A1', 'address': '10.5.50.1/24', 'interface': 'wifi2', 'network': '10.5.50.0'},
            '*A2': {'.id': '*A2', 'address': '192.168.88.1/24', 'interface': 'bridge', 'network': '192.168.88.0'},
            '*A3': {'.id': '*A3', 'address': '10.90.1.2/32', 'interface': 'mm-97546f1a', 'network': '10.90.1.2'},
        }
        self.pools = {'*C1': {'.id': '*C1', 'name': 'mm-lab-guest', 'ranges': '10.5.50.10-10.5.50.254'}}
        self.dhcp = {'*D1': {'.id': '*D1', 'name': 'mm-lab-guest', 'interface': 'wifi2', 'address-pool': 'mm-lab-guest'}}
        self.dhcp_net = {
            '*E1': {'.id': '*E1', 'address': '10.5.50.0/24', 'gateway': '10.5.50.1', 'dns-server': '10.5.50.1'},
        }
        self.hotspot = {'*F1': {'.id': '*F1', 'name': 'mm-lab-hotspot', 'interface': 'wifi2', 'profile': 'mm-lab-hsprof'}}
        self.profiles = {
            '*11': {'.id': '*11', 'name': 'mm-lab-hsprof', 'hotspot-address': '10.5.50.1', 'html-directory': 'hotspot'},
        }
        self.writes = []
        self.fail = None
        self.fail_after = None
        self._count = 0
        self.configs = {}
        self.securities = {}

    def client(self, credential=None):
        return FakeGuestClient(self)


class FakeGuestClient:
    def __init__(self, router):
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def export_configuration(self):
        if self.router.fail == 'backup':
            raise RouterOSError('backup_invalid', 'empty')
        return b'/export terse\n# guest lab'

    def get(self, path, optional=False):
        if self.router.fail == 'read':
            raise RouterOSError('unreachable', 'offline')
        table = {
            'interface/wifi': list(self.router.wifi.values()),
            'interface/wifi/configuration': list(self.router.configs.values()),
            'interface/wifi/security': list(self.router.securities.values()),
            'interface/bridge/port': list(self.router.bridge_ports),
            'ip/address': list(self.router.addresses.values()),
            'ip/pool': list(self.router.pools.values()),
            'ip/dhcp-server': list(self.router.dhcp.values()),
            'ip/dhcp-server/network': list(self.router.dhcp_net.values()),
            'ip/hotspot': list(self.router.hotspot.values()),
            'ip/hotspot/profile': list(self.router.profiles.values()),
        }
        if path in table:
            return [dict(x) for x in table[path]]
        if optional:
            return None
        raise AssertionError(path)

    def write(self, method, path, payload):
        self.router._count += 1
        if self.router.fail_after and self.router._count >= self.router.fail_after:
            raise RouterOSError('router_write_failed', 'simulated write failure')
        if self.router.fail == 'write':
            raise RouterOSError('router_write_failed', 'simulated')
        self.router.writes.append((method, path, dict(payload or {})))
        if method != 'PATCH':
            raise AssertionError((method, path))
        rid = path.rsplit('/', 1)[-1]
        if path.startswith('interface/wifi/') and path.count('/') == 2:
            self.router.wifi[rid].update(payload)
            return {}
        if path.startswith('interface/wifi/configuration/'):
            self.router.configs[rid].update(payload)
            return {}
        if path.startswith('interface/wifi/security/'):
            self.router.securities[rid].update(payload)
            return {}
        if path.startswith('ip/address/'):
            self.router.addresses[rid].update(payload)
            return {}
        if path.startswith('ip/pool/'):
            self.router.pools[rid].update(payload)
            return {}
        if path.startswith('ip/dhcp-server/network/'):
            self.router.dhcp_net[rid].update(payload)
            return {}
        if path.startswith('ip/hotspot/profile/'):
            self.router.profiles[rid].update(payload)
            return {}
        raise AssertionError((method, path))


class Store:
    def __init__(self, *a, **k):
        pass

    def save_verified(self, data):
        return ('encrypted://guest.bin', 'c' * 64)

    def remove(self, ref):
        pass


class GuestRouterSettingsTests(unittest.TestCase):
    setUp = fixture.AccountPaymentTests.setUp
    tearDown = fixture.AccountPaymentTests.tearDown
    login = fixture.AccountPaymentTests.login

    def enable_flag(self):
        self.app.state.router_settings_changes_enabled = True
        self.env = patch.dict(os.environ, {
            'MIKROMAGIC_BACKUP_KEY': Fernet.generate_key().decode(),
            'MIKROMAGIC_ROUTER_SETTINGS_CHANGES': 'true',
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def fixture(self):
        self.enable_flag()
        platform = self.login('platform')
        owner = self.login('owner')
        hub = self.client.post('/v1/hubs', headers=platform, json={
            'name': 'Guest Hub', 'endpoint': 'hub.example.com', 'pool': '10.90.30.0/24', 'public_key': key(1),
        }).json()['id']
        with self.app.state.factory() as s:
            tenant = s.get(User, self.users['owner']).tenant_id
        self.client.post('/v1/hubs/' + hub + '/assignments', headers=platform, json={'tenant_id': tenant})
        site = self.client.post('/v1/sites', headers=owner, json={'name': 'Guest Cafe'}).json()['id']
        router = self.client.post('/v1/routers', headers=owner, json={
            'site_id': site, 'name': 'hAP', 'model': 'hAP ax2', 'reported_routeros': '7.24.2',
        }).json()['id']
        now = int(time.time())
        with self.app.state.factory() as s:
            user = s.get(User, self.users['owner'])
            s.add(RouterEvidence(
                tenant_id=tenant, router_id=router, kind='preflight', observed_at=now,
                source='routeros_rest_live_read', created_by=user.id, created=now,
                payload={
                    'preflight_stage': 'post_connection',
                    'management_read': {'authenticated': True, 'identity_verified': True},
                    'compatibility': {'status': 'compatible_for_safe_change'},
                    'hotspot_portal_inventory': {
                        'servers': [{'.id': '*H1', 'name': 'mm-lab-hotspot', 'interface': 'wifi2', 'profile': 'mm-lab-hsprof'}],
                        'profiles': [{'name': 'mm-lab-hsprof', 'hotspot-address': '10.5.50.1'}],
                    },
                },
            ))
            s.commit()
        plan = self.client.post('/v1/routers/' + router + '/plan', headers=owner, json={
            'hub_id': hub, 'router_public_key': key(2),
        }).json()
        self.client.post('/v1/router-plans/' + plan['id'] + '/review', headers=owner, json={'confirmed_review': True})
        with self.app.state.factory() as s:
            current = s.get(RouterPlan, plan['id'])
            current.lifecycle_state = 'connected'
            current.handshake_verified_at = now
            current.management_read_verified_at = now
            s.query(RouterEvidence).filter_by(router_id=router).one().observed_at = now
            s.commit()
        fake = FakeGuestRouter()
        return owner, router, fake

    def harness(self, fake):
        return patch.multiple(
            'backend.safe_changes',
            load_routeros_safe_change_credential=lambda id: object(),
            RouterOSClient=fake.client,
            EncryptedBackupStore=Store,
        )

    def test_flag_off_refuses_guest_preview(self):
        owner, router, fake = self.fixture()
        self.app.state.router_settings_changes_enabled = False
        with self.harness(fake):
            r = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'Magic Open', 'security_mode': 'open',
            })
        self.assertEqual(r.status_code, 503, r.text)

    def test_guest_wifi_open_to_wpa_and_refuse_station(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            bad = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi1',
                'ssid': 'Nope', 'security_mode': 'open',
            })
        self.assertEqual(bad.status_code, 409, bad.text)
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'Magic Secure', 'security_mode': 'wpa2_wpa3_psk', 'passphrase': 'cafe-secret-99',
            })
        self.assertEqual(preview.status_code, 201, preview.text)
        body = preview.json()
        self.assertEqual(body['risk'], 'high')
        self.assertEqual(body['diff']['ssid'], {'before': 'Magic Cafe', 'after': 'Magic Secure'})
        self.assertEqual(body['diff']['security_mode'], {'before': 'open', 'after': 'wpa2_wpa3_psk'})
        self.assertNotIn('cafe-secret', preview.text.lower())
        self.assertNotIn('passphrase_ciphertext', preview.text)
        self.assertIn('rejoin', body['diff']['impact'].lower())
        with self.harness(fake):
            applied = self.client.post('/v1/router-changes/' + body['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()['status'], 'applied')
        self.assertEqual(fake.wifi['*2']['configuration.ssid'], 'Magic Secure')
        self.assertEqual(fake.wifi['*2']['security.authentication-types'], 'wpa2-psk,wpa3-psk')
        self.assertNotIn('cafe-secret', applied.text.lower())

    def test_guest_wifi_shared_profile_refused(self):
        owner, router, fake = self.fixture()
        fake.configs = {'*21': {'.id': '*21', 'name': 'shared-cfg', 'ssid': 'Shared'}}
        fake.wifi['*2'] = {
            '.id': '*2', 'name': 'wifi2', 'configuration': 'shared-cfg', 'configuration.mode': 'ap',
        }
        fake.wifi['*3'] = {
            '.id': '*3', 'name': 'wifi3', 'configuration': 'shared-cfg', 'configuration.mode': 'ap',
        }
        with self.harness(fake):
            r = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'New', 'security_mode': 'open',
            })
        self.assertEqual(r.status_code, 409, r.text)
        self.assertIn('shared', r.text.lower())

    def test_guest_wifi_rollback_on_mismatch(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'Temp Name', 'security_mode': 'open',
            }).json()
        original_apply = __import__('backend.guest_wifi_settings', fromlist=['apply_change']).apply_change

        def mismatch(client, before, desired):
            result = original_apply(client, before, desired)
            result['ssid'] = 'WRONG'
            return result

        with self.harness(fake), patch('backend.safe_changes.guest_wifi.apply_change', side_effect=mismatch):
            result = self.client.post('/v1/router-changes/' + preview['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.json()['status'], 'rolled_back')
        self.assertEqual(fake.wifi['*2']['configuration.ssid'], 'Magic Cafe')

    def test_guest_network_addressing_success_and_overlap_refuse(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            overlap = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_network_addressing', 'wifi_interface': 'wifi2',
                'network_cidr': '192.168.88.0/24', 'gateway': '192.168.88.1',
                'pool_start': '192.168.88.10', 'pool_end': '192.168.88.50',
            })
        self.assertEqual(overlap.status_code, 409, overlap.text)
        with self.harness(fake):
            hub = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_network_addressing', 'wifi_interface': 'wifi2',
                'network_cidr': '10.90.5.0/24', 'gateway': '10.90.5.1',
                'pool_start': '10.90.5.10', 'pool_end': '10.90.5.50',
            })
        self.assertEqual(hub.status_code, 409, hub.text)
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_network_addressing', 'wifi_interface': 'wifi2',
                'network_cidr': '10.5.60.0/24', 'gateway': '10.5.60.1',
                'pool_start': '10.5.60.10', 'pool_end': '10.5.60.200', 'dns': '10.5.60.1',
            })
        self.assertEqual(preview.status_code, 201, preview.text)
        body = preview.json()
        self.assertEqual(body['diff']['interface_address']['after'], '10.5.60.1/24')
        self.assertIn('lose their sessions', body['diff']['impact'])
        with self.harness(fake):
            applied = self.client.post('/v1/router-changes/' + body['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()['status'], 'applied')
        self.assertEqual(fake.addresses['*A1']['address'], '10.5.60.1/24')
        self.assertEqual(fake.pools['*C1']['ranges'], '10.5.60.10-10.5.60.200')
        self.assertEqual(fake.dhcp_net['*E1']['address'], '10.5.60.0/24')
        self.assertEqual(fake.profiles['*11']['hotspot-address'], '10.5.60.1')
        # LAN bridge untouched
        self.assertEqual(fake.addresses['*A2']['address'], '192.168.88.1/24')
        self.assertEqual(fake.addresses['*A3']['address'], '10.90.1.2/32')

    def test_guest_network_rollback_restores_all(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_network_addressing', 'wifi_interface': 'wifi2',
                'network_cidr': '10.5.70.0/24', 'gateway': '10.5.70.1',
                'pool_start': '10.5.70.20', 'pool_end': '10.5.70.100',
            }).json()
        original = __import__('backend.guest_network_addressing', fromlist=['apply_change']).apply_change

        def mismatch(client, before, desired):
            result = original(client, before, desired)
            result['address'] = '10.5.70.1/24'
            result['hotspot_address'] = '9.9.9.9'
            return result

        with self.harness(fake), patch('backend.safe_changes.guest_net.apply_change', side_effect=mismatch):
            result = self.client.post('/v1/router-changes/' + preview['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.json()['status'], 'rolled_back')
        self.assertEqual(fake.addresses['*A1']['address'], '10.5.50.1/24')
        self.assertEqual(fake.pools['*C1']['ranges'], '10.5.50.10-10.5.50.254')
        self.assertEqual(fake.dhcp_net['*E1']['gateway'], '10.5.50.1')
        self.assertEqual(fake.profiles['*11']['hotspot-address'], '10.5.50.1')

    def test_tenant_isolation_and_confirmation(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'X', 'security_mode': 'open',
            }).json()
            self.assertEqual(self.client.post('/v1/router-changes/' + preview['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': False,
            }).status_code, 422)
        other = self.login('other')
        with self.harness(fake):
            self.assertEqual(self.client.post('/v1/router-changes/' + preview['id'] + '/apply', headers=other, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            }).status_code, 404)

    def test_blocking_while_active_change(self):
        owner, router, fake = self.fixture()
        with self.app.state.factory() as s:
            user = s.get(User, self.users['owner'])
            tenant = user.tenant_id
            now = int(time.time())
            s.add(RouterChange(
                tenant_id=tenant, router_id=router, operation='wireguard_peer_keepalive',
                resource_id='*A', risk='high', status='recovery_required', revision=2,
                before={}, desired={}, actual={}, expected={}, diff={}, before_fingerprint='x',
                safety_backup_verified=True, rollback_attempted=True, created_by=user.id,
                created=now, updated=now,
            ))
            s.commit()
        with self.harness(fake):
            r = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_wifi_settings', 'wifi_interface': 'wifi2',
                'ssid': 'Blocked', 'security_mode': 'open',
            })
        self.assertEqual(r.status_code, 409)

    def test_prefix_and_public_network_validation(self):
        from backend.guest_network_addressing import validate_desired
        with self.assertRaises(RouterOSError):
            validate_desired(
                network_cidr='10.0.0.0/16', gateway='10.0.0.1',
                pool_start='10.0.0.10', pool_end='10.0.0.20', dns=None, protected=[],
            )
        with self.assertRaises(RouterOSError):
            validate_desired(
                network_cidr='8.8.8.0/24', gateway='8.8.8.1',
                pool_start='8.8.8.10', pool_end='8.8.8.20', dns=None, protected=[],
            )
        ok = validate_desired(
            network_cidr='10.5.50.0/24', gateway='10.5.50.1',
            pool_start='10.5.50.10', pool_end='10.5.50.50', dns=None,
            protected=[ipaddress.ip_network('192.168.88.0/24')],
        )
        self.assertEqual(ok['address'], '10.5.50.1/24')


if __name__ == '__main__':
    unittest.main()
