"""Offline simulated RouterOS tests for HotSpot portal Safe Change publish."""
import hashlib
import os
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import test_backend as fixture
from backend.local_portal_package import FILES, build_local_hotspot_package
from backend.models import (
    HotspotPortalPlan,
    LocalPortalPackage,
    RouterChange,
    RouterEvidence,
    RouterPlan,
    SitePortal,
    User,
)
from backend.routeros_adapter import RouterOSError
from backend.schemas import PortalConfig


def key(n):
    return __import__('base64').b64encode(bytes([n]) * 32).decode()


class FakePortalRouter:
    """Minimal RouterOS stand-in: HotSpot profiles, files and config export."""

    def __init__(self, profile_name='guest-main', html_directory='hotspot', profile_id='*A1'):
        self.profiles = {profile_id: {'.id': profile_id, 'name': profile_name, 'html-directory': html_directory, 'login-by': 'http-chap'}}
        self.files = {}
        self.dirs = set()
        self.writes = []
        self.fail = None
        self.fail_after = None
        self._count = 0
        self.profile_id = profile_id

    def client(self, credential=None):
        return FakePortalClient(self)


class FakePortalClient:
    def __init__(self, router):
        self.router = router

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def export_configuration(self):
        if self.router.fail == 'backup':
            raise RouterOSError('backup_invalid', 'empty')
        return b'/ip hotspot profile export show-sensitive=no'

    def get(self, path, optional=False):
        if self.router.fail == 'read':
            raise RouterOSError('unreachable', 'offline')
        if path == 'ip/hotspot/profile':
            return [dict(x) for x in self.router.profiles.values()]
        if path == 'file' or path.startswith('file'):
            dirs = sorted({name.rsplit('/', 1)[0] for name in self.router.files if '/' in name} | self.router.dirs)
            return [{'.id': '*D' + d, 'name': d, 'type': 'directory'} for d in dirs] + [
                {'.id': '*F' + name, 'name': name, 'type': 'file', 'size': str(len(body))} for name, body in self.router.files.items()]
        raise AssertionError(path)

    def write(self, method, path, payload):
        self.router._count += 1
        if self.router.fail_after and self.router._count >= self.router.fail_after:
            raise RouterOSError('router_write_failed', 'simulated write failure')
        if self.router.fail == 'write':
            raise RouterOSError('router_write_failed', 'simulated')
        self.router.writes.append((method, path, dict(payload or {})))
        if method == 'PUT' and path == 'file':
            name = payload['name']
            if name.endswith('.json'):
                raise RouterOSError('router_write_failed', 'permission denied')
            if name in self.router.files:
                raise RouterOSError('router_write_failed', 'exists')
            self.router.files[name] = payload.get('contents') or ''
            if '/' in name:
                self.router.dirs.add(name.rsplit('/', 1)[0])
            return {}
        if method == 'POST' and path == 'file/remove':
            name = payload['.id'][2:]
            if payload['.id'].startswith('*D') and not any(f.startswith(name + '/') for f in self.router.files):
                self.router.dirs.discard(name)
                return []
            raise RouterOSError('router_write_failed', 'cannot remove')
        if method == 'PATCH' and path.startswith('ip/hotspot/profile/'):
            from urllib.parse import unquote
            rid = unquote(path.rsplit('/', 1)[-1])
            self.router.profiles[rid].update(payload)
            return {}
        if method == 'DELETE' and path.startswith('file/'):
            from urllib.parse import unquote
            name = unquote(path[len('file/'):])
            self.router.files.pop(name, None)
            return {}
        raise AssertionError((method, path))


class Store:
    def __init__(self, *a, **k):
        pass

    def save_verified(self, data):
        return ('encrypted://portal.bin', 'b' * 64)

    def remove(self, ref):
        pass


