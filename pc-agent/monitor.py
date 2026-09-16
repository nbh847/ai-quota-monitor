"""AI Quota Monitor PC Agent 入口。

组装 Codex App Server 客户端、额度缓存调度线程与 HTTP 服务。
HTTP 只读内存缓存，不直接触发 App Server 查询。
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from codex_client import AppServerClient
from quotas import QuotaCache

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8767

AGENT_NAME = "ai-quota-monitor-agent"
AGENT_VERSION = "0.1.0"


def build_cache():
    """真实装配：App Server 客户端 + 额度缓存。"""
    return QuotaCache(AppServerClient)


def make_handler(cache, log):
    """构造 HTTP 请求处理类；响应只读缓存快照。"""

    class QuotaHandler(BaseHTTPRequestHandler):

        def _send_json(self, payload, status=200):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/v1/quotas/codex":
                self._send_json(cache.render())
            elif path == "/api/v1/health":
                self._send_json({"ok": True, "agent": AGENT_NAME,
                                 "version": AGENT_VERSION})
            else:
                self._send_json({"error": "not found"}, status=404)

        def log_message(self, fmt, *args):
            # 默认日志会记录完整请求行；仅保留路径级别信息即可。
            log("%s %s" % (self.command, self.path.split("?", 1)[0]))

    return QuotaHandler


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI Quota Monitor PC Agent")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    cache = build_cache()
    cache.start()

    server = ThreadingHTTPServer((args.host, args.port),
                                 make_handler(cache, lambda msg: print(msg, flush=True)))
    print(f"{AGENT_NAME} v{AGENT_VERSION} listening on {args.host}:{args.port}",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        cache.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())