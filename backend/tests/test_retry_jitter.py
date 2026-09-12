"""
优化4 单元测试：重试退避抖动
compute_backoff_delay 的边界与随机性、with_retry 使用抖动间隔
"""
import pytest

from app.utils.retry_utils import compute_backoff_delay, with_retry


class TestComputeBackoffDelay:
    def test_bounds_equal_jitter(self):
        """等量抖动：结果落在 [基础值/2, 基础值]"""
        for attempt in range(6):
            for _ in range(50):
                delay = compute_backoff_delay(attempt, base_delay=1.0, max_delay=10.0)
                base = min(1.0 * (2 ** attempt), 10.0)
                assert base / 2 <= delay <= base

    def test_max_delay_capped(self):
        """指数增长封顶于 max_delay"""
        delay = compute_backoff_delay(attempt=20, base_delay=1.0, max_delay=10.0)
        assert 5.0 <= delay <= 10.0

    def test_attempt_zero_half_base(self):
        """attempt=0 时基础值为 base_delay，抖动区间 [base/2, base]"""
        for _ in range(20):
            assert 0.5 <= compute_backoff_delay(0, 1.0, 10.0) <= 1.0

    def test_deterministic_with_stubbed_random(self, monkeypatch):
        monkeypatch.setattr("app.utils.retry_utils.random.uniform", lambda a, b: (a + b) / 2)
        # base=1, attempt=1 → 基础值 2 → uniform(1,2) 中点 1.5
        assert compute_backoff_delay(1, 1.0, 10.0) == pytest.approx(1.5)


class TestWithRetryJitter:
    def test_sleep_receives_jittered_delay(self, monkeypatch):
        """with_retry 的等待间隔来自抖动函数"""
        sleeps = []
        monkeypatch.setattr("app.utils.retry_utils.time.sleep", lambda s: sleeps.append(s))

        calls = {"n": 0}

        @with_retry(max_retries=2, base_delay=2.0, max_delay=8.0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return "ok"

        assert flaky() == "ok"
        assert len(sleeps) == 2
        # 第一次重试基础值 2s → sleep ∈ [1, 2]；第二次 4s → [2, 4]
        assert 1.0 <= sleeps[0] <= 2.0
        assert 2.0 <= sleeps[1] <= 4.0
