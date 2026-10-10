import unittest
from backend.routeros_compatibility import classify_routeros_compatibility


class RouterOSCompatibilityTests(unittest.TestCase):
    def classify(self, version='7.20.2 (stable)', architecture='arm64', wireguard=True, scheme='https', tls=True):
        return classify_routeros_compatibility(
            {'version': version, 'architecture-name': architecture},
            {'wireguard': wireguard},
            {'scheme': scheme, 'tls_verified': tls},
            read_access_verified=True,
        )

    def test_capability_evidence_not_model_name_controls_review_readiness(self):
        result = self.classify()
        self.assertEqual(result['status'], 'compatible_for_safe_change')
        self.assertTrue(result['wireguard_detected'])
        self.assertEqual(result['management_permissions']['monitoring_read'], 'verified')
        self.assertEqual(result['management_permissions']['safe_change_write'], 'not_tested')
        self.assertFalse(result['connection_verified'])
        self.assertFalse(result['router_configuration_changed'])

    def test_routeros_6_or_legacy_architecture_is_unsupported(self):
        self.assertEqual(self.classify(version='6.49.17', architecture='mipsbe')['status'], 'unsupported')
        self.assertEqual(self.classify(architecture='mipsle')['status'], 'unsupported')

    def test_missing_capability_unknown_arch_or_unverified_tls_needs_review(self):
        self.assertEqual(self.classify(wireguard=False)['status'], 'needs_review')
        self.assertEqual(self.classify(architecture='unknown-cpu')['status'], 'needs_review')
        self.assertEqual(self.classify(architecture='')['status'], 'needs_review')
        self.assertEqual(self.classify(scheme='http')['status'], 'needs_review')
        self.assertEqual(self.classify(tls=False)['status'], 'needs_review')

    def test_prerelease_versions_do_not_pass_automatically(self):
        result = self.classify(version='7.21rc1')
        self.assertEqual(result['status'], 'needs_review')
        self.assertIn('Prerelease/testing RouterOS builds require explicit compatibility review.', result['reasons'])

    def test_management_write_permission_is_never_inferred(self):
        result = self.classify()
        self.assertEqual(result['management_permissions']['safe_change_write'], 'not_tested')
        self.assertIn('No write permission is inferred', result['management_permissions']['note'])


if __name__ == '__main__':
    unittest.main()
