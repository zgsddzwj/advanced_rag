"""
统一配置中心（演进1：配置层架构升级）
================================================
基于 pydantic-settings 的类型安全配置，取代原先 6 个分散的配置类：

- 单一配置源：所有模块只从 `settings` 读取，消除 os.getenv 散落各处的问题
- 启动时校验：类型错误、非法取值在进程启动瞬间即失败（fail-fast），而非运行中期才暴露
- 环境变量契约 100% 兼容：字段名与 .env 中历史变量名一一对应（大小写不敏感），
  已有的 backend/.env 与部署环境无需任何修改
- 密钥脱敏：describe() 输出配置摘要时自动掩码敏感项，可安全用于启动日志与健康检查

用法：
    from app.conf.settings import settings
    settings.dashscope_api_key
"""
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（settings.py 位于 backend/app/conf/ 下）
BACKEND_DIR = Path(__file__).resolve().parents[2]

# .env 文件固定从 backend/ 目录加载（与历史 load_dotenv 行为一致，
# 不受进程启动时的工作目录影响）
_ENV_FILE = BACKEND_DIR / ".env"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """
    全局统一配置
    字段名与 .env 环境变量名一一对应（pydantic-settings 默认大小写不敏感匹配）
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===================== 阿里云百炼 API（LLM / VLM / Embedding / Rerank） =====================
    dashscope_api_key: str = Field(default="", description="百炼统一 API Key")

    # LLM (Qwen-Plus)
    llm_model_name: str = "qwen-plus"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # VLM (Qwen-VL-Plus)
    vlm_model_name: str = "qwen-vl-plus"
    vlm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Embedding (text-embedding-v3)
    embedding_model_name: str = "text-embedding-v3"
    embedding_dimension: int = Field(default=1024, ge=1, le=4096)
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Rerank (gte-rerank)
    rerank_model_name: str = "gte-rerank"

    # ===================== 百炼 MCP（网络搜索） =====================
    bailian_mcp_app_id: str = ""

    # ===================== Milvus =====================
    milvus_url: str = "http://localhost:19530"
    chunks_collection: str = "kb_chunks"
    item_names_collection: str = "kb_item_names"

    # ===================== MinIO =====================
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "kb-import-bucket"
    minio_secure: bool = False
    minio_pdf_dir: str = "pdf_files"
    minio_img_dir: str = "images"

    # ===================== MongoDB =====================
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "kb002"
    mongo_server_selection_timeout_ms: int = Field(default=5000, ge=1000,
                                                   description="MongoDB serverSelection 超时（毫秒）")

    # ===================== Kafka =====================
    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_topic: str = "document-events"
    kafka_consumer_group: str = "nexusrag-doc-sync"
    # 死信队列 topic：重试耗尽的事件转入 DLQ 人工排查（演进6）
    kafka_dlq_topic: str = "document-events-dlq"
    # 事件处理重试策略（演进6）
    kafka_event_retry_max: int = Field(default=3, ge=0, description="单事件最大重试次数")
    kafka_event_retry_delay_seconds: float = Field(default=5.0, ge=0, description="重试基础间隔（秒）")
    # 消费幂等：event_id 去重记录保留天数（TTL 索引自动清理）
    event_dedup_ttl_days: int = Field(default=7, ge=1)

    # ===================== MinerU（PDF 解析） =====================
    mineru_base_url: str = "https://mineru.net/api/v4"
    mineru_api_token: str = ""

    # ===================== 日志 =====================
    log_console_enable: bool = True
    log_console_level: LogLevel = "INFO"
    log_file_enable: bool = True
    log_file_level: LogLevel = "INFO"
    log_file_retention: str = "7 days"
    log_file_encoding: str = "utf-8"

    # ===================== 缓存（演进8：多级缓存） =====================
    embedding_cache_ttl_seconds: int = Field(default=21600, ge=60, description="Embedding 缓存 TTL（6h）")
    hyde_cache_ttl_seconds: int = Field(default=3600, ge=60, description="HyDE 假设回答缓存 TTL（1h）")
    web_search_cache_ttl_seconds: int = Field(default=1800, ge=60, description="联网搜索缓存 TTL（30min）")
    alignment_cache_ttl_seconds: int = Field(default=600, ge=60, description="主题对齐缓存 TTL（10min）")

    # ===================== 校验器 =====================

    @field_validator("log_console_level", "log_file_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v):
        """日志级别统一大写并映射 python/logging 与 loguru 均可识别的取值"""
        if isinstance(v, str):
            v = v.strip().upper()
            if v == "WARN":
                v = "WARNING"
        return v

    @field_validator("kafka_bootstrap_servers")
    @classmethod
    def _validate_kafka_bootstrap(cls, v: str, info):
        """Kafka 启用时 broker 地址不能为空，避免消费者启动后无限重连"""
        if info.data.get("kafka_enabled") and not v.strip():
            raise ValueError("KAFKA_BOOTSTRAP_SERVERS 不能为空（KAFKA_ENABLED=true 时必填）")
        return v

    @field_validator("log_file_retention")
    @classmethod
    def _validate_retention(cls, v: str) -> str:
        """loguru retention 必须是数字+单位形式（如 '7 days'）"""
        v = v.strip()
        if not v:
            raise ValueError("LOG_FILE_RETENTION 不能为空")
        return v

    # ===================== 派生属性 =====================

    @property
    def dashscope_key_configured(self) -> bool:
        """百炼 API Key 是否已配置真实值（非空且非占位符）"""
        key = self.dashscope_api_key
        return bool(key) and not key.startswith("sk-xxxx")

    @property
    def mineru_token_configured(self) -> bool:
        """MinerU Token 是否已配置真实值"""
        token = self.mineru_api_token
        return bool(token) and not token.startswith("your_")

    @property
    def bailian_mcp_configured(self) -> bool:
        """百炼 MCP App ID 是否已配置真实值"""
        app_id = self.bailian_mcp_app_id
        return bool(app_id) and not app_id.startswith("your_")

    # ===================== 工具方法 =====================

    @staticmethod
    def _mask(secret: str, keep_head: int = 8, keep_tail: int = 4) -> str:
        """敏感值脱敏：保留首尾少量字符，中间掩码"""
        if not secret:
            return "<未配置>"
        if len(secret) <= keep_head + keep_tail:
            return "*" * len(secret)
        return f"{secret[:keep_head]}...{secret[-keep_tail:]}"

    def describe(self) -> dict:
        """
        输出配置摘要（敏感项自动掩码）
        用于启动日志、健康检查等场景，禁止直接序列化 settings 本体
        """
        return {
            "llm": {
                "model": self.llm_model_name,
                "api_key": self._mask(self.dashscope_api_key),
                "embedding_dim": self.embedding_dimension,
                "rerank": self.rerank_model_name,
            },
            "vlm": {"model": self.vlm_model_name},
            "milvus": {
                "url": self.milvus_url,
                "chunks_collection": self.chunks_collection,
                "item_names_collection": self.item_names_collection,
            },
            "minio": {
                "endpoint": self.minio_endpoint,
                "bucket": self.minio_bucket_name,
                "secure": self.minio_secure,
            },
            "mongo": {"db": self.mongo_db_name},
            "kafka": {
                "enabled": self.kafka_enabled,
                "brokers": self.kafka_bootstrap_servers,
                "topic": self.kafka_topic,
                "consumer_group": self.kafka_consumer_group,
            },
            "mineru": {
                "base_url": self.mineru_base_url,
                "token": self._mask(self.mineru_api_token),
            },
            "bailian_mcp": {
                "app_id": self.bailian_mcp_app_id or "<未配置>",
            },
            "log": {
                "console": f"{self.log_console_level}" if self.log_console_enable else "off",
                "file": f"{self.log_file_level}" if self.log_file_enable else "off",
            },
        }


# 全局单例：所有模块统一从这里读取配置
settings = Settings()
