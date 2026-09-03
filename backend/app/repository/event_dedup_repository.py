"""
事件处理与幂等去重仓储（演进6）
processed_events 集合：记录已成功消费的 event_id，配合 TTL 索引自动过期，
实现 Kafka at-least-once 投递下的消费幂等
"""
from datetime import datetime, timezone
from typing import Any, Optional

EVENT_DEDUP_COLLECTION = "processed_events"


class EventDedupRepository:
    """processed_events 集合仓储（可注入替身）"""

    def __init__(self, collection: Optional[Any] = None, ttl_days: int = 7):
        self._collection = collection
        self.ttl_days = ttl_days
        self._index_ready = False

    @property
    def collection(self):
        if self._collection is None:
            from app.repository.mongo_connection import get_mongo_db
            self._collection = get_mongo_db()[EVENT_DEDUP_COLLECTION]
        if not self._index_ready:
            try:
                # TTL 索引：processed_at 超过 ttl_days 的记录自动清理
                self._collection.create_index(
                    "processed_at",
                    expireAfterSeconds=self.ttl_days * 24 * 3600,
                )
                self._index_ready = True
            except Exception:
                pass  # 索引创建失败不阻塞消费，重试机制兜底
        return self._collection

    def is_processed(self, event_id: str) -> bool:
        try:
            return self.collection.find_one({"event_id": event_id}) is not None
        except Exception:
            # 去重探测失败时按未处理对待（重试/幂等写兜底）
            return False

    def mark_processed(self, event_id: str):
        """记录事件已成功消费"""
        self.collection.update_one(
            {"event_id": event_id},
            {"$set": {"event_id": event_id, "processed_at": datetime.now(timezone.utc)}},
            upsert=True,
        )


_repository = None


def get_event_dedup_repository() -> EventDedupRepository:
    global _repository
    if _repository is None:
        from app.conf.settings import settings
        _repository = EventDedupRepository(ttl_days=settings.event_dedup_ttl_days)
    return _repository
