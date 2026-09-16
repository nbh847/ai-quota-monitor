"""Codex App Server 的长期 JSON-RPC 客户端。

通过 `codex app-server --listen stdio://` 子进程的 stdio 逐行通信。
进程只在本地运行，凭证由 Codex CLI 自行管理；本模块不读取、不保存、
不打印任何登录凭据或原始响应内容。
"""

import json
import shutil
import subprocess
import threading

CLIENT_NAME = "ai-quota-monitor-agent"
CLIENT_VERSION = "0.1.0"
HANDSHAKE_TIMEOUT_SEC = 30.0
REQUEST_TIMEOUT_SEC = 30.0


class AppServerError(Exception):
    """App Server 返回了 JSON-RPC error。"""


class AppServerTimeout(AppServerError):
    """请求在超时时间内没有收到对应响应。"""


class AppServerUnavailable(AppServerError):
    """子进程未运行、写入失败或已退出。"""


def resolve_command():
    """定位 Codex CLI 启动入口。

    Windows 上 CreateProcess 不解析 .cmd，npm 安装的入口是 codex.cmd，
    因此优先解析 codex.cmd；找到 .cmd 时通过 cmd /c 启动。
    """
    cmd = shutil.which("codex.cmd") or shutil.which("codex")
    if cmd is None:
        raise AppServerUnavailable("codex executable not found in PATH")
    if cmd.lower().endswith(".cmd"):
        return ["cmd", "/c", cmd]
    return [cmd]


class AppServerClient:
    """单个 App Server 子进程的请求/通知客户端。

    线程模型：
    - reader 线程独占读 stdout，按 id 分发响应，按 method 分发通知。
    - request() 可被多个线程并发调用；stdin 写入串行化。
    - 进程退出时唤醒全部等待者并标记不可用；重启由上层调度线程负责。
    """

    def __init__(self, spawner=None, request_timeout=REQUEST_TIMEOUT_SEC,
                 handshake_timeout=HANDSHAKE_TIMEOUT_SEC):
        self._spawner = spawner or self._default_spawn
        self._request_timeout = request_timeout
        self._handshake_timeout = handshake_timeout
        self._proc = None
        self._reader = None
        self._stderr_reader = None
        self._state_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._next_id = 1
        self._pending = {}  # id -> {"event": Event, "response": dict|None, "dead": bool}
        self._notification_handlers = []
        self._stopped = False

    @staticmethod
    def _default_spawn():
        return subprocess.Popen(
            resolve_command() + ["app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    def add_notification_handler(self, handler):
        """注册通知回调 handler(method, params)；异常被吞掉，不影响读取循环。"""
        self._notification_handlers.append(handler)

    def start(self):
        """启动子进程并完成 initialize / initialized 握手。

        失败时清理已启动的进程并抛出 AppServerError，调用方无需二次清理。
        """
        with self._state_lock:
            if self._proc is not None:
                raise AppServerUnavailable("client already started")
        try:
            proc = self._spawner()
        except OSError as exc:
            raise AppServerUnavailable(f"failed to spawn app server: {exc}") from exc

        with self._state_lock:
            self._proc = proc
            self._reader = threading.Thread(
                target=self._reader_loop, args=(proc,),
                name="app-server-reader", daemon=True)
            self._stderr_reader = threading.Thread(
                target=self._stderr_loop, args=(proc,),
                name="app-server-stderr", daemon=True)
            self._reader.start()
            self._stderr_reader.start()
        try:
            self.request("initialize", {
                "clientInfo": {
                    "name": CLIENT_NAME,
                    "title": "AI Quota Monitor Agent",
                    "version": CLIENT_VERSION,
                },
            }, timeout=self._handshake_timeout)
            self.notify("initialized", {})
        except Exception:
            self.stop()
            raise

    def stop(self):
        """停止客户端：唤醒等待者并终止子进程，不遗留子进程。"""
        self._stopped = True
        self._fail_pending(dead=True)
        with self._state_lock:
            proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except OSError:
                    pass

    @property
    def running(self):
        with self._state_lock:
            proc = self._proc
        return proc is not None and proc.poll() is None

    def request(self, method, params=None, timeout=None):
        """发送请求并等待同 id 响应；返回 result，error 抛 AppServerError。"""
        with self._state_lock:
            if self._stopped or self._proc is None:
                raise AppServerUnavailable("app server not running")
            rid = self._next_id
            self._next_id += 1
            slot = {"event": threading.Event(), "response": None, "dead": False}
            self._pending[rid] = slot

        line = json.dumps({"jsonrpc": "2.0", "id": rid,
                           "method": method, "params": params if params is not None else {}})
        try:
            with self._write_lock:
                proc = self._proc
                if proc is None:
                    raise AppServerUnavailable("app server stopped before write")
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
        except (OSError, ValueError) as exc:
            self._pending.pop(rid, None)
            raise AppServerUnavailable(f"failed to write request: {exc}") from exc

        wait = self._request_timeout if timeout is None else timeout
        if not slot["event"].wait(wait):
            self._pending.pop(rid, None)
            raise AppServerTimeout(f"request timed out: {method}")

        if slot["dead"]:
            self._pending.pop(rid, None)
            raise AppServerUnavailable("app server exited before response")
        response = slot["response"]
        self._pending.pop(rid, None)
        if response is None:
            raise AppServerUnavailable("app server response missing")
        if "error" in response:
            # 只透传错误消息文本，不携带原始对象。
            raise AppServerError(str(response["error"].get("message", "unknown error")))
        return response.get("result")

    def notify(self, method, params=None):
        """发送 JSON-RPC 通知（无 id，不等待响应）。"""
        with self._state_lock:
            if self._stopped:
                return
            proc = self._proc
        if proc is None:
            return
        line = json.dumps({"jsonrpc": "2.0", "method": method,
                           "params": params if params is not None else {}})
        try:
            with self._write_lock:
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
        except (OSError, ValueError):
            # 通知失败不抛异常；后续 request 会感知进程退出。
            pass

    def _reader_loop(self, proc):
        try:
            for line in proc.stdout:
                text = line.strip()
                if not text:
                    continue
                try:
                    message = json.loads(text)
                except ValueError:
                    # 无效 JSON 行直接跳过；协议输出混入诊断文本时保持静默。
                    continue
                self._dispatch(message)
        except (OSError, ValueError):
            pass
        finally:
            self._fail_pending(dead=True)

    @staticmethod
    def _stderr_loop(proc):
        """持续排空 stderr，避免子进程因管道写满阻塞；内容不保存、不打印。"""
        try:
            for _ in proc.stderr:
                pass
        except (OSError, ValueError):
            pass

    def _dispatch(self, message):
        if not isinstance(message, dict):
            return
        rid = message.get("id")
        if rid is not None:
            with self._state_lock:
                slot = self._pending.get(rid)
            if slot is None:
                # 未知响应 ID：超时后迟到或来自上层未跟踪的请求，安全忽略。
                return
            slot["response"] = message
            slot["event"].set()
            return
        method = message.get("method")
        if method is None:
            return
        params = message.get("params")
        for handler in list(self._notification_handlers):
            try:
                handler(method, params)
            except Exception:
                continue

    def _fail_pending(self, dead=True):
        with self._state_lock:
            slots = list(self._pending.values())
        for slot in slots:
            slot["dead"] = dead
            slot["event"].set()
