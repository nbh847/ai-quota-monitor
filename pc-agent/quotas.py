"""Codex 额度归一化、缓存与查询调度。

只读取 rateLimits/read 结果中白名单内的字段；HTTP 响应只暴露
归一化后的额度快照，绝不透传账号 ID、邮箱、Token、Cookie、
重置券或 App Server 原始响应。
"""

import math
import threading
import time

from codex_client import AppServerError, AppServerUnavailable

PROVIDER_ID = "codex"
PROVIDER_NAME = "Codex"

POLL_INTERVAL_SEC = 60.0     # 通知之外的兜底查询周期
STALE_AFTER_SEC = 180.0      # 超过该时长没有成功更新即标记 stale
RESTART_BACKOFF_SEC = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)

STATUS_OK = "ok"
STATUS_AUTH_REQUIRED = "auth_required"
STATUS_UNAVAILABLE = "unavailable"
STATUS_INVALID_DATA = "invalid_data"
STATUS_STALE = "stale"

# 2026-09-15 冻结决策：300 分钟显示 5H，10080 分钟显示 7D。
FIXED_WINDOW_LABELS = {300: "5H", 10080: "7D"}


class NormalizationError(Exception):
    """输入数据无法归一化为任何有效窗口。"""


class AppServerDown(Exception):
    """调度循环内部信号：客户端已不可用，需要重建。"""


def window_label(duration_mins):
    """窗口时长标签；未知或非法时长返回 None，由显示层降级。"""
    if not isinstance(duration_mins, int) or isinstance(duration_mins, bool):
        return None
    if duration_mins <= 0:
        return None
    fixed = FIXED_WINDOW_LABELS.get(duration_mins)
    if fixed is not None:
        return fixed
    if duration_mins % 60 == 0:
        return f"{duration_mins // 60}H"
    return f"{duration_mins}M"


def clamp_percent(value):
    """剩余比例 clamp(100 - usedPercent, 0, 100)。"""
    return max(0, min(100, 100 - value))


