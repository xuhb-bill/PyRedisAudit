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

    def test_check_defaults_to_1_execute_defaults_to_0(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET dba-test 12345"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["check"], 1)
        self.assertEqual(data["execute"], 0)
        self.assertEqual(data["results"][0]["syntax"]["status"], "passed")
        self.assertIn("audit", data["results"][0])

    def test_check_1_forces_execute_0(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET dba-test 12345", "check": 1, "execute": 1}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["check"], 1)
        self.assertEqual(data["execute"], 0)
        self.assertNotIn("execute", data["results"][0])

    def test_execute_requires_redis_info(self):
        resp = self.client.post(
            "/audit",
            json={"command": "SET k v EX 10", "check": 0, "execute": 1}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("redis_info", resp.get_json()["error"])

    def test_execute_success_path_uses_tokens(self):
        fake_client = mock.MagicMock()
        fake_client.connect.return_value = (True, "Success")
        fake_client.get_server_version.return_value = "7.0.0"
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
        self.assertEqual(data["check"], 0)
        self.assertEqual(data["execute"], 1)
        self.assertEqual(data["target_redis_version"], "7.0.0")
        self.assertEqual(data["results"][0]["execute"]["status"], "succeeded")
