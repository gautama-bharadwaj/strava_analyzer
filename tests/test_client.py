import pytest

from stravadash.client import DailyLimitReached, StravaClient, seconds_until_next_window


class Resp:
    def __init__(self, status, headers, body=None):
        self.status_code, self.headers, self._body = status, headers, body

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Session:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, *a, **k):
        return self.responses.pop(0)


H = lambda usage: {"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": usage}


def test_waits_when_window_full():
    slept = []
    c = StravaClient(lambda: "t", Session([Resp(200, H("99,500"), [1])]), sleep=slept.append, log=lambda *_: None)
    assert c.get("/x") == [1]
    assert slept and 0 < slept[0] <= 905


def test_retries_after_429():
    slept = []
    c = StravaClient(lambda: "t", Session([Resp(429, H("100,500")), Resp(200, H("1,501"), {"ok": 1})]),
                     sleep=slept.append, log=lambda *_: None)
    assert c.get("/x") == {"ok": 1} and len(slept) == 1


def test_daily_limit_raises():
    c = StravaClient(lambda: "t", Session([Resp(200, H("5,999"), [])]), sleep=lambda s: None)
    with pytest.raises(DailyLimitReached):
        c.get("/x")


def test_window_math():
    assert seconds_until_next_window(900 * 10 + 100) == 805
