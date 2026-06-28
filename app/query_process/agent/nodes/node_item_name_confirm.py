"""商品名确认节点：根据用户query在item_names集合中检索匹配的商品名"""
import sys
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


def node_item_name_confirm(state: QueryGraphState) -> QueryGraphState:
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    return state
