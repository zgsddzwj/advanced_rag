"""
网络搜索客户端封装（百炼 MCP）
通过百炼 MCP 联网搜索获取互联网实时信息
"""
from typing import List, Dict, Any
import dashscope
from app.core.logger import logger
from app.conf.bailian_mcp_config import bailian_mcp_config


def web_search(query: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    调用百炼 MCP 联网搜索
    :param query: 搜索查询词
    :param count: 返回结果数量
    :return: 搜索结果列表 [{title, url, content, source}, ...]
    """
    result = dashscope.Application.call(
        api_key=bailian_mcp_config.DASHSCOPE_API_KEY,
        app_id=bailian_mcp_config.BAILIAN_MCP_APP_ID,
        prompt=query,
    )

    if result.status_code != 200:
        logger.error(f"百炼 MCP 搜索失败: {result.message}")
        return []

    # 解析搜索结果，统一格式
    docs = []
    output_text = result.output.choices[0].message.content if hasattr(result.output, 'choices') else str(result.output)

    # 如果返回的是结构化数据，按结构解析；否则包装为单个文档
    if isinstance(output_text, list):
        for item in output_text:
            docs.append({
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "content": item.get("snippet", item.get("content", "")),
                "source": "web",
            })
    else:
        docs.append({
            "title": query,
            "url": "",
            "content": str(output_text),
            "source": "web",
        })

    logger.info(f"网络搜索完成: 查询='{query}'，返回 {len(docs)} 条结果")
    return docs[:count]
