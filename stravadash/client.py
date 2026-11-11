"""Thin Strava API client that respects the read rate limits.

Strava reports usage in response headers, so instead of keeping our own
request log we read `X-ReadRateLimit-Usage` / `-Limit` after every call.
Short-term (15 min) limits are waited out; hitting the daily limit raises
`DailyLimitReached` so a sync can stop cleanly and resume later.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import requests

API = "https://www.strava.com/api/v3"
SAFETY_MARGIN = 2


class DailyLimitReached(RuntimeError):
    pass


def _pair(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        short, daily = (int(x) for x in value.split(",")[:2])
        return short, daily
    except ValueError:
        return None


def seconds_until_next_window(now: float | None = None) -> float:
    """Strava's 15-minute windows reset at :00, :15, :30 and :45."""
    now = time.time() if now is None else now
    return 900 - (now % 900) + 5


class StravaClient:
    def __init__(
        self,
        token_provider: Callable[[], str],
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
    ):
        self._token = token_provider
        self._session = session or requests.Session()
        self._sleep = sleep
        self._log = log

    def get(self, path: str, params: dict | None = None):
        for _ in range(3):
            resp = self._session.get(
                f"{API}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=30,
            )
            limit = _pair(resp.headers.get("X-ReadRateLimit-Limit")) or _pair(resp.headers.get("X-RateLimit-Limit"))
            usage = _pair(resp.headers.get("X-ReadRateLimit-Usage")) or _pair(resp.headers.get("X-RateLimit-Usage"))

            if resp.status_code == 429:
                self._handle_limit(usage, limit, exhausted=True)
                continue
            resp.raise_for_status()
            self._handle_limit(usage, limit, exhausted=False)
            return resp.json()
        raise RuntimeError(f"Strava kept rate limiting {path}")

    def _handle_limit(self, usage, limit, exhausted: bool) -> None:
        if usage and limit and usage[1] >= limit[1] - SAFETY_MARGIN:
            raise DailyLimitReached(
                f"Strava daily read limit reached ({usage[1]}/{limit[1]}). "
                "Progress is saved; run sync again after midnight UTC."
            )
        if exhausted or (usage and limit and usage[0] >= limit[0] - SAFETY_MARGIN):
            wait = seconds_until_next_window()
            resume = datetime.fromtimestamp(time.time() + wait, tz=timezone.utc).astimezone()
            self._log(f"Rate limit window full, pausing until {resume:%H:%M:%S}...")
            self._sleep(wait)

    def list_activities(self, after: int | None = None, per_page: int = 200):
        page = 1
        while True:
            params = {"page": page, "per_page": per_page}
            if after:
                params["after"] = after
            batch = self.get("/athlete/activities", params)
            if not batch:
                return
            yield from batch
            page += 1

    def get_activity(self, activity_id: int) -> dict:
        return self.get(f"/activities/{activity_id}", {"include_all_efforts": "false"})
