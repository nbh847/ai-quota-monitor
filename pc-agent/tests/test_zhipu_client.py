"""智谱客户端单元测试：配置发现、HTTP 请求与响应归一化。"""

import json
import pathlib
import tempfile
import unittest
import urllib.error

from zhipu_client import (ZhipuAuthError, ZhipuConfig, ZhipuConfigError,
                          ZhipuDataError, ZhipuUnavailableError,
                          discover_config, fetch_quota_limit,
                          normalize_zhipu_quota)

from tests.samples import (ZHIPU_RESET_5H_MS, ZHIPU_RESET_5H_SEC,
                           ZHIPU_RESET_1W_MS, ZHIPU_RESET_1W_SEC,
                           zhipu_limit_item, zhipu_quota_result)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        path.write_text("{not valid json", encoding="utf-8")
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


class FakeResponse:
    def __init__(self, body=b"{}"):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RecordingOpener:
    """记录请求并按脚本返回结果或异常的假 urlopen。"""

    def __init__(self, body=b"{}", status=200, error=None):
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.status = status
        self.error = error
        self.calls = []

    def __call__(self, request, timeout=None):
        self.calls.append({"url": request.full_url,
                           "headers": dict(request.header_items()),
                           "method": request.get_method(),
                           "timeout": timeout})
        if self.error is not None:
            raise self.error
        return FakeResponse(self.body)


def http_error(code):
    return urllib.error.HTTPError("https://open.bigmodel.cn", code, "err",
                                  hdrs=None, fp=None)


class DiscoverConfigTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    @property
    def config_path(self):
        return self.home / "config.json"

    def test_project_config_is_loaded(self):
        write_json(self.config_path, {
            "zhipu": {
                "base_url": "https://open.bigmodel.cn/api/anthropic",
                "api_key": "sample-key",
            }
        })
        config = discover_config(config_path=self.config_path)
        self.assertEqual(config.source, "project-config")
        self.assertEqual(config.endpoint,
                         "https://open.bigmodel.cn/api/monitor/usage/quota/limit")

    def test_dev_domain_is_supported(self):
        write_json(self.config_path, {
            "zhipu": {
                "base_url": "https://dev.bigmodel.cn/api/anthropic",
                "api_key": "sample-key",
            }
        })
        config = discover_config(config_path=self.config_path)
        self.assertIn("dev.bigmodel.cn", config.endpoint)

    def test_missing_file_raises(self):
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_corrupt_json_raises(self):
        write_json(self.config_path, None)
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_unknown_domain_rejected(self):
        # 所有来源都因域名校验失败后应抛错；z.ai 未验收，不声明支持。
        write_json(self.config_path, {
            "zhipu": {
                "base_url": "https://api.z.ai/api/anthropic",
                "api_key": "sample-key",
            }
        })
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_missing_token_raises(self):
        write_json(self.config_path, {
            "zhipu": {
                "base_url": "https://open.bigmodel.cn/api/anthropic"
            }
        })
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_template_token_raises(self):
        write_json(self.config_path, {
            "zhipu": {
                "base_url": "https://open.bigmodel.cn/api/anthropic",
                "api_key": "YOUR_ZHIPU_API_KEY",
            }
        })
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_missing_base_url_raises(self):
        write_json(self.config_path, {
            "zhipu": {"api_key": "sample-key"}
        })
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)

    def test_missing_zhipu_section_raises(self):
        write_json(self.config_path, {"other": {}})
        with self.assertRaises(ZhipuConfigError):
            discover_config(config_path=self.config_path)


class FetchQuotaLimitTest(unittest.TestCase):

    def make_config(self):
        return ZhipuConfig("https://open.bigmodel.cn/api/monitor/usage/quota/limit",
                           "sample-key", "environment")

    def test_request_headers_and_timeout(self):
        opener = RecordingOpener(body=json.dumps(zhipu_quota_result()))
        config = self.make_config()
        fetch_quota_limit(config, timeout=7.5, urlopen=opener)
        call = opener.calls[0]
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["timeout"], 7.5)
        headers = {name.lower(): value
                   for name, value in call["headers"].items()}
        # Authorization 直接放 Token，不添加 Bearer。
        self.assertEqual(headers["authorization"], "sample-key")
        self.assertEqual(headers["accept-language"], "en-US,en")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertNotIn("bearer", headers["authorization"].lower())

    def test_success_returns_parsed_json(self):
        opener = RecordingOpener(body=json.dumps(zhipu_quota_result()))
        payload = fetch_quota_limit(self.make_config(), urlopen=opener)
        self.assertEqual(payload["data"]["level"], "pro")

    def test_401_403_maps_to_auth_error(self):
        for code in (401, 403):
            opener = RecordingOpener(error=http_error(code))
            with self.assertRaises(ZhipuAuthError):
                fetch_quota_limit(self.make_config(), urlopen=opener)

    def test_429_and_5xx_map_to_unavailable(self):
        for code in (429, 500, 503):
            opener = RecordingOpener(error=http_error(code))
            with self.assertRaises(ZhipuUnavailableError):
                fetch_quota_limit(self.make_config(), urlopen=opener)

    def test_timeout_maps_to_unavailable(self):
        opener = RecordingOpener(error=TimeoutError("timed out"))
        with self.assertRaises(ZhipuUnavailableError):
            fetch_quota_limit(self.make_config(), urlopen=opener)

    def test_network_error_maps_to_unavailable(self):
        opener = RecordingOpener(
            error=urllib.error.URLError("connection refused"))
        with self.assertRaises(ZhipuUnavailableError):
            fetch_quota_limit(self.make_config(), urlopen=opener)

    def test_invalid_json_maps_to_data_error(self):
        opener = RecordingOpener(body="<html>gateway</html>")
        with self.assertRaises(ZhipuDataError):
            fetch_quota_limit(self.make_config(), urlopen=opener)


