"""
[兼容层] Kafka 配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class KafkaConfig:
    BOOTSTRAP_SERVERS = settings.kafka_bootstrap_servers
    TOPIC = settings.kafka_topic
    CONSUMER_GROUP = settings.kafka_consumer_group
    ENABLED = settings.kafka_enabled


kafka_config = KafkaConfig()
