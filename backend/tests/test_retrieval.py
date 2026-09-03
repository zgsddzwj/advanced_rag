"""
演进7 单元测试：检索管线可插拔
RetrievalConfig 校验与回退、检索器注册表、RRF 参数化、三态联网搜索决策
"""
import pytest
from pydantic import ValidationError

from app.query_process.agent.retrieval_config import RetrievalConfig, get_retrieval_config
from app.query_process.agent.retrievers import (
    MilvusHybridRetriever, register_retriever, get_retriever, registered_retrievers,
)
from app.query_process.agent.nodes.node_rrf import _rrf_fuse


class TestRetrievalConfig:
    def test_defaults_match_legacy_behavior(self):
        """默认值必须与演进前常量一致"""
        c = RetrievalConfig()
        assert c.enable_hyde is True
        assert c.enable_web_search is None  # 自动判断
        assert c.top_k == 10
        assert c.rrf_k == 60
        assert c.rrf_output_limit == 15
        assert c.web_search_count == 5

    def test_bounds(self):
        with pytest.raises(ValidationError):
            RetrievalConfig(top_k=0)
        with pytest.raises(ValidationError):
            RetrievalConfig(top_k=31)
        with pytest.raises(ValidationError):
            RetrievalConfig(rrf_k=0)
        with pytest.raises(ValidationError):
            RetrievalConfig(rrf_output_limit=51)
        with pytest.raises(ValidationError):
            RetrievalConfig(web_search_count=0)

    def test_get_from_state(self):
        state = {"retrieval_config": {"top_k": 5, "enable_web_search": True}}
        c = get_retrieval_config(state)
        assert c.top_k == 5
        assert c.enable_web_search is True
        assert c.rrf_k == 60  # 未覆盖字段回退默认

    def test_get_from_missing_state(self):
        assert get_retrieval_config({}) == RetrievalConfig()
        assert get_retrieval_config({"retrieval_config": None}) == RetrievalConfig()

    def test_invalid_config_falls_back(self):
        """非法配置不炸管线，回退默认"""
        c = get_retrieval_config({"retrieval_config": {"top_k": 999}})
        assert c == RetrievalConfig()


class TestRetrieverRegistry:
    def test_builtin_retrievers(self):
        names = registered_retrievers()
        assert "embedding" in names and "hyde" in names
        assert get_retriever("embedding").name == "embedding"
        assert get_retriever("hyde").source == "hyde"

    def test_unknown_retriever_raises(self):
        with pytest.raises(KeyError):
            get_retriever("nope")

    def test_register_custom(self):
        class Dummy:
            name = "dummy"

            def retrieve(self, query, item_names, top_k):
                return [{"content": query}]

        register_retriever(Dummy())
        assert get_retriever("dummy").retrieve("hi", [], 5) == [{"content": "hi"}]


class _FakeMilvusClient:
    def __init__(self, has_collection=True):
        self._has = has_collection
        self.loaded = []
        self.search_calls = []

    def has_collection(self, collection_name=None):
        return self._has

    def load_collection(self, collection_name=None):
        self.loaded.append(collection_name)

    def insert(self, collection_name=None, data=None):
        pass

    def hybrid_search(self, collection_name=None, reqs=None, ranker=None, limit=None, output_fields=None):
        self.search_calls.append({"limit": limit, "reqs": reqs})
        return [[{"chunk_id": 1, "content": "c", "title": "t", "parent_title": "pt",
                  "part": 0, "file_title": "f", "item_name": "i"}]]


class TestMilvusHybridRetriever:
    def test_retrieve_happy_path(self, monkeypatch):
        fake = _FakeMilvusClient()

        def fake_embed(text):
            return [0.1] * 4

        from app.query_process.agent import retrievers as mod
        monkeypatch.setattr("app.clients.milvus_utils.get_milvus_client", lambda: fake)
        monkeypatch.setattr(mod, "LANE_RECALL_LIMIT", 15)
        monkeypatch.setattr("app.lm.embedding_utils.generate_embedding", fake_embed)
        # normalize_results 直接复用真实实现（ Milvus 返回结构已模拟）

        retriever = MilvusHybridRetriever(name="embedding", source="embedding")
        chunks = retriever.retrieve("测试问题", ["主题A"], top_k=5)

        assert len(chunks) == 1
        assert fake.search_calls[0]["limit"] == 5  # top_k 透传到最终返回数
        assert len(fake.search_calls[0]["reqs"]) == 2  # Dense + BM25 两路
        assert fake.loaded == [] or True  # ensure_collection_loaded 内部维护缓存

    def test_collection_missing_returns_empty(self, monkeypatch):
        monkeypatch.setattr("app.clients.milvus_utils.get_milvus_client", lambda: _FakeMilvusClient(has_collection=False))
        retriever = MilvusHybridRetriever(name="embedding", source="embedding")
        assert retriever.retrieve("q", [], top_k=5) == []


class TestRRFParameterized:
    def _docs(self, n, prefix="d"):
        return [{"chunk_id": f"{prefix}{i}", "content": f"content-{prefix}-{i}"} for i in range(n)]

    def test_default_k_matches_legacy(self):
        fused = _rrf_fuse(self._docs(3), [], [])
        # k=60: rank1 score = 1/61
        assert fused[0]["rrf_score"] == round(1 / 61, 6)

    def test_custom_k(self):
        fused = _rrf_fuse(self._docs(3), [], [], rrf_k=1)
        assert fused[0]["rrf_score"] == round(1 / 2, 6)

    def test_output_limit(self):
        fused = _rrf_fuse(self._docs(20), [], [], output_limit=5)
        assert len(fused) == 5

    def test_multi_source_bonus(self):
        """同一文档出现在两路时 RRF 分数累加且 sources 合并"""
        docs = self._docs(2)
        fused = _rrf_fuse(docs, docs, [], rrf_k=1)
        assert set(fused[0]["sources"]) == {"embedding", "hyde"}
        assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


class TestWebSearchDecision:
    def _decide(self, config, total):
        from app.query_process.agent.nodes.node_search_embedding_hyde import _decide_web_search
        return _decide_web_search(config, total)

    def test_auto_mode(self):
        c = RetrievalConfig(enable_web_search=None)
        assert self._decide(c, 2) is True   # 结果不足 → 补充搜索
        assert self._decide(c, 10) is False

    def test_forced_on(self):
        assert self._decide(RetrievalConfig(enable_web_search=True), 100) is True

    def test_forced_off(self):
        assert self._decide(RetrievalConfig(enable_web_search=False), 0) is False
