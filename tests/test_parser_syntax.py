import os
import unittest

from core.parser import RedisCommandParser


class TestParserSyntax(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls._old_cwd = os.getcwd()
        os.chdir(cls.project_root)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._old_cwd)

    def setUp(self):
        self.parser = RedisCommandParser()

    def test_unbalanced_quotes(self):
        ok, msg = self.parser.syntax_check_line('SET k "v')
        self.assertFalse(ok)
        self.assertEqual(msg, "Unbalanced quotes")

    def test_invalid_command_name(self):
        ok, msg = self.parser.syntax_check_line("se-t k v")
        self.assertFalse(ok)
        self.assertIn("Invalid command name", msg)

    def test_get_requires_one_arg(self):
        ok, msg = self.parser.syntax_check_line("GET")
        self.assertFalse(ok)
        self.assertEqual(msg, "GET expects exactly 1 argument: GET <key>")

        ok, msg = self.parser.syntax_check_line("GET k extra")
        self.assertFalse(ok)
        self.assertEqual(msg, "GET expects exactly 1 argument: GET <key>")

        ok, msg = self.parser.syntax_check_line("GET k")
        self.assertTrue(ok)
        self.assertIsNone(msg)

    def test_set_requires_key_value(self):
        ok, msg = self.parser.syntax_check_line("SET onlykey")
        self.assertFalse(ok)
        self.assertEqual(msg, "SET expects at least 2 arguments: SET <key> <value>")

    def test_set_ex_requires_int(self):
        ok, msg = self.parser.syntax_check_line("SET k v EX")
        self.assertFalse(ok)
        self.assertEqual(msg, "SET option 'EX' expects an integer argument")

        ok, msg = self.parser.syntax_check_line("SET k v EX notint")
        self.assertFalse(ok)
        self.assertEqual(msg, "SET option 'EX' expects an integer argument")

        ok, msg = self.parser.syntax_check_line("SET k v EX 10")
        self.assertTrue(ok)
        self.assertIsNone(msg)

    def test_set_unknown_option(self):
        ok, msg = self.parser.syntax_check_line("SET k v UNKNOWNOPT")
        self.assertFalse(ok)
        self.assertEqual(msg, "Unknown SET option 'UNKNOWNOPT'")

    def test_parse_script_with_syntax_preserves_order(self):
        parsed, syntax = self.parser.parse_script_with_syntax(
            "SET k v\nGET k\nSET onlykey\n"
        )
        self.assertEqual([s["order"] for s in syntax], [1, 2, 3])
        self.assertEqual([c["order"] for c in parsed], [1, 2])

