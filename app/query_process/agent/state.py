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

    # 商品名对齐
    item_names: List[str]

    # 检索结果
    dense_vector: List[float]
    search_results: List[Dict[str, Any]]
    web_results: List[Dict[str, Any]]
    merged_results: List[Dict[str, Any]]
    reranked_results: List[Dict[str, Any]]

    # 回答
    answer: str

    # 图片
    image_urls: List[str]

    # 流程控制
    need_web_search: bool


graph_default_state: QueryGraphState = {
    "session_id": "",
    "task_id": "",
    "query": "",
    "rewritten_query": "",
    "item_names": [],
    "dense_vector": [],
    "search_results": [],
    "web_results": [],
    "merged_results": [],
    "reranked_results": [],
    "answer": "",
    "image_urls": [],
    "need_web_search": False,
}


def create_default_state(**overrides) -> QueryGraphState:
    """创建默认状态，支持覆盖"""
    state = copy.deepcopy(graph_default_state)
    state.update(overrides)
    return state
