from types import SimpleNamespace

import pytest
import requests

from behavioralsignals import BehavioralSignalsError, base
from behavioralsignals.models import ProcessItem
from behavioralsignals.deepfakes import Deepfakes
from behavioralsignals.behavioral import Behavioral


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    clock = FakeClock()
    fake_time = SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep)
    monkeypatch.setattr(base, "time", fake_time)
    return clock


def make_client(cls, statuses, video=False):
    """Client without network: get_process returns (or raises) the given statuses, then repeats the last."""
    client = cls.__new__(cls)
    calls = []

    def get_process(pid):
        calls.append(pid)
        status = statuses[min(len(calls), len(statuses)) - 1]
        if isinstance(status, Exception):
            raise status
        return ProcessItem(pid=pid, status=status, statusmsg=f"status {status}")

    result = SimpleNamespace(kind="video" if video else "audio")
    if video:
        client.get_video_process, client.get_video_result = get_process, lambda pid: result
    else:
        client.get_process, client.get_result = get_process, lambda pid: result
    return client, calls, result


def test_returns_result_after_pending_and_processing(clock):
    client, calls, result = make_client(Behavioral, [0, 1, 2])
    assert client.wait_for_result(pid=7) is result
    assert calls == [7, 7, 7] and clock.sleeps == 2


def test_returns_immediately_when_already_complete(clock):
    client, calls, result = make_client(Deepfakes, [2])
    assert client.wait_for_result(pid=7) is result
    assert calls == [7] and clock.sleeps == 0


def test_raises_on_failed(clock):
    client, _, _ = make_client(Behavioral, [0, -1])
    with pytest.raises(RuntimeError, match="status -1"):
        client.wait_for_result(pid=7)


def test_raises_on_insufficient_credits(clock):
    client, _, _ = make_client(Deepfakes, [-2])
    with pytest.raises(RuntimeError, match="status -2"):
        client.wait_for_result(pid=7)


def test_raises_on_timeout(clock):
    client, _, _ = make_client(Behavioral, [1])
    with pytest.raises(TimeoutError, match="still running"):
        client.wait_for_result(pid=7, timeout=3)
    assert clock.now >= 3


def test_video_uses_video_endpoints(clock):
    client, calls, result = make_client(Deepfakes, [0, 2], video=True)
    assert client.wait_for_video_result(pid=9) is result
    assert calls == [9, 9]


def test_retries_network_errors(clock):
    errors = [requests.ConnectionError("down"), requests.Timeout("slow")]
    client, calls, result = make_client(Behavioral, [*errors, 2])
    assert client.wait_for_result(pid=7) is result
    assert calls == [7, 7, 7] and clock.sleeps == 2


def test_ssl_and_proxy_errors_are_retried(clock):
    errors = [requests.exceptions.SSLError("eof"), requests.exceptions.ProxyError("proxy down")]
    client, calls, result = make_client(Behavioral, [*errors, 2])
    assert client.wait_for_result(pid=7, timeout=3) is result
    assert calls == [7, 7, 7]


def test_network_error_past_deadline_is_raised(clock):
    client, _, _ = make_client(Deepfakes, [requests.ConnectionError("down")])
    with pytest.raises(requests.ConnectionError, match="down"):
        client.wait_for_result(pid=7, timeout=3)
    assert clock.now >= 3


def test_api_error_is_not_retried(clock):
    error = BehavioralSignalsError("API Error 401: bad key", status_code=401)
    client, calls, _ = make_client(Behavioral, [error])
    with pytest.raises(BehavioralSignalsError, match="401"):
        client.wait_for_result(pid=7, timeout=3)
    assert calls == [7]
