"""智谱额度查询客户端：配置发现、HTTPS 查询与响应归一化。

协议参考 goals/references/glm-query-usage.mjs 快照（2026-09-16 实测冻结）；
生产链路使用本模块的原生 Python 实现。所有错误消息不携带 Token、
真实网络地址或原始响应内容。
"""

import http.client
import json
import math
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REQUEST_TIMEOUT_SEC = 15.0

QUOTA_LIMIT_PATH = "/api/monitor/usage/quota/limit"

# v0.2 验收域名冻结：api.z.ai 未经本项目独立真实验证，不声明支持。
VALID_HOSTS = ("open.bigmodel.cn", "dev.bigmodel.cn")

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")
SOURCE_PROJECT_CONFIG = "project-config"

# unit 枚举由真实只读查询冻结：TOKENS_LIMIT unit=3 为 5 小时窗口，
# unit=6 为每周窗口。未知 unit 显式降级，不靠数组顺序、number 或
# 重置时间大小推断窗口类型。
TOKEN_WINDOW_UNITS = ((3, "5H"), (6, "1W"))


class ZhipuConfigError(Exception):
    """配置缺失、无效或指向未知域名（对应 auth_required）。"""


class ZhipuAuthError(Exception):
    """服务端拒绝凭据：HTTP 401/403（对应 auth_required）。"""


class ZhipuUnavailableError(Exception):
    """网络错误、超时、限流或服务端错误（对应 unavailable）。"""


class ZhipuDataError(Exception):
    """响应不是 JSON 或缺少必要字段（对应 invalid_data）。"""


class ZhipuConfig:
    """已验证的智谱配置：完整端点、Token 与来源。"""

    __slots__ = ("endpoint", "token", "source")

    def __init__(self, endpoint, token, source):
        self.endpoint = endpoint
        self.token = token
        self.source = source


def _origin(base_url):
    """校验 base_url 并返回 {scheme}://{host}；无效或未知域名返回 None。

    只接受 https 与冻结的验收域名；拒绝明文与任意子域，防止误把
    相似域名当作智谱端点。
    """
    if not isinstance(base_url, str) or not base_url:
        return None
    try:
        parts = urlsplit(base_url)
    except ValueError:
        return None
    if parts.scheme != "https" or parts.hostname is None:
        return None
    host = parts.hostname.lower()
    if host not in VALID_HOSTS:
        return None
    return f"https://{host}"


def _read_json(path):
    """读取 JSON 文件；损坏或不可读时返回 None，由上层回落下一来源。"""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _from_config_values(base_url, token):
    origin = _origin(base_url)
    if (origin is None or not isinstance(token, str) or not token
            or token == "YOUR_ZHIPU_API_KEY"):
        return None
    return ZhipuConfig(origin + QUOTA_LIMIT_PATH, token,
                        SOURCE_PROJECT_CONFIG)


def discover_config(config_path=None):
    """从 PC Agent 项目本地配置读取智谱凭据。

    默认读取与本模块相邻的 config.json。该真实配置被 Git 忽略，
    config.example.json 仅提供无凭据模板。
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    raw = _read_json(path)
    zhipu = raw.get("zhipu") if isinstance(raw, dict) else None
    config = (_from_config_values(zhipu.get("base_url"),
                                  zhipu.get("api_key"))
              if isinstance(zhipu, dict) else None)
    if config is None:
        raise ZhipuConfigError(
            "zhipu credentials missing or invalid in pc-agent/config.json")
    return config


def fetch_quota_limit(config, timeout=REQUEST_TIMEOUT_SEC, urlopen=None):
    """GET quota/limit 并解析 JSON；错误消息不携带 Token 或响应体。"""
    opener = urlopen if urlopen is not None else urllib.request.urlopen
    request = urllib.request.Request(
        config.endpoint,
        headers={
            "Authorization": config.token,
            "Accept-Language": "en-US,en",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ZhipuAuthError(f"zhipu api rejected credentials: http {exc.code}") from exc
        raise ZhipuUnavailableError(f"zhipu api http error: {exc.code}") from exc
    except (urllib.error.URLError, http.client.HTTPException, OSError,
            ValueError) as exc:
        raise ZhipuUnavailableError(
            f"zhipu api request failed: {exc.__class__.__name__}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ZhipuDataError("zhipu response is not valid json") from exc


def _valid_percent(value):
    """已用比例必须是有限数值；bool 在 Python 中是 int 子类，显式排除。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _valid_reset_ms(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value) and value > 0


def normalize_zhipu_quota(payload):
    """归一化 quota/limit 响应为统一快照；无有效 Token 窗口抛 ZhipuDataError。

    只读取 data.level 与 data.limits[] 的 type、unit、percentage、
    nextResetTime。MCP（TIME_LIMIT）与未知 type/unit 条目跳过；窗口输出
    顺序固定为 5H、1W，不依赖数组顺序。nextResetTime 为毫秒时间戳，
    转换为 Unix 秒。
    """
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = payload if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ZhipuDataError("zhipu quota payload missing data object")

    level = data.get("level")
    plan = level if isinstance(level, str) else None

    limits = data.get("limits")
    if not isinstance(limits, list):
        raise ZhipuDataError("zhipu quota payload missing limits array")

    windows = []
    for unit, label in TOKEN_WINDOW_UNITS:
        for item in limits:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "TOKENS_LIMIT":
                continue
            if item.get("unit") != unit:
                continue
            used = item.get("percentage")
            if not _valid_percent(used):
                continue
            reset_ms = item.get("nextResetTime")
            resets_at = (int(reset_ms // 1000)
                         if _valid_reset_ms(reset_ms) else None)
            remaining = max(0, min(100, round(100 - used)))
            windows.append({"label": label, "remaining_percent": remaining,
                            "resets_at": resets_at})
            break

    if not windows:
        raise ZhipuDataError("no valid zhipu token quota window")
    return {"plan": plan, "windows": windows}
