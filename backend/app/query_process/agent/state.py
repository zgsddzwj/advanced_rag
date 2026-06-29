"""检索流程图状态定义"""
import copy
from typing import TypedDict, List, Dict, Any


class QueryGraphState(TypedDict):
    """检索图状态，所有节点共享"""
    session_id: str
    task_id: str

    # 用户输入
    query: str
    rewritten_query: str

    # 对话历史
    history: list

    # 商品名对齐
    item_names: List[str]

    # 检索结果 —— 各路独立
    embedding_chunks: list        # 节点2: 正常向量+BM25混合检索
    hyde_text: str                # 节点3: HyDE生成的假设性回答文本
    hyde_chunks: list             # 节点3: HyDE检索结果
    web_search_docs: list         # 节点4: 网络搜索结果

    # 融合与重排
    rrf_chunks: list              # 节点5: RRF融合结果
    reranked_docs: list           # 节点6: Rerank重排结果

    # 回答
    answer: str
    image_urls: List[str]
    prompt: str

    # 流程控制
    need_web_search: bool
    is_stream: bool


graph_default_state: QueryGraphState = {
    "session_id": "",
    "task_id": "",
    "query": "",
    "rewritten_query": "",
    "history": [],
    "item_names": [],
    "embedding_chunks": [],
    "hyde_text": "",
    "hyde_chunks": [],
    "web_search_docs": [],
    "rrf_chunks": [],
    "reranked_docs": [],
    "answer": "",
    "image_urls": [],
    "prompt": "",
    "need_web_search": False,
    "is_stream": False,
}


def create_default_state(**overrides) -> QueryGraphState:
    """创建默认状态，支持覆盖"""
    state = copy.deepcopy(graph_default_state)
    state.update(overrides)
    return state
