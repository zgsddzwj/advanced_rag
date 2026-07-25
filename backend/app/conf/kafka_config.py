"""Kafka 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class KafkaConfig:
    # Kafka broker 地址（外部访问用 29092，容器间用 9092）
    BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")

    # Topic 名称
    TOPIC = os.getenv("KAFKA_TOPIC", "document-events")

    # Consumer Group
    CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "nexusrag-doc-sync")

    # 是否启用 Kafka（false 时降级为同步处理）
    ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() == "true"


kafka_config = KafkaConfig()
