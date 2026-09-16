"""智谱归一化缓存（ZhipuCache）单元测试：调度、状态与渲染。"""

import unittest

from quotas import (STATUS_AUTH_REQUIRED, STATUS_INVALID_DATA, STATUS_OK,
                    STATUS_STALE, STATUS_UNAVAILABLE)
from zhipu_client import ZhipuConfig, ZhipuDataError
from zhipu_quotas import ZhipuCache

from tests.samples import (ZHIPU_RESET_5H_SEC, ZHIPU_RESET_1W_SEC,
                           zhipu_quota_result)
from tests.test_quotas import FakeClock

VALID_CONFIG = ZhipuConfig(
    "https://open.bigmodel.cn/api/monitor/usage/quota/limit",
    "sample-key", "environment")


class FakeDiscover:
    """可编程配置发现：按脚本返回配置或抛错。"""

    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return VALID_CONFIG


class FakeFetch:
    """可编程查询：按脚本返回载荷或抛错。"""

    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else zhipu_quota_result()
        self.error = error
        self.calls = []

    def __call__(self, config):
        self.calls.append(config)
        if self.error is not None:
            raise self.error
        return self.payload


class ZhipuCacheTest(unittest.TestCase):

    def wait_until(self, condition, timeout=2.0):
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.005)
        return condition()

    def make_cache(self, discover=None, fetch=None, clock=None,
                   poll=0.05, stale_after=0.2):
        return ZhipuCache(fetch=fetch, discover=discover,
                          epoch=clock.epoch, monotonic=clock.monotonic,
                          poll_interval=poll, stale_after=stale_after)

    def test_ok_flow(self):
        clock = FakeClock()
        cache = self.make_cache(FakeDiscover(), FakeFetch(), clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
            body = cache.render()
            self.assertEqual(body["provider_id"], "zhipu")
            self.assertEqual(body["provider_name"], "智谱")
            self.assertEqual(body["plan"], "pro")
            self.assertEqual(body["status"], STATUS_OK)
            self.assertEqual([w["label"] for w in body["windows"]],
                             ["5H", "1W"])
            self.assertEqual(body["windows"][0]["remaining_percent"], 60)
            self.assertEqual(body["windows"][0]["resets_at"],
                             ZHIPU_RESET_5H_SEC)
            self.assertEqual(body["windows"][0]["reset_in_sec"],
                             ZHIPU_RESET_5H_SEC - int(clock.epoch()))
            self.assertIsNotNone(body["windows"][0]["reset_at_local"])
            self.assertIsNone(body["message"])
        finally:
            cache.stop()

    def test_stale_keeps_old_windows_and_recovers(self):
        from zhipu_client import ZhipuUnavailableError
        clock = FakeClock()
        fetch = FakeFetch()
        cache = self.make_cache(FakeDiscover(), fetch, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
            fetch.error = ZhipuUnavailableError("zhipu api http error: 500")
            clock.advance(0.3)  # 超过 stale_after=0.2
            self.assertEqual(cache.current_status(), STATUS_STALE)
            body = cache.render()
            self.assertEqual(body["status"], STATUS_STALE)
            self.assertEqual(len(body["windows"]), 2)  # 旧值保留
            self.assertIn("stale", body["message"])

            fetch.error = None
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
        finally:
            cache.stop()

    def test_discover_failure_is_auth_required(self):
        from zhipu_client import ZhipuConfigError
        clock = FakeClock()
        discover = FakeDiscover(error=ZhipuConfigError("zhipu credentials not found"))
        cache = self.make_cache(discover, FakeFetch(), clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_AUTH_REQUIRED))
            body = cache.render()
            self.assertEqual(body["status"], STATUS_AUTH_REQUIRED)
            self.assertEqual(body["windows"], [])
        finally:
            cache.stop()

    def test_fetch_auth_error_is_auth_required(self):
        from zhipu_client import ZhipuAuthError
        clock = FakeClock()
        cache = self.make_cache(
            FakeDiscover(),
            FakeFetch(error=ZhipuAuthError("zhipu api rejected credentials: http 401")),
            clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_AUTH_REQUIRED))
        finally:
            cache.stop()

    def test_fetch_unavailable_is_unavailable(self):
        from zhipu_client import ZhipuUnavailableError
        clock = FakeClock()
        cache = self.make_cache(
            FakeDiscover(),
            FakeFetch(error=ZhipuUnavailableError("zhipu api request failed")),
            clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_UNAVAILABLE))
        finally:
            cache.stop()

    def test_invalid_data_status(self):
        clock = FakeClock()
        cache = self.make_cache(
            FakeDiscover(), FakeFetch(payload={"data": {}}), clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_INVALID_DATA))
            body = cache.render()
            self.assertEqual(body["status"], STATUS_INVALID_DATA)
            self.assertEqual(body["windows"], [])
        finally:
            cache.stop()

    def test_render_before_any_data(self):
        clock = FakeClock()
        cache = self.make_cache(FakeDiscover(), FakeFetch(), clock)
        body = cache.render()
        self.assertEqual(body["status"], STATUS_UNAVAILABLE)
        self.assertEqual(body["windows"], [])
        self.assertIsNone(body["updated_at_epoch"])

    def test_no_token_leak_in_messages(self):
        from zhipu_client import (ZhipuAuthError, ZhipuConfigError,
                                  ZhipuUnavailableError)
        clock = FakeClock()
        cache = self.make_cache(FakeDiscover(), FakeFetch(), clock)
        for error in (ZhipuConfigError("missing"),
                      ZhipuAuthError("rejected"),
                      ZhipuUnavailableError("network"),
                      ZhipuDataError("bad data")):
            cache._set_state(STATUS_AUTH_REQUIRED, str(error))
            rendered = str(cache.render())
            self.assertNotIn("sample-key", rendered)


    def test_update_once_direct_flow(self):
        clock = FakeClock()
        discover = FakeDiscover()
        fetch = FakeFetch()
        cache = self.make_cache(discover, fetch, clock)
        self.assertTrue(cache._update_once())
        self.assertEqual(discover.calls, 1)
        self.assertEqual(fetch.calls, [VALID_CONFIG])
        self.assertEqual(cache.current_status(), STATUS_OK)


if __name__ == "__main__":
    unittest.main()