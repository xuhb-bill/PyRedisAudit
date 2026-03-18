import os
import unittest

from config.config_loader import ConfigLoader
from core.auditor import RedisAuditor
from core.parser import RedisCommandParser


class TestAuditorRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls._old_cwd = os.getcwd()
        os.chdir(cls.project_root)

        cls.config_loader = ConfigLoader(os.path.join(cls.project_root, "config/default_config.yaml"))
        cls.parser = RedisCommandParser()
        cls.auditor = RedisAuditor(cls.config_loader)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._old_cwd)

    def test_high_risk_command_blocked(self):
        parsed = self.parser.parse_line("FLUSHALL")
        res = self.auditor.audit_commands([parsed])
        self.assertEqual(res[0]["status"], "failed")
        self.assertEqual(res[0]["level"], "error")
        self.assertIn("High-risk command", res[0]["message"])

    def test_flushdb_blocked(self):
        parsed = self.parser.parse_line("FLUSHDB")
        res = self.auditor.audit_commands([parsed])
        self.assertEqual(res[0]["status"], "failed")
        self.assertIn(res[0]["level"], ("error", "warning"))

    def test_ttl_requirement_warning(self):
        parsed = self.parser.parse_line("SET k v")
        res = self.auditor.audit_commands([parsed])
        self.assertEqual(res[0]["status"], "failed")
        self.assertEqual(res[0]["level"], "warning")
        self.assertIn("missing TTL", res[0]["message"])

    def test_version_incompatibility_error(self):
        parsed = self.parser.parse_line("COPY k1 k2")
        res = self.auditor.audit_commands([parsed])
        self.assertEqual(res[0]["status"], "failed")
        self.assertEqual(res[0]["level"], "error")
        self.assertIn("not supported", res[0]["message"])

    def test_key_naming_violation(self):
        parsed = self.parser.parse_line("SET user@1003 v EX 10")
        res = self.auditor.audit_commands([parsed])
        self.assertEqual(res[0]["status"], "failed")
        self.assertEqual(res[0]["level"], "warning")
