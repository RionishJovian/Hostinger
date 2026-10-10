import hashlib
import io
import json
import unittest
import zipfile

import test_backend
import test_guest_entry
from backend.local_portal_package import validate_local_hotspot_package
from backend.models import LocalPortalPackage, SitePortal, User
from sqlalchemy import select


class LocalPortalPublishFlowTests(unittest.TestCase):
    setUp = test_backend.AccountPaymentTests.setUp
    tearDown = test_backend.AccountPaymentTests.tearDown
    login = test_backend.AccountPaymentTests.login
    site = test_guest_entry.GuestEntryTests.site

    def test_owner_publishes_site_revision_and_internal_package_atomically(self):
        owner = self.login('owner')
        site_id = self.site()
        url = f'/v1/sites/{site_id}/portal'
        state = self.client.get(url, headers=owner).json()
        self.assertEqual(state['local_portal_package']['status'], 'pending')
        settings = {**state['draft'], 'business_name': 'Synthetic Acceptance Cafe',
                    'welcome': 'Local fixture portal', 'terms': 'Synthetic test only'}
        saved = self.client.post(url + '/draft', headers=owner,
                                 json={'expected_revision': state['revision'], 'settings': settings})
        self.assertEqual(saved.status_code, 200)
        published = self.client.post(url + '/publish', headers=owner,
                                     json={'expected_revision': saved.json()['revision']})
        self.assertEqual(published.status_code, 200)
        result = published.json()
        revision = result['published_revision']
        self.assertEqual(result['local_portal_package']['status'], 'ready_for_router_deployment')
        self.assertEqual(result['local_portal_package']['published_revision'], revision)
        self.assertEqual(result['router_deployment_status'], 'pending')
        self.assertEqual(result['router_apply_state'], 'not_connected')

        with self.app.state.factory() as session:
            site = session.get(SitePortal, site_id)
            actor = session.get(User, self.users['owner'])
            artifact = session.scalar(select(LocalPortalPackage).where(
                LocalPortalPackage.scope_key == 'site:' + site_id,
                LocalPortalPackage.published_revision == revision,
            ))
            self.assertEqual(site.published_revision, revision)
            self.assertEqual(artifact.tenant_id, actor.tenant_id)
            self.assertEqual(artifact.site_id, site_id)
            self.assertEqual(artifact.package_sha256, hashlib.sha256(artifact.package_bytes).hexdigest())
            self.assertEqual(artifact.package_sha256, result['local_portal_package']['sha256'])
            self.assertTrue(validate_local_hotspot_package(artifact.package_bytes)['valid'])
            with zipfile.ZipFile(io.BytesIO(artifact.package_bytes)) as archive:
                manifest = json.loads(archive.read('portal-manifest.json'))
                self.assertEqual(manifest['scope'], {'tenant_id': actor.tenant_id, 'site_id': site_id,
                                                     'published_revision': revision})
                self.assertFalse(manifest['installation_performed'])
                self.assertFalse(manifest['router_compatibility_verified'])
        self.assertEqual(self.client.get(url, headers=self.login('other')).status_code, 404)
        refreshed = self.client.get(url, headers=owner).json()
        self.assertEqual(refreshed['local_portal_package']['sha256'], result['local_portal_package']['sha256'])
        public = self.client.get('/v1/public/sites/' + site_id).json()
        self.assertNotIn('local_portal_package', public)
        self.assertNotIn(result['local_portal_package']['sha256'], json.dumps(public))


if __name__ == '__main__':
    unittest.main()