def _valid_number(value):
    """仅接受有限数值；bool 在 Python 中是 int 子类，必须显式排除。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _valid_timestamp(value):
    return (not isinstance(value, bool) and isinstance(value, int)
            and value > 0)


def _format_local_time(epoch_sec):
    if not _valid_timestamp(epoch_sec):
        return None
    return time.strftime("%m-%d %H:%M", time.localtime(epoch_sec))


def _format_local_hhmm(epoch_sec):
    if not _valid_timestamp(epoch_sec):
        return None
    return time.strftime("%H:%M", time.localtime(epoch_sec))


def normalize_window(raw_window):
    """归一化单个额度窗口；数值无效时返回 None（跳过该窗口）。"""
    if not isinstance(raw_window, dict):
        return None
    used = raw_window.get("usedPercent")
    if not _valid_number(used):
        return None
    label = window_label(raw_window.get("windowDurationMins"))
    resets_at = raw_window.get("resetsAt")
    if not _valid_timestamp(resets_at):
        resets_at = None
    return {
        "label": label,
        "remaining_percent": round(clamp_percent(used)),
        "resets_at": resets_at,
    }


def normalize_rate_limits(raw):
    """从 account/rateLimits/read 的 result 归一化 Codex 快照。

    只读取 rateLimitsByLimitId.codex 的 primary / secondary 两个窗口。
    主要与次要窗口全部无效时抛 NormalizationError（对应 invalid_data）；
    部分缺失时输出存在的窗口，由显示层对缺失项降级。
    """
    by_limit = raw.get("rateLimitsByLimitId") if isinstance(raw, dict) else None
    codex = by_limit.get("codex") if isinstance(by_limit, dict) else None
    if not isinstance(codex, dict):
        raise NormalizationError("codex limit bucket missing")

    plan = codex.get("planType")
    if not isinstance(plan, str):
        plan = None

    windows = []
    for name in ("primary", "secondary"):
        window = normalize_window(codex.get(name))
        if window is not None:
            windows.append(window)

    if not windows:
        raise NormalizationError("no valid quota window")
    return {"plan": plan, "windows": windows}


class BaseQuotaCache:
    """额度缓存公共骨架：状态、快照存储、stale 判定与 HTTP 渲染。

    调度循环由子类实现（_run_loop）；Codex 走 App Server 子进程调度，
    智谱走纯 HTTP 轮询，两者共享同一份统一快照契约。
    """

    provider_id = None
    provider_name = None

    def __init__(self, epoch=time.time, monotonic=time.monotonic,
                 poll_interval=POLL_INTERVAL_SEC, stale_after=STALE_AFTER_SEC):
        self._epoch = epoch
        self._monotonic = monotonic
        self._poll_interval = poll_interval
        self._stale_after = stale_after

        self._lock = threading.Lock()
        self._snapshot = None          # 最近一次成功归一化结果（含 resets_at）
        self._snapshot_at = None       # 成功时刻的 monotonic 时间
        self._updated_at_epoch = None  # 成功时刻的本机 unix 秒
        self._status = STATUS_UNAVAILABLE
        self._message = "not started"

        self._wake = threading.Event()
        self._stop_flag = False
        self._thread = None

    # ---- 生命周期 ----

    def start(self):
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"quota-scheduler-{self.provider_id}", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag = True
        self._wake.set()

    # ---- 状态与渲染 ----

    def current_status(self):
        """当前业务状态；成功快照超过 stale_after 未刷新时降级为 stale。"""
        with self._lock:
            if (self._snapshot is not None
                    and self._status in (STATUS_OK, STATUS_UNAVAILABLE,
                                         STATUS_INVALID_DATA)
                    and self._monotonic() - self._snapshot_at > self._stale_after):
                return STATUS_STALE
            return self._status

    def render(self):
        """组装 HTTP 响应。只输出白名单字段，reset_in_sec / age_sec 实时计算。"""
        status = self.current_status()
        now_epoch = int(self._epoch())
        with self._lock:
            snapshot = self._snapshot
            snapshot_at = self._snapshot_at
            updated_at = self._updated_at_epoch
            message = self._message
        if status == STATUS_STALE:
            message = "data is stale; last successful update too old"

        body = {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "plan": None,
            "status": status,
            "windows": [],
            "updated_at_epoch": updated_at,
            "updated_at_local": _format_local_hhmm(updated_at),
            "age_sec": (round(self._monotonic() - snapshot_at, 1)
                        if snapshot_at is not None else None),
            "message": message,
        }
        if snapshot is None:
            return body

        body["plan"] = snapshot["plan"]
        for window in snapshot["windows"]:
            resets_at = window["resets_at"]
            body["windows"].append({
                "label": window["label"],
                "remaining_percent": window["remaining_percent"],
                "resets_at": resets_at,
                "reset_in_sec": (max(resets_at - now_epoch, 0)
                                 if resets_at is not None else None),
                "reset_at_local": _format_local_time(resets_at),
            })
        return body

    # ---- 子类接口 ----

    def _run_loop(self):
        raise NotImplementedError

    def _set_state(self, status, message):
        with self._lock:
            self._status = status
            self._message = message

    def _store_success(self, snapshot):
        """成功归一化后入库：整体替换快照并刷新时间与状态。"""
        with self._lock:
            self._snapshot = snapshot
            self._snapshot_at = self._monotonic()
            self._updated_at_epoch = int(self._epoch())
            self._status = STATUS_OK
            self._message = None


class QuotaCache(BaseQuotaCache):
    """Codex 额度缓存与调度线程。

    调度循环：确保子进程存活（有限退避重启）→ 必要时校验登录类型 →
    读取额度并归一化入库；通知与 60 秒兜底都会唤醒查询。
    """

    provider_id = PROVIDER_ID
    provider_name = PROVIDER_NAME

    def __init__(self, client_factory, epoch=time.time, monotonic=time.monotonic,
                 poll_interval=POLL_INTERVAL_SEC, stale_after=STALE_AFTER_SEC):
        super().__init__(epoch=epoch, monotonic=monotonic,
                         poll_interval=poll_interval, stale_after=stale_after)
        self._client_factory = client_factory
        self._auth_confirmed = False

    def on_rate_limits_updated(self):
        """App Server 通知回调：额度变化，立即安排一次查询。"""
        self._wake.set()

    # ---- 调度循环 ----

    def _run_loop(self):
        backoff_index = 0
        client = None
        while not self._stop_flag:
            if client is None or not client.running:
                try:
                    replacement = self._restart_client(backoff_index)
                except AppServerError:
                    backoff_index += 1
                    continue
                if replacement is None:
                    break  # 仅在停止时返回 None
                if client is not None:
                    client.stop()
                client = replacement
                backoff_index += 1
            try:
                if self._update_once(client):
                    backoff_index = 0
            except AppServerDown:
                client.stop()
                client = None
                continue
            self._wake.wait(self._poll_interval)
            self._wake.clear()
        if client is not None:
            client.stop()

    def _restart_client(self, backoff_index):
        """按有限退避序列等待后重启客户端；返回 None 表示已停止。"""
        delay = RESTART_BACKOFF_SEC[min(backoff_index, len(RESTART_BACKOFF_SEC) - 1)]
        self._set_state(STATUS_UNAVAILABLE, "app server restarting")
        woke = self._wake.wait(delay)
        self._wake.clear()
        if self._stop_flag:
            return None
        client = self._client_factory()
        client.add_notification_handler(self._handle_notification)
        try:
            client.start()
        except Exception:
            client.stop()
            raise
        return client

    def _handle_notification(self, method, params):
        if method == "account/rateLimits/updated":
            self.on_rate_limits_updated()
        elif method == "account/updated":
            self._auth_confirmed = False
            self._wake.set()

    def _update_once(self, client):
        """执行一轮登录校验与额度查询；返回是否成功更新。"""
        if not self._auth_confirmed:
            try:
                self._check_auth(client)
            except AppServerError:
                return False  # _check_auth 内部已设置对应状态
            if not self._auth_confirmed:
                # 非 ChatGPT 登录时没有额度可查，保持 auth_required，
                # 不能被后续查询结果覆盖状态。
                return False
        try:
            raw = client.request("account/rateLimits/read")
        except AppServerUnavailable as exc:
            # 进程退出或写入失败：调度循环需要立即重建客户端。
            self._set_state(STATUS_UNAVAILABLE, "app server not running")
            raise AppServerDown() from exc
        except AppServerError:
            self._set_state(STATUS_UNAVAILABLE, "quota query failed")
            return False
        try:
            normalized = normalize_rate_limits(raw)
        except NormalizationError:
            self._set_state(STATUS_INVALID_DATA, "codex quota data invalid")
            return False
        self._store_success(normalized)
        return True

    def _check_auth(self, client):
        """确认 ChatGPT 登录态；非 ChatGPT 登录时进入 auth_required。"""
        try:
            # App Server 的当前协议要求显式给出 refreshToken。省略参数时，
            # Codex CLI 0.154.0 可能返回 account=null，即使本地 ChatGPT
            # 登录态有效；这里只做只读检查，不强制刷新或改变凭据。
            result = client.request("account/read", {"refreshToken": False})
        except AppServerError:
            self._auth_confirmed = False
            self._set_state(STATUS_UNAVAILABLE, "account state unknown")
            raise
        account = result.get("account") if isinstance(result, dict) else None
        account_type = account.get("type") if isinstance(account, dict) else None
        if account_type == "chatgpt":
            self._auth_confirmed = True
            return
        self._auth_confirmed = False
        self._set_state(STATUS_AUTH_REQUIRED,
                        "ChatGPT login required; run codex login")
