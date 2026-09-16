"""HTTP 契约测试：字段、类型、状态码与敏感字段白名单。"""

import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from monitor import AGENT_NAME, AGENT_VERSION, make_handler
from quotas import QuotaCache
from zhipu_client import ZhipuConfig, ZhipuConfigError
from zhipu_quotas import ZhipuCache

from tests.samples import (account_ok_result, rate_limits_result,
                           zhipu_quota_result)
from tests.test_quotas import FakeClock, FakeClient
from tests.test_zhipu_quotas import FakeDiscover, FakeFetch, VALID_CONFIG


def build_running_server(codex_cache, zhipu_cache):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(codex_cache, zhipu_cache, lambda msg: None))
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
        cls.codex_cache = QuotaCache(lambda: client, epoch=cls.clock.epoch,
                                     monotonic=cls.clock.monotonic,
                                     poll_interval=0.05, stale_after=60)
        cls.zhipu_cache = ZhipuCache(fetch=FakeFetch(),
                                     discover=FakeDiscover(),
                                     epoch=cls.clock.epoch,
                                     monotonic=cls.clock.monotonic,
                                     poll_interval=0.05, stale_after=60)
        cls.codex_cache.start()
        cls.zhipu_cache.start()

        for _ in range(100):
            if (cls.codex_cache.current_status() == "ok"
                    and cls.zhipu_cache.current_status() == "ok"):
                break
            time.sleep(0.01)
        cls.server, cls.thread = build_running_server(cls.codex_cache,
                                                      cls.zhipu_cache)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.codex_cache.stop()
        cls.zhipu_cache.stop()

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

    def test_zhipu_endpoint_contract(self):
        status, content_type, text = http_get(f"{self.base}/api/v1/quotas/zhipu")
        self.assertEqual(status, 200)
        self.assertIn("application/json", content_type)
        body = json.loads(text)

        self.assertEqual(body["provider_id"], "zhipu")
        self.assertEqual(body["plan"], "pro")
        self.assertEqual(body["status"], "ok")
        self.assertIsInstance(body["updated_at_epoch"], int)
        self.assertRegex(body["updated_at_local"], r"^\d{2}:\d{2}$")
        self.assertIsNone(body["message"])

        labels = [window["label"] for window in body["windows"]]
        self.assertEqual(labels, ["5H", "1W"])
        for window in body["windows"]:
            self.assertIsInstance(window["remaining_percent"], int)
            self.assertTrue(0 <= window["remaining_percent"] <= 100)
            self.assertIsInstance(window["resets_at"], int)
            self.assertIsInstance(window["reset_at_local"], str)

    def test_both_endpoints_independent(self):
        # 同一 Agent 上两个端点同时可用，各自携带自己的 provider 标识。
        _, _, codex_text = http_get(f"{self.base}/api/v1/quotas/codex")
        _, _, zhipu_text = http_get(f"{self.base}/api/v1/quotas/zhipu")
        codex = json.loads(codex_text)
        zhipu = json.loads(zhipu_text)
        self.assertEqual(codex["provider_id"], "codex")
        self.assertEqual(zhipu["provider_id"], "zhipu")
        self.assertEqual(codex["status"], "ok")
        self.assertEqual(zhipu["status"], "ok")

    def test_no_sensitive_fields_in_response(self):
        for path in ("/api/v1/quotas/codex", "/api/v1/quotas/zhipu"):
            _, _, text = http_get(f"{self.base}{path}")
            lowered = text.lower()
            for forbidden in ("accountid", "email", "token", "cookie",
                              "ratelimits", "credits", "resetsat",
                              "usedpercent", "apikey", "authorization",
                              "nextresettime", "percentage", "limits"):
                self.assertNotIn(forbidden, lowered,
                                 f"sensitive field leaked in {path}: {forbidden}")

    def test_health_endpoint(self):
        status, _, text = http_get(f"{self.base}/api/v1/health")
        self.assertEqual(status, 200)
        body = json.loads(text)
        self.assertTrue(body["ok"])
        self.assertEqual(body["agent"], AGENT_NAME)
        self.assertEqual(body["version"], AGENT_VERSION)
        self.assertEqual(AGENT_VERSION, "0.2.0")

    def test_unknown_path_404(self):
        status, _, text = http_get(f"{self.base}/unknown")
        self.assertEqual(status, 404)
        self.assertIn("not found", text)

    def test_query_string_ignored(self):
        status, _, _ = http_get(f"{self.base}/api/v1/quotas/codex?x=1")
        self.assertEqual(status, 200)
        status, _, _ = http_get(f"{self.base}/api/v1/quotas/zhipu?x=1")
        self.assertEqual(status, 200)


class ProviderIsolationHttpTest(unittest.TestCase):
    """单侧失败隔离：智谱不可用时 Codex 端点不受影响。"""

    @classmethod
    def setUpClass(cls):
        cls.clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cls.codex_cache = QuotaCache(lambda: client, epoch=cls.clock.epoch,
                                     monotonic=cls.clock.monotonic,
                                     poll_interval=0.05, stale_after=60)
        broken_discover = FakeDiscover(error=ZhipuConfigError(
            "zhipu credentials missing or invalid in pc-agent/config.json"))
        cls.zhipu_cache = ZhipuCache(fetch=FakeFetch(),
                                     discover=broken_discover,
                                     epoch=cls.clock.epoch,
                                     monotonic=cls.clock.monotonic,
                                     poll_interval=0.05, stale_after=60)
        cls.codex_cache.start()
        cls.zhipu_cache.start()
        for _ in range(100):
            if (cls.codex_cache.current_status() == "ok"
                    and cls.zhipu_cache.current_status() == "auth_required"):
                break
            time.sleep(0.01)
        cls.server, cls.thread = build_running_server(cls.codex_cache,
                                                      cls.zhipu_cache)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.codex_cache.stop()
        cls.zhipu_cache.stop()

    def test_codex_ok_while_zhipu_auth_required(self):
        _, _, codex_text = http_get(f"{self.base}/api/v1/quotas/codex")
        _, _, zhipu_text = http_get(f"{self.base}/api/v1/quotas/zhipu")
        self.assertEqual(json.loads(codex_text)["status"], "ok")
        self.assertEqual(json.loads(zhipu_text)["status"], "auth_required")


if __name__ == "__main__":
    unittest.main()
