import os
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest import mock

from config.config_loader import ConfigLoader
from core.auditor import RedisAuditor
from core.parser import RedisCommandParser


class TestConcurrencyAndBigKey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls._old_cwd = os.getcwd()
        os.chdir(cls.project_root)

        cls.config_loader = ConfigLoader(os.path.join(cls.project_root, "config/default_config.yaml"))
        cls.auditor = RedisAuditor(cls.config_loader)
        cls.parser = RedisCommandParser()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._old_cwd)

    def test_high_concurrency_check_only(self):
        commands = [f"SET app:user:{i} v EX 10" for i in range(200)]

        def one(cmd):
            parsed, syntax = self.parser.parse_script_with_syntax(cmd)
            self.assertEqual(len(syntax), 1)
            self.assertEqual(syntax[0]["status"], "passed")
            res = self.auditor.audit_commands(parsed)
            return res[0]["status"]

        with ThreadPoolExecutor(max_workers=50) as ex:
            futures = [ex.submit(one, c) for c in commands]
            results = [f.result() for f in as_completed(futures)]

        self.assertEqual(len(results), 200)
        self.assertTrue(all(r == "passed" for r in results))

    def test_big_value_parsing_and_audit(self):
        big_value = "x" * (1024 * 1024)
        cmd = f'SET app:bigkey "{big_value}" EX 10'
        parsed, syntax = self.parser.parse_script_with_syntax(cmd)
        self.assertEqual(syntax[0]["status"], "passed")
        res = self.auditor.audit_commands(parsed)
        self.assertEqual(res[0]["status"], "passed")

    def test_execute_big_value_uses_tokens(self):
        big_value = "x" * (256 * 1024)
        cmd = f'SET app:bigexec "{big_value}" EX 10'
        parsed, syntax = self.parser.parse_script_with_syntax(cmd)
        self.assertEqual(syntax[0]["status"], "passed")

        fake_client = mock.MagicMock()
        fake_client.get_server_version.return_value = "7.0.0"
        fake_client.key_exists.return_value = False
        fake_client.execute.return_value = (True, "OK")

        res = self.auditor.audit_commands(parsed, redis_client=fake_client)
        self.assertEqual(res[0]["status"], "passed")
        ok, _ = fake_client.execute(parsed[0]["tokens"])
        self.assertTrue(ok)
