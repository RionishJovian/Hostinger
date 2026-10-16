import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from backend.owner_api import _platform_admin, _safe_change_script, _terminal_command, _test_lab_unavailable, _visible_router


class _NoRouterSession:
    def scalar(self, _query):
        return None


class OwnerApiGuardTests(unittest.TestCase):
    def test_staff_cannot_use_platform_admin_routes(self):
        with self.assertRaises(HTTPException) as error:
            _platform_admin(SimpleNamespace(role="sme", platform_owner=False))
        self.assertEqual(error.exception.status_code, 403)

    def test_platform_admin_requires_both_role_and_owner_flag(self):
        with self.assertRaises(HTTPException):
            _platform_admin(SimpleNamespace(role="platform", platform_owner=False))
        self.assertIsNone(_platform_admin(SimpleNamespace(role="platform", platform_owner=True)))

    def test_cross_shop_router_is_not_visible(self):
        with self.assertRaises(HTTPException) as error:
            _visible_router(_NoRouterSession(), SimpleNamespace(tenant_id="shop-a"), "router-from-shop-b")
        self.assertEqual(error.exception.status_code, 404)

    def test_terminal_and_script_guards_are_fail_closed(self):
        for command in ("/sys reb", ':execute "foo"', "user set password=x"):
            with self.subTest(command=command):
                with self.assertRaises(HTTPException):
                    _terminal_command(command)
        with self.assertRaises(HTTPException) as error:
            _safe_change_script("unknown-operation")
        self.assertEqual(error.exception.status_code, 422)

    def test_test_lab_is_always_unavailable(self):
        with self.assertRaises(HTTPException) as error:
            _test_lab_unavailable()
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
