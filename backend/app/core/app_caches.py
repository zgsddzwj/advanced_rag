"""
应用级命名缓存注册（演进8）
统一登记全部业务缓存实例，便于健康检查与指标统一输出。
TTL 取自统一配置 settings；容量按数据特征设定：
- embedding: 文本→向量（1024 维浮点），容量上限考虑内存占用
- hyde_text: 查询→假设性回答（LLM 生成，成本高，收益大）
- web_search: 查询→联网结果（外部 API，30 分钟新鲜度）
- item_name_alignment: 主题名→对齐结果（依赖 Milvus 内容，短 TTL）
"""
from app.conf.settings import settings
from app.core.cache import register_cache

embedding_cache = register_cache(
    "embedding", maxsize=2048, ttl=settings.embedding_cache_ttl_seconds
)
hyde_cache = register_cache(
    "hyde_text", maxsize=512, ttl=settings.hyde_cache_ttl_seconds
)
web_search_cache = register_cache(
    "web_search", maxsize=256, ttl=settings.web_search_cache_ttl_seconds
)
alignment_cache = register_cache(
    "item_name_alignment", maxsize=1024, ttl=settings.alignment_cache_ttl_seconds
)
