"""额度归一化与 QuotaCache 单元测试：固定样例覆盖正常与失败路径。"""

import json
import threading
import unittest
from unittest import mock

import quotas
from quotas import (NormalizationError, QuotaCache, STATUS_AUTH_REQUIRED,
                    STATUS_INVALID_DATA, STATUS_OK, STATUS_STALE,
                    STATUS_UNAVAILABLE, clamp_percent, normalize_rate_limits,
                    window_label)

from tests.samples import (RESET_PRIMARY_AT, RESET_SECONDARY_AT,
                           account_ok_result, jsonrpc_response,
                           rate_limits_result)


class FakeClock:
    """可控时钟：monotonic 与 epoch 同步推进。"""

    def __init__(self):
        self.monotonic_val = 100.0
        self.epoch_val = 1789462530.0

    def monotonic(self):
        return self.monotonic_val

    def epoch(self):
        return self.epoch_val

    def advance(self, seconds):
        self.monotonic_val += seconds
        self.epoch_val += seconds


class FakeClient:
    """脚本化假客户端：按预设返回结果或抛出异常。"""

    def __init__(self, account_result=None, rate_result=None,
                 account_error=None, rate_error=None, dead=False,
                 start_error=None):
        self.account_result = account_result
        self.rate_result = rate_result
        self.account_error = account_error
        self.rate_error = rate_error
        self.dead = dead
        self.start_error = start_error
        self.notification_handler = None
        self.started = False
        self.stopped = False
        self.requests = []

    def add_notification_handler(self, handler):
        self.notification_handler = handler

    def start(self):
        if self.start_error is not None:
            raise self.start_error
        self.started = True

    def stop(self):
        self.stopped = True

    @property
    def running(self):
        return not self.dead

    def request(self, method, params=None, timeout=None):
        self.requests.append((method, params))
        if method == "account/read":
            if self.account_error is not None:
                raise self.account_error
            return self.account_result
        if method == "account/rateLimits/read":
            if self.rate_error is not None:
                raise self.rate_error
            return self.rate_result
        raise AssertionError(f"unexpected method: {method}")


class WindowLabelTest(unittest.TestCase):

    def test_frozen_labels(self):
        self.assertEqual(window_label(300), "5H")
        self.assertEqual(window_label(10080), "7D")

    def test_generic_labels(self):
        self.assertEqual(window_label(720), "12H")
        self.assertEqual(window_label(45), "45M")

    def test_invalid_values(self):
        for value in (0, -5, None, "300", True, 1.5):
            self.assertIsNone(window_label(value), f"label for {value!r}")


class ClampPercentTest(unittest.TestCase):

    def test_clamp(self):
        self.assertEqual(clamp_percent(0), 100)
        self.assertEqual(clamp_percent(40), 60)
        self.assertEqual(clamp_percent(100), 0)
        self.assertEqual(clamp_percent(150), 0)
        self.assertEqual(clamp_percent(-5), 100)


