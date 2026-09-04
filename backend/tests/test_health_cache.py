"""
优化2 单元测试：/api/health 探活结果短缓存
"""
import pytest

from app.core import health


@pytest.fixture(autouse=True)
def _reset_cache():
    health._health_cache["data"] = None
    health._health_cache["expires_at"] = 0.0
    yield
    health._health_cache["data"] = None
    health._health_cache["expires_at"] = 0.0


class TestHealthCache:
    def test_second_call_served_from_cache(self, monkeypatch):
        """TTL 内第二次调用直接返回缓存，不再探活"""
        calls = {"n": 0}

        def fake_probe():
            calls["n"] += 1
            return {"status": "degraded", "checks": {}, "caches": {}}

        monkeypatch.setattr(health, "_probe_all", fake_probe)

        first = health.collect_health()
        second = health.collect_health()

        assert calls["n"] == 1
        assert first["cached"] is False
        assert second["cached"] is True
        assert second["status"] == "degraded"

    def test_cache_expires(self, monkeypatch):
        """TTL 过期后重新探活"""
        calls = {"n": 0}

        def fake_probe():
            calls["n"] += 1
            return {"status": "ok", "checks": {}, "caches": {}}

        fake_clock = [1000.0]
        monkeypatch.setattr(health, "_probe_all", fake_probe)
        monkeypatch.setattr(health.time, "monotonic", lambda: fake_clock[0])

        health.collect_health()
        fake_clock[0] += health.HEALTH_CACHE_TTL_SECONDS + 0.1
        result = health.collect_health()

        assert calls["n"] == 2
        assert result["cached"] is False

    def test_force_refresh_bypasses_cache(self, monkeypatch):
        calls = {"n": 0}

        def fake_probe():
            calls["n"] += 1
            return {"status": "ok", "checks": {}, "caches": {}}

        monkeypatch.setattr(health, "_probe_all", fake_probe)

        health.collect_health()
        result = health.collect_health(force_refresh=True)

        assert calls["n"] == 2
        assert result["cached"] is False

    def test_cached_result_not_mutated_by_caller(self):
        """返回的副本带 cached 标记，缓存本体不受污染"""
        health._health_cache["data"] = {"status": "ok", "checks": {}, "caches": {}}
        health._health_cache["expires_at"] = health.time.monotonic() + 10

        result = health.collect_health()
        assert result["cached"] is True
        assert "cached" not in health._health_cache["data"]  # 缓存本体无 cached 键