class HotspotPortalPublishTests(unittest.TestCase):
    setUp = fixture.AccountPaymentTests.setUp
    tearDown = fixture.AccountPaymentTests.tearDown
    login = fixture.AccountPaymentTests.login

    def setUp_env(self):
        self.env = patch.dict(os.environ, {'MIKROMAGIC_BACKUP_KEY': Fernet.generate_key().decode()})
        self.env.start()
        self.addCleanup(self.env.stop)

    def fixture(self):
        self.setUp_env()
        platform = self.login('platform')
        owner = self.login('owner')
        hub = self.client.post('/v1/hubs', headers=platform, json={
            'name': 'Portal Hub', 'endpoint': 'hub.example.com', 'pool': '10.90.20.0/24', 'public_key': key(1),
        }).json()['id']
        with self.app.state.factory() as s:
            tenant = s.get(User, self.users['owner']).tenant_id
        self.client.post('/v1/hubs/' + hub + '/assignments', headers=platform, json={'tenant_id': tenant})
        site = self.client.post('/v1/sites', headers=owner, json={'name': 'Portal Cafe'}).json()['id']
        router = self.client.post('/v1/routers', headers=owner, json={
            'site_id': site, 'name': 'Gateway', 'model': 'hAP ax2', 'reported_routeros': '7.20',
        }).json()['id']
        package_bytes = build_local_hotspot_package(
            PortalConfig(business_name='Portal Cafe', welcome='Welcome'),
            tenant_id=tenant, site_id=site, revision=1,
        )
        digest = hashlib.sha256(package_bytes).hexdigest()
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
                        'write_operations_enabled': False,
                        'servers': [{'.id': '*A', 'name': 'hs-main', 'interface': 'bridge-guest', 'profile': 'guest-main', 'profile_server_count': 1}],
                        'profiles': [{'name': 'guest-main', 'login-by': 'http-chap', 'html-directory': 'hotspot', 'server_count': 1}],
                        'storage': {'flash_directory_present': True, 'configured_portal_files': []},
                    },
                },
            ))
            s.add(SitePortal(site_id=site, revision=1, draft={}, published={'business_name': 'Portal Cafe'}, published_revision=1, updated=now))
            s.add(LocalPortalPackage(
                tenant_id=tenant, site_id=site, scope_key='site:' + site, published_revision=1,
                package_sha256=digest, package_bytes=package_bytes, created=now,
            ))
            s.commit()
            evidence_id = s.query(RouterEvidence).filter_by(router_id=router).one().id
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
        prepared = self.client.post('/v1/routers/' + router + '/hotspot-portal-plans', headers=owner, json={
            'evidence_id': evidence_id, 'server_id': '*A',
        })
        self.assertEqual(prepared.status_code, 201, prepared.text)
        reviewed = self.client.post('/v1/hotspot-portal-plans/' + prepared.json()['id'] + '/review', headers=owner, json={
            'expected_revision': 1, 'confirm_exact_scope': True,
        })
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        fake = FakePortalRouter()
        return owner, router, reviewed.json(), fake, site, digest

    def harness(self, fake, store=Store):
        return patch.multiple(
            'backend.safe_changes',
            load_routeros_safe_change_credential=lambda id: object(),
            RouterOSClient=lambda credential: fake.client(),
            EncryptedBackupStore=store,
        )

    def test_publish_installs_create_only_directory_and_switches_profile(self):
        owner, router, plan, fake, site, digest = self.fixture()
        destination = f'flash/mm-b21-{site[:8]}-r1'
        with self.harness(fake):
            preview = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            })
        self.assertEqual(preview.status_code, 201, preview.text)
        change = preview.json()
        self.assertEqual(change['operation'], 'hotspot_portal_publish')
        self.assertEqual(change['diff']['profile_html_directory'], {'before': 'hotspot', 'after': destination})
        self.assertEqual(self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=owner, json={
            'expected_revision': 1, 'confirm_high_risk': False,
        }).status_code, 422)
        with self.harness(fake):
            applied = self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(applied.status_code, 200, applied.text)
        body = applied.json()
        self.assertEqual(body['status'], 'applied')
        self.assertTrue(body['safety_backup_verified'])
        self.assertEqual(body['real_device_acceptance'], 'not_yet_performed')
        self.assertEqual(fake.profiles[fake.profile_id]['html-directory'], destination)
        for name in FILES:
            if name.endswith('.json'):
                self.assertNotIn(destination + '/' + name, fake.files)
            else:
                self.assertIn(destination + '/' + name, fake.files)
        acceptance = self.client.get(f'/v1/sites/{site}/first-site-acceptance?router_id={router}', headers=owner).json()
        stages = {s['key']: s for s in acceptance['stages']}
        self.assertEqual(stages['router_apply_verified']['status'], 'complete')
        self.assertEqual(stages['temporary_test_voucher']['status'], 'blocked')
        self.assertFalse(acceptance['site_ready'])
        self.assertEqual(acceptance['real_device_acceptance'], 'not_yet_performed')

    def test_backup_failure_writes_nothing(self):
        owner, router, plan, fake, site, digest = self.fixture()
        class FailedStore:
            def __init__(self, *a, **k): pass
            def save_verified(self, data): raise RouterOSError('backup_verification_failed', 'bad')
        with self.harness(fake):
            change = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            }).json()
        with self.harness(fake, FailedStore):
            result = self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.status_code, 409)
        self.assertEqual(fake.writes, [])
        self.assertEqual(fake.profiles[fake.profile_id]['html-directory'], 'hotspot')
        self.assertEqual(fake.files, {})

    def test_destination_collision_refuses_preview(self):
        owner, router, plan, fake, site, digest = self.fixture()
        destination = f'flash/mm-b21-{site[:8]}-r1'
        fake.files[destination + '/login.html'] = 'stale'
        with self.harness(fake):
            result = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            })
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()['detail']['code'], 'file_collision')

    def test_verification_mismatch_rolls_back_profile_and_files(self):
        owner, router, plan, fake, site, digest = self.fixture()
        with self.harness(fake):
            change = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            }).json()
        original_apply = __import__('backend.hotspot_portal_publish', fromlist=['apply_install']).apply_install

        def broken_apply(client, before, desired, files):
            original_apply(client, before, desired, files)
            # Corrupt verification by pointing the profile elsewhere after install.
            client.router.profiles[before['resource_id']]['html-directory'] = 'other-hotspot'
            raise RouterOSError('router_write_failed', 'post-switch failure')

        with self.harness(fake), patch('backend.safe_changes.portal.apply_install', broken_apply):
            result = self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'rolled_back')
        self.assertEqual(fake.profiles[fake.profile_id]['html-directory'], 'hotspot')
        self.assertEqual(fake.files, {})
        self.assertEqual(fake.dirs, set())

    def test_stale_profile_directory_is_conflict(self):
        owner, router, plan, fake, site, digest = self.fixture()
        with self.harness(fake):
            change = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            }).json()
        fake.profiles[fake.profile_id]['html-directory'] = 'changed-by-owner'
        with self.harness(fake):
            result = self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=owner, json={
                'expected_revision': 1, 'confirm_high_risk': True,
            })
        self.assertEqual(result.status_code, 409)
        with self.app.state.factory() as s:
            self.assertEqual(s.get(RouterChange, change['id']).status, 'conflict')

    def test_tenant_isolation_and_unreviewed_plan(self):
        owner, router, plan, fake, site, digest = self.fixture()
        other = self.login('other')
        with self.harness(fake):
            change = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            }).json()
        self.assertEqual(self.client.post('/v1/router-changes/' + change['id'] + '/apply', headers=other, json={
            'expected_revision': 1, 'confirm_high_risk': True,
        }).status_code, 404)
        with self.app.state.factory() as s:
            row = s.get(HotspotPortalPlan, plan['id'])
            row.status = 'prepared'
            row.revision = 1
            row.reviewed_at = None
            s.commit()
        with self.harness(fake):
            denied = self.client.post('/v1/routers/' + router + '/changes/preview', headers=owner, json={
                'operation': 'hotspot_portal_publish', 'hotspot_portal_plan_id': plan['id'],
            })
        self.assertEqual(denied.status_code, 409)


if __name__ == '__main__':
    unittest.main()
