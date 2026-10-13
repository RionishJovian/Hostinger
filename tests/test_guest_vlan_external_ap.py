"""Offline simulated RouterOS tests for guest VLAN external-AP Safe Change."""
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


class FakeVlanRouter:
    def __init__(self):
        self.next = 100
        self.interfaces = {
            'ether1': {'.id': '*E1', 'name': 'ether1', 'type': 'ether'},
            'ether2': {'.id': '*E2', 'name': 'ether2', 'type': 'ether'},
            'ether3': {'.id': '*E3', 'name': 'ether3', 'type': 'ether'},
            'wifi1': {'.id': '*W1', 'name': 'wifi1', 'type': 'wlan'},
            'wifi2': {'.id': '*W2', 'name': 'wifi2', 'type': 'wlan'},
            'bridge': {'.id': '*BR', 'name': 'bridge', 'type': 'bridge'},
            'mm-97546f1a': {'.id': '*WG', 'name': 'mm-97546f1a', 'type': 'wireguard'},
        }
        self.wifi = {
            '*1': {
                '.id': '*1', 'name': 'wifi1', 'configuration.mode': 'station',
                'configuration.ssid': 'HomeUplink', 'security.authentication-types': 'wpa2-psk',
            },
            '*2': {
                '.id': '*2', 'name': 'wifi2', 'configuration.mode': 'ap',
                'configuration.ssid': 'Magic Cafe', 'security.authentication-types': '',
            },
        }
        self.bridges = {'*BR': {'.id': '*BR', 'name': 'bridge'}}
        self.bridge_ports = [{'.id': '*BP2', 'interface': 'ether2', 'bridge': 'bridge'}]
        self.vlans = {}
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
        self.dhcp_clients = {
            '*DC1': {'.id': '*DC1', 'interface': 'ether1', 'disabled': 'false'},
        }
        self.pppoe = {}
        self.hotspot = {'*F1': {'.id': '*F1', 'name': 'mm-lab-hotspot', 'interface': 'wifi2', 'profile': 'mm-lab-hsprof'}}
        self.profiles = {
            '*11': {'.id': '*11', 'name': 'mm-lab-hsprof', 'hotspot-address': '10.5.50.1', 'html-directory': 'hotspot'},
        }
        self.writes = []
        self.fail = None
        self.fail_after = None
        self._count = 0

    def _id(self):
        self.next += 1
        return f'*{self.next}'

    def client(self, credential=None, router_id=None, **kwargs):
        return FakeVlanClient(self)


