"""
Rerank 客户端封装（gte-rerank via 百炼）
对文档列表进行精准重排序
"""
from typing import List, Dict, Any
import dashscope
from app.core.logger import logger
from app.conf.lm_config import lm_config


def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    text_field: str = "content",
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    调用 gte-rerank API 对文档进行重排序
    :param query: 查询文本
    :param documents: 待排序的文档列表（字典格式）
    :param text_field: 文档中提取文本的字段名
    :param top_n: 返回 Top N
    :return: 排序后的文档列表（新增 score 字段）
    """
    texts = [doc.get(text_field, "") for doc in documents]

    result = dashscope.TextReRank.call(
        model=lm_config.RERANK_MODEL,
        query=query,
        documents=texts,
        top_n=top_n,
        return_documents=False,
        api_key=lm_config.DASHSCOPE_API_KEY,
    )

    if result.status_code != 200:
        logger.error(f"Rerank API 调用失败: {result.message}")
        return documents[:top_n]

    scored_docs = []
    for item in result.output.results:
        idx = item["index"]
        doc = documents[idx].copy()
        doc["score"] = item["relevance_score"]
        scored_docs.append(doc)

    logger.info(f"Rerank 完成: {len(scored_docs)} 条文档，Top1 得分: {scored_docs[0]['score']:.4f}" if scored_docs else "Rerank 完成: 无结果")
    return scored_docs
