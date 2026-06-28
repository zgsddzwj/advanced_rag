"""MinerU API 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class MineruConfig:
    BASE_URL = os.getenv("MINERU_BASE_URL", "https://mineru.net/api/v4")
    API_TOKEN = os.getenv("MINERU_API_TOKEN", "")


mineru_config = MineruConfig()
