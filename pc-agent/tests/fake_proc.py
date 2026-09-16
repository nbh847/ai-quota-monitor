"""CP1/CP2 测试共享的伪造子进程与工具。"""

import queue
import threading
import time


class LineStream:
    """可动态写入的逐行流，模拟子进程 stdout。"""

    def __init__(self):
        self._queue = queue.Queue()

    def feed(self, text):
        self._queue.put(text)

    def close(self):
        self._queue.put(None)

    def empty(self):
        return self._queue.empty()

    def __iter__(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            yield item


class FakeStdin:

    def __init__(self, fail=False):
        self.lines = []
        self.fail = fail
        self.closed = False

    def write(self, text):
        if self.fail:
            raise OSError("broken pipe")
        self.lines.append(text)
        return len(text)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class FakeProc:
    """模拟 subprocess.Popen 的最小接口。"""

    def __init__(self, fail_writes=False):
        self.stdin = FakeStdin(fail=fail_writes)
        self.stdout = LineStream()
        self.stderr = LineStream()
        self.terminated = False
        self.killed = False
        self._exited = threading.Event()

    def poll(self):
        return 0 if self._exited.is_set() else None

    def terminate(self):
        self.terminated = True
        self._exited.set()
        self.stdout.close()
        self.stderr.close()

    def kill(self):
        self.killed = True
        self._exited.set()
        self.stdout.close()
        self.stderr.close()

    def wait(self, timeout=None):
        self._exited.wait(timeout if timeout is not None else 5)
        return 0 if self._exited.is_set() else None

    def simulate_exit(self):
        self._exited.set()
        self.stdout.close()
        self.stderr.close()


def spawn_factory(fail_writes=False):
    """返回 () -> FakeProc 的工厂。"""
    def spawn():
        return FakeProc(fail_writes=fail_writes)
    return spawn


def wait_for(condition, timeout=2.0):
    """轮询条件成立；返回是否在超时前满足。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.005)
    return condition()


def request_id_of(line):
    """从 stdin 记录的请求行解析 id。"""
    import json
    return json.loads(line).get("id")
