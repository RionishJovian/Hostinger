import unittest
from datetime import datetime, timedelta, timezone

from backend.change_actions import ChangePlan, FairShareChange, HotspotVoucherChange, ProtectionChange, build_change_plan, build_fair_share_plan, build_hotspot_plan, build_protection_plan, verify_readback


class ChangeActionTests(unittest.TestCase):
    def test_protection_plan_is_typed_safe_change_data(self):
        plan = build_protection_plan(ProtectionChange("10.20.0.7/24", "guest-vlan20"))
        self.assertEqual((plan.action, plan.execution_path, plan.risk), ("protection", "safe_change_only", "high"))
        self.assertTrue(all(command.startswith("/ip firewall filter add ") for command in plan.commands))
        self.assertTrue(any(rule["comment"].endswith("-router") for rule in plan.expected_readback["rules"]))
        self.assertIs(build_change_plan(ProtectionChange("10.20.0.0/24", "guest-vlan20")).__class__, ChangePlan)

    def test_protection_rejects_routeros_injection(self):
        with self.assertRaises(ValueError):
            build_protection_plan(ProtectionChange("10.20.0.0/24", "guest; /system reboot"))

    def test_fair_share_builds_pcq_queue_and_normalizes_readback_rates(self):
        plan = build_fair_share_plan(FairShareChange("shop-guests", "10.30.0.9/24", "10M", "20M"))
        self.assertIn("pcq-upload-default/pcq-download-default", plan.commands[0])
        actual = {"queue": dict(plan.expected_readback["queue"], **{"max-limit": "10000000/20000000", "disabled": "false"})}
        self.assertEqual(verify_readback(plan, actual), (True, {}))

    def test_readback_diff_reports_only_mismatches(self):
        plan = build_fair_share_plan(FairShareChange("shop-guests", "10.30.0.0/24", "10M", "20M"))
        actual = {"queue": dict(plan.expected_readback["queue"], target="10.31.0.0/24")}
        ok, diff = verify_readback(plan, actual)
        self.assertFalse(ok)
        self.assertEqual(diff["queue.target"], {"expected": "10.30.0.0/24", "actual": "10.31.0.0/24"})

    def test_hotspot_plan_has_bounded_quota_deadline_and_disabled_first_create(self):
        now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        plan = build_hotspot_plan(HotspotVoucherChange("voucher_001", "02-11-22-33-44-55", "hotspot1", 60, 500, now + timedelta(minutes=60), "mac-secret"), now=now)
        self.assertEqual(plan.action, "hotspot_voucher")
        self.assertIn('disabled="yes"', plan.commands[1])
        self.assertTrue(plan.commands[-1].startswith("/ip hotspot user enable"))
        self.assertNotIn("mac-secret", str(plan.expected_readback))
        self.assertEqual(plan.expected_readback["user"]["limit-bytes-total"], "500000000")
        self.assertEqual(verify_readback(plan, plan.expected_readback), (True, {}))

    def test_hotspot_rejects_multicast_mac_expired_or_excess_allowance(self):
        now = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
        for change in (
            HotspotVoucherChange("v1", "01:11:22:33:44:55", "hotspot1", 60, 5, now + timedelta(minutes=1)),
            HotspotVoucherChange("v1", "02:11:22:33:44:55", "hotspot1", 60, 5, now),
            HotspotVoucherChange("v1", "02:11:22:33:44:55", "hotspot1", 1, 5, now + timedelta(minutes=2)),
        ):
            with self.assertRaises(ValueError):
                build_hotspot_plan(change, now=now)


if __name__ == "__main__":
    unittest.main()
