"""
[兼容层] MongoDB 对话历史工具
演进3 后数据访问统一由 app.repository.chat_history_repository 提供，
本模块仅为历史引用保留。新代码请使用：
    from app.repository import get_chat_history_repository

注：演进前本模块在导入期即建立 MongoDB 连接（基础设施未就绪时每个进程
都要付出超时等待）；现连接已下沉至仓储层懒加载，导入本模块零开销。
"""
from app.repository.chat_history_repository import get_chat_history_repository


def save_chat_message(
    session_id: str,
    role: str,
    text: str,
    rewritten_query: str = "",
    item_names: list = None,
    image_urls: list = None,
    message_id: str = None,
) -> str:
    """写入/更新单条会话记录（委托仓储）"""
    return get_chat_history_repository().save_message(
        session_id=session_id,
        role=role,
        text=text,
        rewritten_query=rewritten_query,
        item_names=item_names,
        image_urls=image_urls,
        message_id=message_id,
    )


def get_recent_messages(session_id: str, limit: int = 10) -> list:
    """查询指定会话的最近 N 条对话记录（时间正序）"""
    return get_chat_history_repository().get_recent(session_id, limit=limit)


def clear_history(session_id: str) -> int:
    """清空指定会话的所有历史对话"""
    return get_chat_history_repository().clear(session_id)


def get_message_count(session_id: str) -> int:
    """获取指定会话的消息总数"""
    return get_chat_history_repository().count(session_id)
