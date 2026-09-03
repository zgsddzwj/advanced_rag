"""
演进1 单元测试：统一配置中心 settings
- 默认值与环境变量覆盖
- 校验器（fail-fast）
- 敏感信息脱敏
- 旧配置模块兼容 shim
"""
import pytest
from pydantic import ValidationError

from app.conf.settings import Settings, settings


@pytest.fixture
def clean_env(monkeypatch):
    """清空所有配置相关环境变量 + 禁用 .env 文件，保证测试隔离"""
    env_keys = [
        "DASHSCOPE_API_KEY", "LLM_MODEL_NAME", "LLM_BASE_URL",
        "VLM_MODEL_NAME", "VLM_BASE_URL", "EMBEDDING_MODEL_NAME",
        "EMBEDDING_DIMENSION", "EMBEDDING_BASE_URL", "RERANK_MODEL_NAME",
        "BAILIAN_MCP_APP_ID", "MILVUS_URL", "CHUNKS_COLLECTION",
        "ITEM_NAMES_COLLECTION", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY",
        "MINIO_SECRET_KEY", "MINIO_BUCKET_NAME", "MINIO_SECURE",
        "MINIO_PDF_DIR", "MINIO_IMG_DIR", "MONGO_URL", "MONGO_DB_NAME",
        "KAFKA_ENABLED", "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC",
        "KAFKA_CONSUMER_GROUP", "MINERU_BASE_URL", "MINERU_API_TOKEN",
        "LOG_CONSOLE_ENABLE", "LOG_CONSOLE_LEVEL", "LOG_FILE_ENABLE",
        "LOG_FILE_LEVEL", "LOG_FILE_RETENTION", "LOG_FILE_ENCODING",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def make_settings(**kwargs) -> Settings:
    """构造不读取 .env 文件的隔离 Settings 实例"""
    return Settings(_env_file=None, **kwargs)


class TestDefaults:
    def test_default_llm_models(self, clean_env):
        s = make_settings()
        assert s.llm_model_name == "qwen-plus"
        assert s.vlm_model_name == "qwen-vl-plus"
        assert s.embedding_model_name == "text-embedding-v3"
        assert s.embedding_dimension == 1024
        assert s.rerank_model_name == "gte-rerank"

    def test_default_infra(self, clean_env):
        s = make_settings()
        assert s.milvus_url == "http://localhost:19530"
        assert s.chunks_collection == "kb_chunks"
        assert s.minio_endpoint == "localhost:9000"
        assert s.mongo_url == "mongodb://localhost:27017"
        assert s.kafka_enabled is True
        assert s.kafka_bootstrap_servers == "localhost:29092"
        assert s.kafka_topic == "document-events"


class TestEnvOverride:
    def test_env_override(self, clean_env):
        clean_env.setenv("EMBEDDING_DIMENSION", "768")
        clean_env.setenv("KAFKA_ENABLED", "false")
        clean_env.setenv("MINIO_SECURE", "true")
        s = make_settings()
        assert s.embedding_dimension == 768
        assert s.kafka_enabled is False
        assert s.minio_secure is True

    def test_case_insensitive(self, clean_env):
        """环境变量大小写不敏感匹配"""
        clean_env.setenv("llm_model_name", "qwen-max")
        assert make_settings().llm_model_name == "qwen-max"


class TestValidators:
    def test_embedding_dimension_bounds(self, clean_env):
        with pytest.raises(ValidationError):
            make_settings(embedding_dimension=0)
        with pytest.raises(ValidationError):
            make_settings(embedding_dimension=99999)

    def test_log_level_normalized(self, clean_env):
        clean_env.setenv("LOG_CONSOLE_LEVEL", "warn")
        assert make_settings().log_console_level == "WARNING"

    def test_invalid_log_level_rejected(self, clean_env):
        clean_env.setenv("LOG_FILE_LEVEL", "VERBOSE")
        with pytest.raises(ValidationError):
            make_settings()

    def test_kafka_bootstrap_required_when_enabled(self, clean_env):
        with pytest.raises(ValidationError):
            make_settings(kafka_enabled=True, kafka_bootstrap_servers="  ")

    def test_kafka_bootstrap_optional_when_disabled(self, clean_env):
        s = make_settings(kafka_enabled=False, kafka_bootstrap_servers="")
        assert s.kafka_bootstrap_servers == ""


class TestMasking:
    def test_mask_long_key(self):
        masked = Settings._mask("sk-1234567890abcdefxyz", keep_head=8, keep_tail=4)
        assert masked == "sk-12345...fxyz"
        assert "90abcdef" not in masked

    def test_mask_empty(self):
        assert Settings._mask("") == "<未配置>"

    def test_describe_masks_secrets(self, clean_env):
        s = make_settings(dashscope_api_key="sk-secret-key-123456789")
        summary = s.describe()
        assert "sk-secret" not in str(summary)
        assert summary["llm"]["api_key"] == "sk-secre...6789"

    def test_configured_flags(self, clean_env):
        s = make_settings()
        assert s.dashscope_key_configured is False  # 未配置
        s = make_settings(dashscope_api_key="sk-real-key-abcdefg")
        assert s.dashscope_key_configured is True
        s = make_settings(dashscope_api_key="sk-xxxx-placeholder")
        assert s.dashscope_key_configured is False


class TestBackwardCompatShims:
    """旧配置模块 shim 必须保持属性名与取值兼容"""

    def test_lm_config_shim(self):
        from app.conf.lm_config import lm_config
        assert lm_config.DASHSCOPE_API_KEY == settings.dashscope_api_key
        assert lm_config.LLM_MODEL == settings.llm_model_name
        assert lm_config.EMBEDDING_DIM == settings.embedding_dimension
        assert lm_config.RERANK_MODEL == settings.rerank_model_name

    def test_milvus_config_shim(self):
        from app.conf.milvus_config import milvus_config
        assert milvus_config.MILVUS_URL == settings.milvus_url
        assert milvus_config.CHUNKS_COLLECTION == settings.chunks_collection

    def test_kafka_config_shim(self):
        from app.conf.kafka_config import kafka_config
        assert kafka_config.ENABLED == settings.kafka_enabled
        assert kafka_config.TOPIC == settings.kafka_topic

    def test_minio_config_shim(self):
        from app.conf.minio_config import minio_config
        assert minio_config.ENDPOINT == settings.minio_endpoint
        assert minio_config.SECURE == settings.minio_secure

    def test_mineru_config_shim(self):
        from app.conf.mineru_config import mineru_config
        assert mineru_config.BASE_URL == settings.mineru_base_url

    def test_bailian_mcp_config_shim(self):
        from app.conf.bailian_mcp_config import bailian_mcp_config
        assert bailian_mcp_config.BAILIAN_MCP_APP_ID == settings.bailian_mcp_app_id
