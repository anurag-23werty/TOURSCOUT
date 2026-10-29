from __future__ import annotations

import pytest

from tourscout_api.api.ratelimit import Limiter, SlidingWindow
from tourscout_api.api.sessions import SessionStore
from tourscout_api.api.uploads import UploadError, UploadStore, sniff_image


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_sliding_window_blocks_then_recovers() -> None:
    clock = Clock()
    w = SlidingWindow(2, 60, clock)
    assert w.check("ip").allowed and w.check("ip").allowed
    blocked = w.check("ip")
    assert not blocked.allowed and 1 <= blocked.retry_after_s <= 61
    assert w.check("other-ip").allowed
    clock.t += 61
    assert w.check("ip").allowed


def test_global_daily_cap_applies_across_ips() -> None:
    clock = Clock()
    limiter = Limiter({"plan": (5, 3600)}, {"plan": 2}, clock)
    assert limiter.check("plan", "a").allowed and limiter.check("plan", "b").allowed
    d = limiter.check("plan", "c")
    assert not d.allowed and "daily" in d.reason


def test_blocked_per_ip_requests_dont_use_the_daily_budget() -> None:
    limiter = Limiter({"plan": (1, 3600)}, {"plan": 2}, Clock())
    assert limiter.check("plan", "a").allowed
    assert not limiter.check("plan", "a").allowed  # per-IP block…
    assert limiter.check("plan", "b").allowed  # …didn't consume the global cap


def test_sessions_expire_and_own_threads() -> None:
    clock = Clock()
    store = SessionStore(ttl_s=100, clock=clock)
    s = store.create()
    t = store.new_thread(s)
    assert store.get(s.id) is s and store.owns(s, t) and not store.owns(s, "someone-else")
    clock.t += 101
    assert store.get(s.id) is None


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def test_uploads_sniff_bytes_and_are_single_use() -> None:
    store = UploadStore(max_bytes=1000, ttl_s=60, clock=Clock())
    up, preview = store.add(PNG, "dashboard.txt", "s1")  # the name lies, the bytes don't
    assert up.kind == "image" and preview["mime"] == "image/png"
    with pytest.raises(UploadError, match="not found"):
        store.take(up.id, "s2")  # another session can't use it
    assert store.take(up.id, "s1")["mime"] == "image/png"
    with pytest.raises(UploadError):
        store.take(up.id, "s1")  # deleted after use


def test_csv_upload_preview_and_rejections() -> None:
    store = UploadStore(max_bytes=1000, ttl_s=60, clock=Clock())
    _, preview = store.add(b"City,Listeners\nChicago,12.4K\nColumbus,2500\n", "top.csv", "s1")
    assert preview["rows"][0] == {"city": "Chicago", "listeners": 12400} and preview["total_rows"] == 2
    with pytest.raises(UploadError, match="too large"):
        store.add(b"x" * 2000, "big.csv", "s1")
    with pytest.raises(UploadError, match="PNG/JPEG/WebP"):
        store.add(b"%PDF-1.7 hello", "doc.pdf", "s1")
    with pytest.raises(ValueError, match="city column"):
        store.add(b"a,b\n1,2\n", "x.csv", "s1")
    assert sniff_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