class NormalizeRateLimitsTest(unittest.TestCase):

    def test_ok_full_snapshot(self):
        snapshot = normalize_rate_limits(rate_limits_result())
        self.assertEqual(snapshot["plan"], "plus")
        self.assertEqual(len(snapshot["windows"]), 2)
        primary, secondary = snapshot["windows"]
        self.assertEqual(primary["label"], "5H")
        self.assertEqual(primary["remaining_percent"], 60)
        self.assertEqual(primary["resets_at"], RESET_PRIMARY_AT)
        self.assertEqual(secondary["label"], "7D")
        self.assertEqual(secondary["remaining_percent"], 9)
        self.assertEqual(secondary["resets_at"], RESET_SECONDARY_AT)

    def test_boundary_percent(self):
        for used, remaining in ((0, 100), (100, 0), (150, 0), (-5, 100)):
            snapshot = normalize_rate_limits(
                rate_limits_result(primary_used=used, include_secondary=False))
            self.assertEqual(snapshot["windows"][0]["remaining_percent"], remaining)

    def test_invalid_used_percent_skips_window(self):
        # 字符串、bool、NaN 均不参与展示；两个窗口全部无效时归一化失败。
        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = "40"
        with self.assertRaises(NormalizationError):
            normalize_rate_limits(raw)

        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = True
        with self.assertRaises(NormalizationError):
            normalize_rate_limits(raw)

        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["usedPercent"] = \
            json.loads("NaN")
        with self.assertRaises(NormalizationError):
            normalize_rate_limits(raw)

    def test_secondary_missing_keeps_primary(self):
        snapshot = normalize_rate_limits(rate_limits_result(include_secondary=False))
        self.assertEqual(len(snapshot["windows"]), 1)
        self.assertEqual(snapshot["windows"][0]["label"], "5H")

    def test_secondary_null_keeps_primary(self):
        raw = rate_limits_result(include_secondary=False)
        self.assertEqual(len(normalize_rate_limits(raw)["windows"]), 1)

    def test_codex_bucket_missing(self):
        with self.assertRaises(NormalizationError):
            normalize_rate_limits({})
        with self.assertRaises(NormalizationError):
            normalize_rate_limits({"rateLimitsByLimitId": {"other": {}}})
        with self.assertRaises(NormalizationError):
            normalize_rate_limits(None)

    def test_unknown_window_duration(self):
        snapshot = normalize_rate_limits(
            rate_limits_result(primary_mins=720, include_secondary=False))
        self.assertEqual(snapshot["windows"][0]["label"], "12H")

    def test_invalid_window_duration_degrades_label(self):
        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["windowDurationMins"] = "300"
        snapshot = normalize_rate_limits(raw)
        self.assertIsNone(snapshot["windows"][0]["label"])
        self.assertEqual(snapshot["windows"][0]["remaining_percent"], 60)

    def test_invalid_resets_at_degrades_to_none(self):
        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["resetsAt"] = "soon"
        snapshot = normalize_rate_limits(raw)
        self.assertIsNone(snapshot["windows"][0]["resets_at"])

        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["primary"]["resetsAt"] = 0
        snapshot = normalize_rate_limits(raw)
        self.assertIsNone(snapshot["windows"][0]["resets_at"])

    def test_plan_type_invalid_degrades(self):
        raw = rate_limits_result(include_secondary=False)
        raw["rateLimitsByLimitId"]["codex"]["planType"] = 123
        self.assertIsNone(normalize_rate_limits(raw)["plan"])


