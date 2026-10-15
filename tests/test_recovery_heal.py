import unittest

from backend.recovery_heal import RecoveryState, recommend_recovery, recommend_recovery_action


class RecoveryHealTests(unittest.TestCase):
    def test_up_or_verified_rollback_needs_no_action(self):
        self.assertEqual(recommend_recovery_action(RecoveryState("up")), "no_action")
        result = recommend_recovery(RecoveryState("offline", safe_change_status="rolled_back", rollback_verified=True))
        self.assertEqual((result.action, result.automatic), ("no_action", False))

    def test_transient_state_only_recommends_reprobe(self):
        result = recommend_recovery(RecoveryState("stale", attempts=1))
        self.assertEqual((result.action, result.automatic), ("reprobe", False))

    def test_failed_safe_change_proposes_reviewed_rollback_without_applying(self):
        result = recommend_recovery(RecoveryState("offline", safe_change_status="recovery_required", rollback_available=True))
        self.assertEqual(result.action, "propose_safe_change_rollback")
        self.assertFalse(result.automatic)

    def test_missing_rollback_or_backoff_alerts_owner(self):
        self.assertEqual(recommend_recovery_action(RecoveryState("failed", safe_change_status="failed")), "alert_owner")
        self.assertEqual(recommend_recovery_action(RecoveryState("offline", attempts=3, max_attempts=3)), "alert_owner")

    def test_invalid_state_fails_closed(self):
        with self.assertRaises(ValueError):
            recommend_recovery(RecoveryState("reboot"))
        with self.assertRaises(ValueError):
            recommend_recovery(RecoveryState("offline", attempts=-1))


if __name__ == "__main__":
    unittest.main()
