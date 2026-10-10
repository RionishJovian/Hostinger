import base64
import time
import unittest

from sqlalchemy import select

import test_backend
from backend.models import (
    LocalPortalPackage,
    MagicHub,
    RouterDevice,
    RouterEvidence,
    HotspotPortalPlan,
    RouterPlan,
    Site,
    SitePortal,
    User,
)


def key(value):
    return base64.b64encode(bytes([value]) * 32).decode()


class FirstSiteAcceptanceTests(unittest.TestCase):
    setUp = test_backend.AccountPaymentTests.setUp
    tearDown = test_backend.AccountPaymentTests.tearDown
    login = test_backend.AccountPaymentTests.login

    def create_site_router(self, owner, name='Acceptance site'):
        site = self.client.post('/v1/sites', headers=owner, json={'name': name, 'timezone': 'Asia/Yangon'})
        self.assertEqual(site.status_code, 201, site.text)
        router = self.client.post('/v1/routers', headers=owner, json={
            'site_id': site.json()['id'], 'name': 'Gateway', 'model': 'hAP test', 'reported_routeros': '7.24.2',
        })
        self.assertEqual(router.status_code, 201, router.text)
        return site.json()['id'], router.json()['id']

    def test_owner_sees_truthful_blocked_flow_without_router_evidence(self):
        owner = self.login('owner')
        site_id, router_id = self.create_site_router(owner)
        result = self.client.get(f'/v1/sites/{site_id}/first-site-acceptance', headers=owner)
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body['selected_router_id'], router_id)
        self.assertFalse(body['site_ready'])
        stages = {stage['key']: stage for stage in body['stages']}
        self.assertEqual(stages['site_details']['status'], 'complete')
        self.assertEqual(stages['router_registered']['status'], 'complete')
        for key_name in ['connection_verified', 'preflight_verified', 'hotspot_change_prepared',
                         'router_apply_verified', 'temporary_test_voucher', 'first_customer_test', 'site_ready']:
            self.assertNotEqual(stages[key_name]['status'], 'complete')
        self.assertEqual(body['real_device_acceptance'], 'not_yet_performed')

    def test_connected_preflight_and_portal_records_do_not_claim_hotspot_or_site_ready(self):
        owner = self.login('owner')
        site_id, router_id = self.create_site_router(owner, 'Evidence site')
        now = int(time.time())
        with self.app.state.factory() as session:
            actor = session.get(User, self.users['owner'])
            hub = MagicHub(name='Synthetic hub', endpoint='hub.invalid', port=51820, pool='10.90.0.0/24', public_key=key(1), next_host=3, created=now)
            session.add(hub);session.flush()
            plan = RouterPlan(tenant_id=actor.tenant_id, router_id=router_id, hub_id=hub.id,
                              router_public_key=key(2), address='10.90.0.2', snapshot={}, created=now,
                              reviewed_at=now-30, lifecycle_state='connected', handshake_verified_at=now-20,
                              management_read_verified_at=now-10)
            session.add(plan)
            session.add(RouterEvidence(tenant_id=actor.tenant_id, router_id=router_id, kind='preflight',
                observed_at=now-10, source='authenticated_routeros_read', created_by=actor.id, created=now-10,
                payload={'preflight_stage': 'post_connection',
                         'management_read': {'authenticated': True, 'identity_verified': True},
                         'compatibility': {'status': 'compatible_for_safe_change'},
                         'hotspot_portal_inventory': {
                             'write_operations_enabled': False,
                             'servers': [{'.id': '*A', 'name': 'hs-main', 'interface': 'bridge-guest', 'profile': 'guest-main', 'profile_server_count': 1}],
                             'profiles': [{'name': 'guest-main', 'login-by': 'http-chap,cookie', 'html-directory': 'hotspot', 'server_count': 1}],
                             'storage': {'flash_directory_present': True, 'configured_portal_files': []},
                         }}))
            session.add(SitePortal(site_id=site_id, revision=2, draft={}, published={}, published_revision=2, updated=now))
            session.add(LocalPortalPackage(tenant_id=actor.tenant_id, site_id=site_id, scope_key='site:'+site_id,
                published_revision=2, package_sha256='a'*64, package_bytes=b'synthetic', created=now))
            session.commit()
        body = self.client.get(f'/v1/sites/{site_id}/first-site-acceptance?router_id={router_id}', headers=owner).json()
        stages = {stage['key']: stage for stage in body['stages']}
        for key_name in ['connection_verified', 'preflight_verified', 'portal_published']:
            self.assertEqual(stages[key_name]['status'], 'complete')
        self.assertEqual(stages['hotspot_change_prepared']['status'], 'pending')
        for key_name in ['owner_review', 'router_apply_verified', 'temporary_test_voucher',
                         'first_customer_test', 'site_ready']:
            self.assertEqual(stages[key_name]['status'], 'blocked')
        self.assertFalse(body['site_ready'])

        evidence_id = body['hotspot_proposal']['preflight_evidence_id']
        prepared = self.client.post(f'/v1/routers/{router_id}/hotspot-portal-plans', headers=owner, json={
            'evidence_id': evidence_id, 'server_id': '*A',
        })
        self.assertEqual(prepared.status_code, 201, prepared.text)
        proposal = prepared.json()
        self.assertTrue(proposal['proposal_only'])
        self.assertFalse(proposal['commands_generated'])
        self.assertEqual(proposal['desired']['new_unique_directory'], f'flash/mm-b21-{site_id[:8]}-r2')
        self.assertEqual(proposal['impact']['shared_profile_server_count'], 1)
        self.assertEqual(self.client.post(f"/v1/hotspot-portal-plans/{proposal['id']}/review", headers=owner, json={
            'expected_revision': 1, 'confirm_exact_scope': True,
        }).status_code, 200)
        refreshed = self.client.get(f'/v1/sites/{site_id}/first-site-acceptance?router_id={router_id}', headers=owner).json()
        refreshed_stages = {stage['key']: stage for stage in refreshed['stages']}
        self.assertEqual(refreshed_stages['hotspot_change_prepared']['status'], 'complete')
        self.assertEqual(refreshed_stages['owner_review']['status'], 'complete')
        self.assertEqual(refreshed_stages['router_apply_verified']['status'], 'blocked')
        with self.app.state.factory() as session:
            self.assertEqual(session.query(HotspotPortalPlan).filter_by(router_id=router_id).count(), 1)

    def test_hotspot_proposal_rejects_untrusted_or_unsafe_inputs(self):
        owner = self.login('owner')
        other = self.login('other')
        site_id, router_id = self.create_site_router(owner, 'Unsafe proposal site')
        self.assertEqual(self.client.post(f'/v1/routers/{router_id}/hotspot-portal-plans', headers=other, json={
            'evidence_id': 'missing', 'server_id': '*A',
        }).status_code, 404)
        self.assertEqual(self.client.post(f'/v1/routers/{router_id}/hotspot-portal-plans', headers=owner, json={
            'evidence_id': 'missing', 'server_id': '*A',
        }).status_code, 409)

    def test_tenant_and_owner_authority_are_enforced(self):
        owner = self.login('owner')
        other = self.login('other')
        guest = self.login('guest')
        site_id, _ = self.create_site_router(owner, 'Private acceptance site')
        self.assertEqual(self.client.get(f'/v1/sites/{site_id}/first-site-acceptance', headers=other).status_code, 404)
        self.assertEqual(self.client.get(f'/v1/sites/{site_id}/first-site-acceptance', headers=guest).status_code, 403)


if __name__ == '__main__':
    unittest.main()
