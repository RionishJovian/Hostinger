import unittest

from backend.owner_api import _SAFE_CHANGE_SCRIPTS, _safe_change_script, _terminal_command
from fastapi import HTTPException


class TerminalAllowlistTests(unittest.TestCase):
    def test_only_named_safe_change_operation_exists(self):
        self.assertEqual(
            _SAFE_CHANGE_SCRIPTS,
            frozenset({'remove-legacy-lovable-api-user-and-wg-peer'}),
        )
        self.assertEqual(
            _safe_change_script('remove-legacy-lovable-api-user-and-wg-peer'),
            'remove-legacy-lovable-api-user-and-wg-peer',
        )
        with self.assertRaises(HTTPException) as error:
            _safe_change_script('arbitrary-routeros-script')
        self.assertEqual(error.exception.status_code, 422)

    def test_fixed_read_commands_are_canonicalized(self):
        self.assertEqual(
            _terminal_command('  /SYSTEM   RESOURCE   PRINT  '),
            '/system resource print',
        )
        self.assertEqual(
            _terminal_command('/interface wireguard print detail'),
            '/interface wireguard print detail',
        )

    def test_old_blocklist_bypasses_are_rejected(self):
        for command in (
            '/sys reb',
            ':execute "/system identity print"',
            'wireguard print detail',
            '/user set password=leaked',
        ):
            with self.subTest(command=command):
                with self.assertRaises(HTTPException) as error:
                    _terminal_command(command)
                self.assertEqual(error.exception.status_code, 422)

    def test_chaining_and_unvalidated_arguments_are_rejected(self):
        for command in (
            '/system identity print; /system reboot',
            '/system identity print where name=router',
            '/interface wireguard print terse',
            '/ip route print proplist=.id',
        ):
            with self.subTest(command=command):
                with self.assertRaises(HTTPException):
                    _terminal_command(command)


if __name__ == '__main__':
    unittest.main()