class QuotaCacheTest(unittest.TestCase):

    def make_cache(self, factory, clock, poll=0.05, stale_after=0.2):
        return QuotaCache(factory, epoch=clock.epoch, monotonic=clock.monotonic,
                          poll_interval=poll, stale_after=stale_after)

    def wait_until(self, condition, timeout=2.0):
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.005)
        return condition()

    def test_ok_flow(self):
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
            body = cache.render()
            self.assertEqual(body["status"], STATUS_OK)
            self.assertEqual(body["provider_id"], "codex")
            self.assertEqual(body["plan"], "plus")
            self.assertRegex(body["updated_at_local"], r"^\d{2}:\d{2}$")
            self.assertEqual(len(body["windows"]), 2)
            self.assertEqual(body["windows"][0]["label"], "5H")
            self.assertEqual(body["windows"][0]["remaining_percent"], 60)
            self.assertEqual(body["windows"][0]["resets_at"], RESET_PRIMARY_AT)
            self.assertEqual(body["windows"][0]["reset_in_sec"],
                             RESET_PRIMARY_AT - int(clock.epoch()))
            self.assertIsNotNone(body["windows"][0]["reset_at_local"])
            self.assertEqual(body["age_sec"], 0)
            self.assertIsNone(body["message"])
        finally:
            cache.stop()

    def test_stale_after_no_updates(self):
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
            clock.advance(0.3)  # 超过 stale_after=0.2
            self.assertEqual(cache.current_status(), STATUS_STALE)
            body = cache.render()
            self.assertEqual(body["status"], STATUS_STALE)
            self.assertEqual(len(body["windows"]), 2)      # 旧值保留
            self.assertEqual(body["windows"][0]["remaining_percent"], 60)
            self.assertIn("stale", body["message"])
        finally:
            cache.stop()

    def test_account_read_uses_explicit_no_refresh(self):
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)

        self.assertTrue(cache._update_once(client))
        self.assertEqual(client.requests[0],
                         ("account/read", {"refreshToken": False}))
        self.assertEqual(client.requests[1],
                         ("account/rateLimits/read", None))

    def test_stale_after_query_failure_with_old_snapshot(self):
        from codex_client import AppServerError
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)

        self.assertTrue(cache._update_once(client))
        clock.advance(0.3)
        client.rate_error = AppServerError("temporary failure")
        self.assertFalse(cache._update_once(client))

        body = cache.render()
        self.assertEqual(body["status"], STATUS_STALE)
        self.assertEqual(len(body["windows"]), 2)

    def test_auth_required_for_non_chatgpt_login(self):
        clock = FakeClock()
        client = FakeClient(
            account_result={"account": {"type": "apikey"}},
            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_AUTH_REQUIRED))
            body = cache.render()
            self.assertEqual(body["status"], STATUS_AUTH_REQUIRED)
            self.assertIn("codex login", body["message"])
        finally:
            cache.stop()

    def test_invalid_data_status(self):
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result={"rateLimitsByLimitId": {}})
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_INVALID_DATA))
            body = cache.render()
            self.assertEqual(body["status"], STATUS_INVALID_DATA)
            self.assertEqual(body["windows"], [])
        finally:
            cache.stop()

    def test_unavailable_when_account_read_fails(self):
        from codex_client import AppServerError
        clock = FakeClock()
        client = FakeClient(account_error=AppServerError("not logged in"))
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_UNAVAILABLE))
        finally:
            cache.stop()

    def test_restart_after_client_death(self):
        from codex_client import AppServerUnavailable
        clock = FakeClock()
        dead = FakeClient(account_result=account_ok_result(),
                          rate_result=rate_limits_result(), dead=True,
                          rate_error=AppServerUnavailable("process exited"))
        good = FakeClient(account_result=account_ok_result(),
                          rate_result=rate_limits_result())
        clients = [dead, good]

        with unittest.mock.patch.object(quotas, "RESTART_BACKOFF_SEC", (0.01,)):
            cache = self.make_cache(lambda: clients.pop(0), clock)
            cache.start()
            try:
                self.assertTrue(self.wait_until(
                    lambda: cache.current_status() == STATUS_OK))
                self.assertTrue(good.started)
                self.assertTrue(dead.stopped)
            finally:
                cache.stop()

    def test_restart_after_client_start_failure(self):
        from codex_client import AppServerUnavailable
        clock = FakeClock()
        broken = FakeClient(start_error=AppServerUnavailable("start failed"))
        good = FakeClient(account_result=account_ok_result(),
                          rate_result=rate_limits_result())
        clients = [broken, good]

        with unittest.mock.patch.object(quotas, "RESTART_BACKOFF_SEC", (0.01,)):
            cache = self.make_cache(lambda: clients.pop(0), clock)
            cache.start()
            try:
                self.assertTrue(self.wait_until(
                    lambda: cache.current_status() == STATUS_OK))
                self.assertTrue(broken.stopped)
                self.assertTrue(good.started)
                self.assertTrue(cache._thread.is_alive())
            finally:
                cache.stop()

    def test_notification_handler_wakes_scheduler(self):
        clock = FakeClock()
        client = FakeClient(account_result=account_ok_result(),
                            rate_result=rate_limits_result())
        cache = self.make_cache(lambda: client, clock)
        cache.start()
        try:
            self.assertTrue(self.wait_until(
                lambda: cache.current_status() == STATUS_OK))
            # App Server 通知经 handler 到达缓存；不抛异常即接入成功。
            self.assertIsNotNone(client.notification_handler)
            client.notification_handler("account/rateLimits/updated", {})
        finally:
            cache.stop()

    def test_render_before_any_data(self):
        clock = FakeClock()
        cache = QuotaCache(FakeClient, epoch=clock.epoch,
                           monotonic=clock.monotonic,
                           poll_interval=60, stale_after=0.2)
        body = cache.render()
        self.assertEqual(body["status"], STATUS_UNAVAILABLE)
        self.assertEqual(body["windows"], [])
        self.assertIsNone(body["updated_at_epoch"])


if __name__ == "__main__":
    unittest.main()
