import base64
import unittest

from backend.mfa import totp
from backend.totp_gate import ReplayGuard, evaluate_safe_change_gate, matching_totp_step, verify_totp


class TOTPGateTests(unittest.TestCase):
    def setUp(self):
        self.secret = base64.b32encode(b"12345678901234567890").decode()
        self.now = 1_700_000_000
        self.code = totp(self.secret, self.now // 30)

    def test_verifies_window_and_rejects_replay_per_subject(self):
        guard = ReplayGuard()
        self.assertTrue(verify_totp(self.secret, self.code, "router-a", guard, now=self.now, window=1))
        self.assertFalse(verify_totp(self.secret, self.code, "router-a", guard, now=self.now, window=1))
        self.assertTrue(verify_totp(self.secret, self.code, "router-b", guard, now=self.now, window=1))
        previous = totp(self.secret, self.now // 30 - 1)
        self.assertIsNotNone(matching_totp_step(self.secret, previous, now=self.now, window=1))

    def test_malformed_secret_and_code_fail_closed(self):
        guard = ReplayGuard()
        with self.assertRaises(ValueError):
            verify_totp("not-valid-1", self.code, "router-a", guard, now=self.now)
        self.assertFalse(verify_totp(self.secret, "12345x", "router-a", guard, now=self.now))

    def test_rejection_and_no_changes_precede_otp(self):
        guard = ReplayGuard()
        rejected = evaluate_safe_change_gate(approved=False, has_changes=True, risk="high", secret=self.secret, code=self.code, subject="change-a", replay_guard=guard, now=self.now)
        empty = evaluate_safe_change_gate(approved=True, has_changes=False, risk="high", secret=self.secret, code=self.code, subject="change-b", replay_guard=guard, now=self.now)
        self.assertEqual((rejected.allowed, rejected.reason), (False, "rejected"))
        self.assertEqual((empty.allowed, empty.reason), (False, "no_changes"))

    def test_high_risk_requires_configured_fresh_totp(self):
        guard = ReplayGuard()
        missing = evaluate_safe_change_gate(approved=True, has_changes=True, risk="high", subject="change-a", replay_guard=guard, now=self.now)
        allowed = evaluate_safe_change_gate(approved=True, has_changes=True, risk="high", secret=self.secret, code=self.code, subject="change-a", replay_guard=guard, now=self.now)
        replay = evaluate_safe_change_gate(approved=True, has_changes=True, risk="high", secret=self.secret, code=self.code, subject="change-a", replay_guard=guard, now=self.now)
        self.assertEqual((missing.allowed, missing.reason), (False, "otp_required"))
        self.assertEqual((allowed.allowed, allowed.reason, allowed.otp_required), (True, "approved", True))
        self.assertEqual((replay.allowed, replay.reason), (False, "otp_invalid"))

    def test_low_risk_manual_approval_does_not_consume_code(self):
        guard = ReplayGuard()
        result = evaluate_safe_change_gate(approved=True, has_changes=True, risk="low", secret=self.secret, code=self.code, subject="change-a", replay_guard=guard, now=self.now)
        self.assertEqual((result.allowed, result.reason, result.otp_required), (True, "approved", False))
        self.assertTrue(verify_totp(self.secret, self.code, "change-a", guard, now=self.now))

    def test_named_high_risk_action_requires_totp_even_at_medium_risk(self):
        result = evaluate_safe_change_gate(approved=True, has_changes=True, risk="medium", actions=["reboot"])
        self.assertEqual((result.allowed, result.reason, result.otp_required), (False, "otp_required", True))


if __name__ == "__main__":
    unittest.main()
