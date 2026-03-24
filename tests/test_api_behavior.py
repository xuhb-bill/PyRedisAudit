import os
import unittest
from unittest import mock

import app as app_module
from config.config_loader import ConfigLoader
from core.auditor import RedisAuditor
from core.parser import RedisCommandParser


class TestApiBehavior(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls._old_cwd = os.getcwd()
        os.chdir(cls.project_root)

        config_loader = ConfigLoader(os.path.join(cls.project_root, "config/default_config.yaml"))
        app_module.parser = RedisCommandParser()
        app_module.auditor = RedisAuditor(config_loader)
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._old_cwd)

    def test_empty_body(self):
        resp = self.client.post("/audit")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["code"], 40001)
        self.assertEqual(data["status"], "failed")

    def test_check_defaults_to_1_execute_defaults_to_0(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET dba-test 12345"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["code"], 2002)
        self.assertEqual(data["status"], "warning")
        self.assertIn("missing TTL", data["msg"])

    def test_check_1_forces_execute_0(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET dba-test 12345", "check": 1, "execute": 1}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["code"], 2002)
        self.assertEqual(data["status"], "warning")

    def test_execute_requires_redis_info(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET k v EX 10", "check": 0, "execute": 1}
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["code"], 40004)
        self.assertEqual(data["status"], "failed")
        self.assertIn("redis_info", data["msg"])

    def test_execute_success_path_uses_tokens(self):
        fake_client = mock.MagicMock()
        fake_client.connect.return_value = (True, "Success")
        fake_client.get_server_version.return_value = "7.0.0"
        fake_client.key_exists.return_value = False
        fake_client.execute.return_value = (True, "OK")

        with mock.patch.object(app_module, "RedisClient", return_value=fake_client):
            resp = self.client.post(
                "/audit",
                json={
                    "command": "SET k v EX 10",
                    "check": 0,
                    "execute": 1,
                    "redis_info": {"host": "127.0.0.1", "port": 6379}
                }
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["code"], 0)
        self.assertEqual(data["status"], "passed")
        self.assertIn("执行成功", data["msg"])
        self.assertIn("OK", data["msg"])

    def test_check_pass_message(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET app:k v EX 10", "check": 1}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["code"], 0)
        self.assertEqual(data["status"], "passed")
        self.assertIn("命令审批正常", data["msg"])
