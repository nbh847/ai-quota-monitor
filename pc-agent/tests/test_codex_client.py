"""AppServerClient 单元测试：伪造子进程覆盖分包、并发、超时与退出路径。"""

import json
import threading
import unittest

from codex_client import (AppServerClient, AppServerError,
                          AppServerTimeout, AppServerUnavailable)

from tests.fake_proc import spawn_factory, wait_for
from tests.samples import account_ok_result, jsonrpc_response, rate_limits_result

HANDSHAKE_LINES = 2  # initialize + initialized


def feed_responses(fake, *messages):
    """向伪造 stdout 按行写入若干 JSON 消息。"""
    for message in messages:
        fake.stdout.feed(message if isinstance(message, str) else json.dumps(message))


def last_request_id(fake):
    return json.loads(fake.stdin.lines[-1])["id"]


class AppServerClientTest(unittest.TestCase):

    def make_client(self, fake, **kwargs):
        return AppServerClient(spawner=lambda: fake, **kwargs)

    def start_client(self, fake):
        """后台线程应答握手请求，阻塞直到 start() 完成。"""

        def run():
            if wait_for(lambda: len(fake.stdin.lines) >= 1):
                feed_responses(fake, jsonrpc_response(last_request_id(fake),
                                                      {"userAgent": "fake"}))

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        client = self.make_client(fake)
        client.start()
        return client

    def request_with_answer(self, client, fake, method, result,
                            extra_feed=(), timeout=None):
        """发起请求；等待请求行出现后喂入响应（可先喂额外消息）。"""
        holder = {}

        def do_request():
            try:
                kwargs = {"timeout": timeout} if timeout is not None else {}
                holder["result"] = client.request(method, **kwargs)
            except AppServerError as exc:
                holder["error"] = exc

        worker = threading.Thread(target=do_request, daemon=True)
        worker.start()
        expected = HANDSHAKE_LINES + 1
        if wait_for(lambda: len(fake.stdin.lines) >= expected):
            feed_responses(fake, *extra_feed,
                           jsonrpc_response(last_request_id(fake), result))
        worker.join(2)
        self.assertFalse(worker.is_alive(), "request worker did not finish")
        return holder

    def test_handshake_writes_initialize_and_initialized(self):
        fake = spawn_factory()()
        client = self.start_client(fake)

        self.assertEqual(len(fake.stdin.lines), 2)
        first = json.loads(fake.stdin.lines[0])
        second = json.loads(fake.stdin.lines[1])
        self.assertEqual(first["method"], "initialize")
        self.assertEqual(first["params"]["clientInfo"]["name"],
                         "ai-quota-monitor-agent")
        self.assertNotIn("id", second)
        self.assertEqual(second["method"], "initialized")
        client.stop()

    def test_request_returns_result(self):
        fake = spawn_factory()()
        client = self.start_client(fake)

        holder = self.request_with_answer(client, fake, "account/read",
                                          account_ok_result())
        self.assertEqual(holder["result"]["account"]["type"], "chatgpt")
        client.stop()

    def test_notification_and_response_concurrent(self):
        fake = spawn_factory()()
        client = self.start_client(fake)
        notifications = []
        client.add_notification_handler(lambda m, p: notifications.append(m))

        holder = self.request_with_answer(
            client, fake, "account/rateLimits/read", rate_limits_result(),
            extra_feed=[{"jsonrpc": "2.0",
                         "method": "account/rateLimits/updated",
                         "params": {}}])
        self.assertEqual(holder["result"]["rateLimitsByLimitId"]["codex"]["planType"],
                         "plus")
        self.assertIn("account/rateLimits/updated", notifications)
        client.stop()

    def test_unknown_response_id_ignored(self):
        fake = spawn_factory()()
        client = self.start_client(fake)

        holder = self.request_with_answer(
            client, fake, "account/read", account_ok_result(),
            extra_feed=[jsonrpc_response(9999, {"unexpected": True})])
        self.assertEqual(holder["result"]["account"]["type"], "chatgpt")
        client.stop()

    def test_request_timeout(self):
        fake = spawn_factory()()
        client = self.start_client(fake)
        with self.assertRaises(AppServerTimeout):
            client.request("account/read", timeout=0.05)
        client.stop()

    def test_invalid_json_line_skipped(self):
        fake = spawn_factory()()
        client = self.start_client(fake)

        holder = self.request_with_answer(
            client, fake, "account/read", account_ok_result(),
            extra_feed=["this is not json", "{broken"])
        self.assertEqual(holder["result"]["account"]["type"], "chatgpt")
        client.stop()

    def test_stderr_is_drained_without_logging(self):
        fake = spawn_factory()()
        client = self.start_client(fake)
        for index in range(1000):
            fake.stderr.feed(f"diagnostic {index}\n")
        self.assertTrue(wait_for(fake.stderr.empty), "stderr was not drained")
        self.assertFalse(hasattr(client, "_stderr_tail"))
        client.stop()

    def test_process_exit_wakes_pending_request(self):
        fake = spawn_factory()()
        client = self.start_client(fake)

        errors = {}

        def do_request():
            try:
                client.request("account/read", timeout=5)
            except AppServerError as exc:
                errors["exc"] = exc

        worker = threading.Thread(target=do_request, daemon=True)
        worker.start()
        if wait_for(lambda: len(fake.stdin.lines) >= HANDSHAKE_LINES + 1):
            fake.simulate_exit()
        worker.join(2)
        self.assertFalse(worker.is_alive(), "request worker did not finish")
        self.assertIsInstance(errors.get("exc"), AppServerUnavailable)
        self.assertFalse(client.running)
        client.stop()

    def test_stop_terminates_process_without_children(self):
        fake = spawn_factory()()
        client = self.start_client(fake)
        client.stop()
        self.assertTrue(fake.terminated)
        self.assertIsNone(client._proc)
        self.assertEqual(fake.poll(), 0)

    def test_spawn_failure_raises_unavailable(self):
        def broken_spawn():
            raise OSError("codex not found")

        client = AppServerClient(spawner=broken_spawn)
        with self.assertRaises(AppServerUnavailable):
            client.start()
        self.assertIsNone(client._proc)

    def test_stdin_write_failure_raises_unavailable(self):
        fake = spawn_factory(fail_writes=True)()
        client = self.make_client(fake)
        with self.assertRaises(AppServerUnavailable):
            client.start()


if __name__ == "__main__":
    unittest.main()
