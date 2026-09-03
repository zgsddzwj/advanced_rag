"""
[兼容层] 百炼 MCP 配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class BailianMCPConfig:
    BAILIAN_MCP_APP_ID = settings.bailian_mcp_app_id
    DASHSCOPE_API_KEY = settings.dashscope_api_key


bailian_mcp_config = BailianMCPConfig()
