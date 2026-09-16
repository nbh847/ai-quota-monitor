"""智谱额度缓存与调度线程。

与 Codex 的 QuotaCache 共享 BaseQuotaCache 的状态与渲染骨架；
调度为纯 HTTP 轮询：每轮重新发现配置并查询（用户补齐配置后无需
重启 Agent），失败保留最后有效快照，超过 stale 阈值后进入 stale。
"""

import time

from quotas import (BaseQuotaCache, STATUS_AUTH_REQUIRED, STATUS_INVALID_DATA,
                    STATUS_UNAVAILABLE)
from zhipu_client import (ZhipuAuthError, ZhipuConfigError, ZhipuDataError,
                          ZhipuUnavailableError, discover_config,
                          fetch_quota_limit, normalize_zhipu_quota)

PROVIDER_ID = "zhipu"
PROVIDER_NAME = "智谱"

POLL_INTERVAL_SEC = 60.0     # 智谱额度轮询周期
STALE_AFTER_SEC = 180.0      # 超过该时长没有成功更新即标记 stale


class ZhipuCache(BaseQuotaCache):
    """智谱额度缓存：独立于 Codex 的状态、快照与调度线程。"""

    provider_id = PROVIDER_ID
    provider_name = PROVIDER_NAME

    def __init__(self, fetch=None, discover=None, epoch=time.time,
                 monotonic=time.monotonic, poll_interval=POLL_INTERVAL_SEC,
                 stale_after=STALE_AFTER_SEC):
        super().__init__(epoch=epoch, monotonic=monotonic,
                         poll_interval=poll_interval, stale_after=stale_after)
        self._fetch = fetch or fetch_quota_limit
        self._discover = discover or discover_config

    def _run_loop(self):
        while not self._stop_flag:
            self._update_once()
            self._wake.wait(self._poll_interval)
            self._wake.clear()

    def _update_once(self):
        """执行一轮配置发现与额度查询；返回是否成功更新。"""
        try:
            config = self._discover()
        except ZhipuConfigError as exc:
            self._set_state(STATUS_AUTH_REQUIRED, str(exc))
            return False
        try:
            payload = self._fetch(config)
        except ZhipuAuthError as exc:
            self._set_state(STATUS_AUTH_REQUIRED, str(exc))
            return False
        except ZhipuUnavailableError as exc:
            self._set_state(STATUS_UNAVAILABLE, str(exc))
            return False
        try:
            snapshot = normalize_zhipu_quota(payload)
        except ZhipuDataError as exc:
            self._set_state(STATUS_INVALID_DATA, str(exc))
            return False
        self._store_success(snapshot)
        return True