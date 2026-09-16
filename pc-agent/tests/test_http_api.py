"""HTTP 契约测试：字段、类型、状态码与敏感字段白名单。"""

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from monitor import AGENT_NAME, make_handler
from quotas import QuotaCache

from tests.samples import account_ok_result, rate_limits_result
from tests.test_quotas import FakeClock, FakeClient


def build_running_server(cache):
    server = ThreadingHTTPServer(("127.0.0.1", 0),
                                 make_handler(cache, lambda msg: None))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.headers.get("Content-Type"), \
                response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type"), exc.read().decode("utf-8")


class HttpApiTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cls.cache = QuotaCache(lambda: client, epoch=cls.clock.epoch,
                               monotonic=cls.clock.monotonic,
                               poll_interval=0.05, stale_after=60)
        cls.cache.start()

        import time
        for _ in range(100):
            if cls.cache.current_status() == "ok":
                break
            time.sleep(0.01)
        cls.server, cls.thread = build_running_server(cls.cache)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.cache.stop()

    def test_codex_endpoint_contract(self):
        status, content_type, text = http_get(f"{self.base}/api/v1/quotas/codex")
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        body = json.loads(text)

        self.assertEqual(body["provider_id"], "codex")
        self.assertEqual(body["provider_name"], "Codex")
        self.assertEqual(body["plan"], "plus")
        self.assertEqual(body["status"], "ok")
        self.assertIsInstance(body["windows"], list)
        self.assertEqual(len(body["windows"]), 2)
        self.assertIsInstance(body["updated_at_epoch"], int)
        self.assertRegex(body["updated_at_local"], r"^\d{2}:\d{2}$")
        self.assertIsInstance(body["age_sec"], (int, float))
        self.assertIsNone(body["message"])

        for window in body["windows"]:
            self.assertIsInstance(window["label"], str)
            self.assertIsInstance(window["remaining_percent"], int)
            self.assertTrue(0 <= window["remaining_percent"] <= 100)
            self.assertIsInstance(window["resets_at"], int)
            self.assertIsInstance(window["reset_in_sec"], int)
            self.assertIsInstance(window["reset_at_local"], str)

        labels = [window["label"] for window in body["windows"]]
        self.assertEqual(labels, ["5H", "7D"])

    def test_no_sensitive_fields_in_response(self):
        _, _, text = http_get(f"{self.base}/api/v1/quotas/codex")
        lowered = text.lower()
        for forbidden in ("accountid", "email", "token", "cookie",
                          "ratelimits", "credits", "resetsat", "usedpercent"):
            self.assertNotIn(forbidden, lowered,
                             f"sensitive field leaked: {forbidden}")

    def test_health_endpoint(self):
        status, _, text = http_get(f"{self.base}/api/v1/health")
        self.assertEqual(status, 200)
        body = json.loads(text)
        self.assertTrue(body["ok"])
        self.assertEqual(body["agent"], AGENT_NAME)

    def test_unknown_path_404(self):
        status, _, text = http_get(f"{self.base}/unknown")
        self.assertEqual(status, 404)
        self.assertIn("not found", text)

    def test_query_string_ignored(self):
        status, _, _ = http_get(f"{self.base}/api/v1/quotas/codex?x=1")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
