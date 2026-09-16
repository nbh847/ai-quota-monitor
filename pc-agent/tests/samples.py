"""CP1/CP2 共享的固定样例数据。

样例字段取自 2026-09-15 本机只读探测确认的协议结构；
不包含任何账号、Token 或原始响应内容。
"""

PROBE_UNIX_TS = 1789462530      # 探测当日时间戳（仅用于固定样例）
RESET_PRIMARY_AT = 1789465966
RESET_SECONDARY_AT = 1789815007


def account_ok_result():
    return {"account": {"type": "chatgpt", "email": "user@example.com",
                        "planType": "plus"},
            "requiresOpenaiAuth": True}


def rate_limits_result(primary_used=40, secondary_used=91,
                       primary_mins=300, secondary_mins=10080,
                       include_secondary=True):
    """构造 rateLimits/read 的 result；仅保留归一化涉及的窗口字段。"""
    primary = {"usedPercent": primary_used,
               "windowDurationMins": primary_mins,
               "resetsAt": RESET_PRIMARY_AT}
    result = {
        "rateLimitsByLimitId": {
            "codex": {
                "limitId": "codex",
                "planType": "plus",
                "primary": primary,
                "secondary": None,
            },
        },
    }
    if include_secondary:
        result["rateLimitsByLimitId"]["codex"]["secondary"] = {
            "usedPercent": secondary_used,
            "windowDurationMins": secondary_mins,
            "resetsAt": RESET_SECONDARY_AT,
        }
    return result


def jsonrpc_response(rid, result):
    import json
    return json.dumps({"jsonrpc": "2.0", "id": rid, "result": result})

# ---- 智谱 quota/limit 固定样例（字段取自 2026-09-16 冻结的协议） ----

ZHIPU_RESET_5H_MS = 1789470000000      # 毫秒时间戳样例（仅用于固定样例）
ZHIPU_RESET_1W_MS = 1789940000000
ZHIPU_RESET_5H_SEC = 1789470000
ZHIPU_RESET_1W_SEC = 1789940000


def zhipu_limit_item(unit, percentage, next_reset_ms, item_type="TOKENS_LIMIT"):
    return {"type": item_type, "unit": unit, "percentage": percentage,
            "nextResetTime": next_reset_ms}


def zhipu_quota_result(level="pro", limits=None):
    """构造智谱 quota/limit 响应；默认含 MCP 条目夹在两条 Token 窗口之间。"""
    if limits is None:
        limits = [
            zhipu_limit_item(3, 40, ZHIPU_RESET_5H_MS),
            zhipu_limit_item(5, 10, ZHIPU_RESET_1W_MS, item_type="TIME_LIMIT"),
            zhipu_limit_item(6, 90, ZHIPU_RESET_1W_MS),
        ]
    return {"data": {"level": level, "limits": limits}}
