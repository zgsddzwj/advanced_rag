"""百炼 MCP 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class BailianMCPConfig:
    BAILIAN_MCP_APP_ID = os.getenv("BAILIAN_MCP_APP_ID", "")
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


bailian_mcp_config = BailianMCPConfig()
