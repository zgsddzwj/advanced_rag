"""
检索策略配置（演进7：检索管线可插拔）
按请求携带的检索参数，全部字段有默认值，缺省时行为与历史版本完全一致。
"""
from typing import Optional

from pydantic import BaseModel, Field


class RetrievalConfig(BaseModel):
    """
    单次查询的检索策略
    - enable_hyde: 是否执行 HyDE 假设性回答补充检索
    - enable_web_search: 三态开关 —— None=自动（按检索结果数量动态判断），
      True=强制联网搜索，False=禁用
    - top_k: 每路检索最终返回的文档数
    - rrf_k: RRF 平滑因子（越大各路排名差异越平缓）
    - rrf_output_limit: RRF 融合后送入 Rerank 的最大文档数
    - web_search_count: 联网搜索返回结果数
    """
    enable_hyde: bool = True
    enable_web_search: Optional[bool] = None
    top_k: int = Field(default=10, ge=1, le=30)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    rrf_output_limit: int = Field(default=15, ge=1, le=50)
    web_search_count: int = Field(default=5, ge=1, le=20)


STATE_KEY = "retrieval_config"


def get_retrieval_config(state: dict) -> RetrievalConfig:
    """从 LangGraph 状态读取检索配置（缺失/非法时回退默认值）"""
    raw = state.get(STATE_KEY)
    if not raw:
        return RetrievalConfig()
    try:
        return RetrievalConfig.model_validate(raw)
    except Exception:
        return RetrievalConfig()
