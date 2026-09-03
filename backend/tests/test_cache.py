"""
演进8 单元测试：多级缓存层
TTL/LRU 行为、get_or_set、统计、注册表、Embedding 批量缓存、HyDE 缓存
"""
import pytest

from app.core import metrics
from app.core.cache import TTLCache, register_cache, get_cache, all_caches


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


class TestTTLCache:
    def test_set_get(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        cache.set("k", {"v": 1})
        assert cache.get("k") == {"v": 1}

    def test_miss_returns_default(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        assert cache.get("missing") is None
        assert cache.get("missing", "fallback") == "fallback"

    def test_ttl_expiry(self, monkeypatch):
        """TTL 到期条目自动失效"""
        fake_now = [1000.0]
        monkeypatch.setattr("app.core.cache.time.monotonic", lambda: fake_now[0])
        cache = TTLCache("t", maxsize=10, ttl=5)
        cache.set("k", "v")
        assert cache.get("k") == "v"

        fake_now[0] = 1004.0  # 未过期
        assert cache.get("k") == "v"

        fake_now[0] = 1006.0  # 已过期
        assert cache.get("k") is None

    def test_lru_eviction(self):
        """容量满时淘汰最久未使用条目"""
        cache = TTLCache("t", maxsize=3, ttl=60)
        for i in range(3):
            cache.set(f"k{i}", i)
        cache.get("k0")      # k0 变为最近使用
        cache.set("k3", 3)   # 淘汰最旧的 k1
        assert cache.get("k0") == 0
        assert cache.get("k1") is None
        assert cache.get("k3") == 3
        assert cache.stats()["evictions"] == 1

    def test_get_or_set(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        calls = {"n": 0}

        def factory():
            calls["n"] += 1
            return "computed"

        assert cache.get_or_set("k", factory) == "computed"
        assert cache.get_or_set("k", factory) == "computed"
        assert calls["n"] == 1  # 第二次命中缓存

    def test_factory_exception_not_cached(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            raise RuntimeError("downstream")

        with pytest.raises(RuntimeError):
            cache.get_or_set("k", flaky)
        with pytest.raises(RuntimeError):
            cache.get_or_set("k", flaky)
        assert calls["n"] == 2  # 失败结果不缓存，每次重试
        assert cache.size == 0

    def test_delete_clear(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.delete("a")
        assert cache.get("a") is None
        cache.clear()
        assert cache.size == 0

    def test_stats_hit_rate(self):
        cache = TTLCache("t", maxsize=10, ttl=60)
        cache.set("k", 1)
        cache.get("k")  # hit
        cache.get("x")  # miss
        stats = cache.stats()
        assert stats["hits"] == 1 and stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_metrics_reported(self):
        cache = TTLCache("mcache", maxsize=10, ttl=60)
        cache.set("k", 1)
        cache.get("k")
        cache.get("nope")
        snap = metrics.snapshot()
        assert snap["counters"]["cache_hits_total|cache=mcache"] == 1.0
        assert snap["counters"]["cache_misses_total|cache=mcache"] == 1.0
        assert snap["gauges"]["cache_entries|cache=mcache"] == 1

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            TTLCache("t", maxsize=0, ttl=60)
        with pytest.raises(ValueError):
            TTLCache("t", maxsize=10, ttl=0)


class TestRegistry:
    def test_register_and_get(self):
        c1 = register_cache("reg_test", maxsize=5, ttl=60)
        c2 = register_cache("reg_test", maxsize=99, ttl=99)  # 同名返回既有实例
        assert c1 is c2
        assert get_cache("reg_test") is c1
        assert "reg_test" in all_caches()

    def test_builtin_caches_registered(self):
        """四个业务缓存必须在导入 app_caches 后可用"""
        import app.core.app_caches  # noqa: F401
        for name in ("embedding", "hyde_text", "web_search", "item_name_alignment"):
            assert get_cache(name) is not None


class TestEmbeddingCache:
    def test_batch_second_call_all_hits(self, monkeypatch):
        """批量向量化第二次调用应全部命中缓存"""
        from app.lm import embedding_utils as mod

        calls = {"n": 0}

        def fake_embed(texts):
            calls["n"] += 1
            return [[0.1, 0.2] for _ in texts]

        monkeypatch.setattr(mod, "_embed_documents_uncached", fake_embed)
        mod.embedding_cache.clear()

        texts = ["t1", "t2", "t3"]
        r1 = mod.generate_embeddings(texts)
        r2 = mod.generate_embeddings(texts)
        assert r1 == r2
        assert calls["n"] == 1  # 第二次全部命中

        stats = mod.embedding_cache.stats()
        assert stats["misses"] >= 3 and stats["hits"] >= 3

    def test_single_query_cached(self, monkeypatch):
        from app.lm import embedding_utils as mod

        calls = {"n": 0}

        def fake_query(text):
            calls["n"] += 1
            return [0.0]

        monkeypatch.setattr(mod, "_embed_query_uncached", fake_query)
        mod.embedding_cache.clear()

        mod.generate_embedding("同一查询")
        mod.generate_embedding("同一查询")
        assert calls["n"] == 1


class TestHydeCache:
    def test_llm_called_once(self, monkeypatch):
        """相同查询的 HyDE 生成只调用一次 LLM"""
        from app.query_process.agent.nodes import node_search_embedding_hyde as node

        calls = {"n": 0}

        class FakeResp:
            content = "假设性回答内容"

        class FakeLLM:
            def invoke(self, messages):
                calls["n"] += 1
                return FakeResp()

        monkeypatch.setattr(node, "get_llm_client", lambda: FakeLLM())
        node.hyde_cache.clear()

        t1 = node._generate_hyde_text("同一个问题")
        t2 = node._generate_hyde_text("同一个问题")
        assert t1 == t2 == "假设性回答内容"
        assert calls["n"] == 1

    def test_llm_failure_falls_back_and_not_cached(self, monkeypatch):
        from app.query_process.agent.nodes import node_search_embedding_hyde as node

        class FailingLLM:
            def invoke(self, messages):
                raise RuntimeError("LLM down")

        monkeypatch.setattr(node, "get_llm_client", lambda: FailingLLM())
        node.hyde_cache.clear()

        assert node._generate_hyde_text("坏查询") == "坏查询"  # 回退原始查询
        assert node.hyde_cache.get("坏查询") is None  # 失败不缓存
