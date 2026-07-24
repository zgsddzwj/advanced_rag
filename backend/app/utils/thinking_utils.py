"""
查询流程思考过程推送工具
在每个节点执行前后，通过 SSE 推送友好的中文描述，让用户了解当前进度
"""
from typing import Optional
from app.utils.sse_utils import push_to_session, SSEEvent
from app.core.logger import logger


# 查询流程节点 → 友好的中文描述映射
_THINKING_MESSAGES = {
    "node_item_name_confirm": {
        "start": "正在理解您的问题，并匹配相关的知识库文档...",
        "detail": "商品名对齐",
    },
    "node_search_embedding": {
        "start": "正在从知识库中检索相关内容（向量 + BM25 混合搜索）...",
        "detail": "向量检索",
    },
    "node_search_embedding_hyde": {
        "start": "正在生成假设性回答，并进行 HyDE 补充检索...",
        "detail": "HyDE 检索",
    },
    "node_web_search_mcp": {
        "start": "知识库中的信息可能不够完整，正在从网络搜索补充资料...",
        "detail": "网络搜索",
    },
    "node_rrf": {
        "start": "正在融合多路检索结果（RRF 算法）...",
        "detail": "RRF 融合",
    },
    "node_rerank": {
        "start": "正在对检索结果进行精排重排，筛选最相关的内容...",
        "detail": "Rerank 重排",
    },
    "node_answer_output": {
        "start": "正在基于检索到的内容，为您生成回答...",
        "detail": "生成回答",
    },
}


def push_thinking_start(task_id: str, node_name: str, is_stream: bool = True):
    """
    推送节点开始执行的思考过程
    """
    if not is_stream or not task_id:
        return

    msg_info = _THINKING_MESSAGES.get(node_name)
    if not msg_info:
        return

    message = msg_info["start"]
    detail = msg_info.get("detail", "")

    push_to_session(task_id, SSEEvent.THINKING, {
        "node": node_name,
        "message": message,
        "detail": detail,
    })
    logger.info(f"[思考过程] {message}")


def push_thinking_done(task_id: str, node_name: str, is_stream: bool = True, extra: Optional[str] = None):
    """
    推送节点完成的思考过程（可选附加信息）
    """
    if not is_stream or not task_id:
        return

    msg_info = _THINKING_MESSAGES.get(node_name)
    if not msg_info:
        return

    detail = msg_info.get("detail", "")
    if extra:
        message = f"{detail}完成 · {extra}"
    else:
        message = f"{detail}完成"

    push_to_session(task_id, SSEEvent.THINKING, {
        "node": node_name,
        "message": message,
        "detail": detail,
        "done": True,
    })