class FakeVlanClient:
    def __init__(self, router):
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def export_configuration(self):
        if self.router.fail == 'backup':
            raise RouterOSError('backup_invalid', 'empty')
        return b'/export terse\n# guest vlan lab'

    def get(self, path, optional=False):
        if self.router.fail == 'read':
            raise RouterOSError('unreachable', 'offline')
        table = {
            'interface': list(self.router.interfaces.values()),
            'interface/wifi': list(self.router.wifi.values()),
            'interface/bridge': list(self.router.bridges.values()),
            'interface/bridge/port': list(self.router.bridge_ports),
            'interface/vlan': list(self.router.vlans.values()),
            'interface/pppoe-client': list(self.router.pppoe.values()),
            'ip/address': list(self.router.addresses.values()),
            'ip/pool': list(self.router.pools.values()),
            'ip/dhcp-server': list(self.router.dhcp.values()),
            'ip/dhcp-server/network': list(self.router.dhcp_net.values()),
            'ip/dhcp-client': list(self.router.dhcp_clients.values()),
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
        self.router.writes.append((method, path, dict(payload) if payload else None))
        if method == 'PUT':
            rid = self.router._id()
            row = {'.id': rid, **dict(payload or {})}
            if path == 'interface/vlan':
                self.router.vlans[rid] = row
                self.router.interfaces[row['name']] = {
                    '.id': rid, 'name': row['name'], 'type': 'vlan',
                }
                return dict(row)
            if path == 'interface/bridge':
                self.router.bridges[rid] = row
                self.router.interfaces[row['name']] = {
                    '.id': rid, 'name': row['name'], 'type': 'bridge',
                }
                return dict(row)
            if path == 'interface/bridge/port':
                self.router.bridge_ports.append(row)
                return dict(row)
            raise AssertionError((method, path))
        if method == 'PATCH':
            rid = path.rsplit('/', 1)[-1]
            if path.startswith('ip/address/'):
                self.router.addresses[rid].update(payload)
                return {}
            if path.startswith('ip/dhcp-server/') and '/network/' not in path:
                self.router.dhcp[rid].update(payload)
                return {}
            if path.startswith('ip/hotspot/') and '/profile/' not in path:
                self.router.hotspot[rid].update(payload)
                return {}
            if path.startswith('interface/vlan/'):
                self.router.vlans[rid].update(payload)
                return {}
            raise AssertionError((method, path))
        if method == 'DELETE':
            # Body must be absent (None) — RouterOS rejects DELETE with a body.
            if payload is not None:
                raise AssertionError('DELETE must be bodyless')
            rid = path.rsplit('/', 1)[-1]
            if path.startswith('interface/bridge/port/'):
                self.router.bridge_ports = [p for p in self.router.bridge_ports if p.get('.id') != rid]
                return {}
            if path.startswith('interface/vlan/'):
                row = self.router.vlans.pop(rid, None)
                if row:
                    self.router.interfaces.pop(row.get('name'), None)
                return {}
            if path.startswith('interface/bridge/'):
                row = self.router.bridges.pop(rid, None)
                if row:
                    self.router.interfaces.pop(row.get('name'), None)
                return {}
            raise AssertionError((method, path))
        raise AssertionError((method, path))


class Store:
    def __init__(self, *a, **k):
        pass

    def save_verified(self, data):
        return ('encrypted://vlan.bin', 'd' * 64)

    def remove(self, ref):
        pass


class GuestVlanExternalApTests(unittest.TestCase):
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
            'name': 'VLAN Hub', 'endpoint': 'hub.example.com', 'pool': '10.90.40.0/24', 'public_key': key(1),
        }).json()['id']
        with self.app.state.factory() as s:
            tenant = s.get(User, self.users['owner']).tenant_id
        self.client.post('/v1/hubs/' + hub + '/assignments', headers=platform, json={'tenant_id': tenant})
        site = self.client.post('/v1/sites', headers=owner, json={'name': 'VLAN Cafe'}).json()['id']
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
        fake = FakeVlanRouter()
        return owner, router, fake

    def harness(self, fake):
        return patch.multiple(
            'backend.safe_changes',
            load_routeros_safe_change_credential=lambda id: object(),
            RouterOSClient=fake.client,
            EncryptedBackupStore=Store,
        )

    def test_flag_off_refuses_vlan_preview(self):
        owner, router, fake = self.fixture()
        self.app.state.router_settings_changes_enabled = False
        with self.harness(fake):
            r = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'ether3', 'vlan_id': 50,
                'hotspot_interface': 'wifi2',
            })
        self.assertEqual(r.status_code, 503, r.text)

    def test_refuse_wan_wifi_and_hub_tunnel(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            wan = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'ether1', 'vlan_id': 50,
                'hotspot_interface': 'wifi2',
            })
            wifi = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'wifi1', 'vlan_id': 50,
                'hotspot_interface': 'wifi2',
            })
            hub = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'mm-97546f1a', 'vlan_id': 50,
                'hotspot_interface': 'wifi2',
            })
        self.assertEqual(wan.status_code, 409, wan.text)
        self.assertEqual(wifi.status_code, 422, wifi.text)
        self.assertEqual(hub.status_code, 422, hub.text)

    def test_apply_creates_vlan_bridge_and_migrates_hotspot(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'ether3', 'vlan_id': 50,
                'vlan_name': 'mm-guest-vlan-50', 'hotspot_interface': 'wifi2',
            })
        self.assertEqual(preview.status_code, 201, preview.text)
        body = preview.json()
        self.assertEqual(body['operation'], 'guest_vlan_external_ap')
        self.assertEqual(body['risk'], 'high')
        self.assertTrue(body['diff']['migration_needed'])
        self.assertEqual(body['diff']['vlan_id']['after'], 50)
        self.assertEqual(body['diff']['guest_bridge']['after'], 'mm-guest-br')
        self.assertIn('external AP', body['diff']['impact'])
        self.assertNotIn('password', preview.text.lower())
        with self.harness(fake):
            applied = self.client.post('/v1/router-changes/' + body['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()['status'], 'applied')
        # VLAN created on ether3
        vlan = next(v for v in fake.vlans.values() if v.get('name') == 'mm-guest-vlan-50')
        self.assertEqual(str(vlan['vlan-id']), '50')
        self.assertEqual(vlan['interface'], 'ether3')
        # Guest bridge created; wifi2 + vlan are ports
        self.assertTrue(any(b.get('name') == 'mm-guest-br' for b in fake.bridges.values()))
        ports = {(p.get('bridge'), p.get('interface')) for p in fake.bridge_ports}
        self.assertIn(('mm-guest-br', 'wifi2'), ports)
        self.assertIn(('mm-guest-br', 'mm-guest-vlan-50'), ports)
        # HotSpot / DHCP / address retargeted to guest bridge
        self.assertEqual(fake.hotspot['*F1']['interface'], 'mm-guest-br')
        self.assertEqual(fake.dhcp['*D1']['interface'], 'mm-guest-br')
        self.assertEqual(fake.addresses['*A1']['interface'], 'mm-guest-br')
        # LAN bridge and Hub addressing untouched
        self.assertEqual(fake.addresses['*A2']['address'], '192.168.88.1/24')
        self.assertEqual(fake.addresses['*A3']['address'], '10.90.1.2/32')
        self.assertTrue(any(p.get('interface') == 'ether2' and p.get('bridge') == 'bridge' for p in fake.bridge_ports))
        # Resource ids in writes are literal *N (never percent-encoded)
        for method, path, _payload in fake.writes:
            self.assertNotIn('%2A', path)
            if method == 'DELETE':
                self.assertIsNone(_payload)

    def test_rollback_on_verify_mismatch(self):
        owner, router, fake = self.fixture()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'ether3', 'vlan_id': 60,
                'hotspot_interface': 'wifi2',
            }).json()
        original = __import__('backend.guest_vlan_external_ap', fromlist=['apply_change']).apply_change

        def mismatch(client, before, desired):
            result = original(client, before, desired)
            result['vlan_on_guest_bridge'] = False
            return result

        with self.harness(fake), patch('backend.safe_changes.guest_vlan.apply_change', side_effect=mismatch):
            result = self.client.post('/v1/router-changes/' + preview['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.json()['status'], 'rolled_back')
        self.assertFalse(any(v.get('name') == 'mm-guest-vlan-60' for v in fake.vlans.values()))
        self.assertEqual(fake.hotspot['*F1']['interface'], 'wifi2')
        self.assertEqual(fake.dhcp['*D1']['interface'], 'wifi2')
        self.assertEqual(fake.addresses['*A1']['interface'], 'wifi2')
        self.assertFalse(any(b.get('name') == 'mm-guest-br' for b in fake.bridges.values()))

    def test_already_on_bridge_only_adds_vlan(self):
        owner, router, fake = self.fixture()
        # HotSpot already on a guest bridge
        rid = fake._id()
        fake.bridges[rid] = {'.id': rid, 'name': 'bridge-guest'}
        fake.interfaces['bridge-guest'] = {'.id': rid, 'name': 'bridge-guest', 'type': 'bridge'}
        fake.bridge_ports.append({'.id': fake._id(), 'interface': 'wifi2', 'bridge': 'bridge-guest'})
        fake.hotspot['*F1']['interface'] = 'bridge-guest'
        fake.addresses['*A1']['interface'] = 'bridge-guest'
        fake.dhcp['*D1']['interface'] = 'bridge-guest'
        # Update evidence inventory to match
        with self.app.state.factory() as s:
            ev = s.query(RouterEvidence).filter_by(router_id=router).one()
            payload = dict(ev.payload)
            payload['hotspot_portal_inventory'] = {
                'servers': [{'.id': '*H1', 'name': 'mm-lab-hotspot', 'interface': 'bridge-guest', 'profile': 'mm-lab-hsprof'}],
                'profiles': [{'name': 'mm-lab-hsprof', 'hotspot-address': '10.5.50.1'}],
            }
            ev.payload = payload
            s.commit()
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'guest_vlan_external_ap', 'ethernet_port': 'ether3', 'vlan_id': 70,
                'hotspot_interface': 'bridge-guest',
            })
        self.assertEqual(preview.status_code, 201, preview.text)
        self.assertFalse(preview.json()['diff']['migration_needed'])
        with self.harness(fake):
            applied = self.client.post('/v1/router-changes/' + preview.json()['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(applied.json()['status'], 'applied')
        vlan = next(v for v in fake.vlans.values() if v.get('name') == 'mm-guest-vlan-70')
        self.assertEqual(vlan['interface'], 'ether3')
        self.assertTrue(any(p.get('interface') == 'mm-guest-vlan-70' and p.get('bridge') == 'bridge-guest' for p in fake.bridge_ports))
        # Did not create mm-guest-br
        self.assertFalse(any(b.get('name') == 'mm-guest-br' for b in fake.bridges.values()))


if __name__ == '__main__':
    unittest.main()