class NormalizeZhipuQuotaTest(unittest.TestCase):

    def test_ok_full_snapshot(self):
        snapshot = normalize_zhipu_quota(zhipu_quota_result())
        self.assertEqual(snapshot["plan"], "pro")
        five_hour, weekly = snapshot["windows"]
        self.assertEqual(five_hour["label"], "5H")
        self.assertEqual(five_hour["remaining_percent"], 60)
        self.assertEqual(five_hour["resets_at"], ZHIPU_RESET_5H_SEC)
        self.assertEqual(weekly["label"], "1W")
        self.assertEqual(weekly["remaining_percent"], 10)
        self.assertEqual(weekly["resets_at"], ZHIPU_RESET_1W_SEC)

    def test_out_of_order_units_keep_fixed_output_order(self):
        raw = zhipu_quota_result(limits=[
            zhipu_limit_item(6, 90, ZHIPU_RESET_1W_MS),
            zhipu_limit_item(3, 40, ZHIPU_RESET_5H_MS),
        ])
        labels = [w["label"] for w in normalize_zhipu_quota(raw)["windows"]]
        self.assertEqual(labels, ["5H", "1W"])

    def test_mcp_entry_in_between_is_skipped(self):
        raw = zhipu_quota_result(limits=[
            zhipu_limit_item(3, 40, ZHIPU_RESET_5H_MS),
            zhipu_limit_item(5, 10, ZHIPU_RESET_1W_MS, item_type="TIME_LIMIT"),
            zhipu_limit_item(6, 90, ZHIPU_RESET_1W_MS),
        ])
        labels = [w["label"] for w in normalize_zhipu_quota(raw)["windows"]]
        self.assertEqual(labels, ["5H", "1W"])

    def test_unknown_unit_and_type_are_skipped(self):
        raw = zhipu_quota_result(limits=[
            zhipu_limit_item(7, 50, ZHIPU_RESET_5H_MS),
            zhipu_limit_item("3", 50, ZHIPU_RESET_5H_MS),
            zhipu_limit_item(5, 10, ZHIPU_RESET_1W_MS, item_type="SOMETHING"),
        ])
        with self.assertRaises(ZhipuDataError):
            normalize_zhipu_quota(raw)

    def test_boundary_percent(self):
        for used, remaining in ((0, 100), (100, 0), (150, 0), (-5, 100)):
            raw = zhipu_quota_result(limits=[
                zhipu_limit_item(3, used, ZHIPU_RESET_5H_MS)])
            snapshot = normalize_zhipu_quota(raw)
            self.assertEqual(snapshot["windows"][0]["remaining_percent"],
                             remaining)

    def test_invalid_percentage_skips_window(self):
        for bad in ("40", True, None):
            raw = zhipu_quota_result(limits=[
                zhipu_limit_item(3, bad, ZHIPU_RESET_5H_MS)])
            with self.assertRaises(ZhipuDataError):
                normalize_zhipu_quota(raw)

    def test_nan_percentage_skips_window(self):
        raw = zhipu_quota_result(limits=[
            zhipu_limit_item(3, json.loads("NaN"), ZHIPU_RESET_5H_MS)])
        with self.assertRaises(ZhipuDataError):
            normalize_zhipu_quota(raw)

    def test_invalid_next_reset_degrades_to_none(self):
        for bad in ("soon", 0, True, -5):
            raw = zhipu_quota_result(limits=[
                zhipu_limit_item(3, 40, bad)])
            snapshot = normalize_zhipu_quota(raw)
            self.assertIsNone(snapshot["windows"][0]["resets_at"])

    def test_single_window_is_enough(self):
        raw = zhipu_quota_result(limits=[
            zhipu_limit_item(3, 40, ZHIPU_RESET_5H_MS)])
        snapshot = normalize_zhipu_quota(raw)
        self.assertEqual([w["label"] for w in snapshot["windows"]], ["5H"])

    def test_missing_limits_raises(self):
        with self.assertRaises(ZhipuDataError):
            normalize_zhipu_quota({"data": {"level": "pro"}})
        with self.assertRaises(ZhipuDataError):
            normalize_zhipu_quota({})
        with self.assertRaises(ZhipuDataError):
            normalize_zhipu_quota(None)

    def test_top_level_payload_without_data_wrapper(self):
        raw = {"level": "max",
               "limits": [zhipu_limit_item(3, 40, ZHIPU_RESET_5H_MS)]}
        snapshot = normalize_zhipu_quota(raw)
        self.assertEqual(snapshot["plan"], "max")
        self.assertEqual(len(snapshot["windows"]), 1)

    def test_non_string_level_degrades_to_none(self):
        raw = zhipu_quota_result(level=123)
        self.assertIsNone(normalize_zhipu_quota(raw)["plan"])


if __name__ == "__main__":
    unittest.main()
