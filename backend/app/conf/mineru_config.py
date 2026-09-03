"""
[兼容层] MinerU API 配置
演进1 后所有配置统一由 app.conf.settings 提供，本模块仅为历史引用保留。
新代码请使用：from app.conf.settings import settings
"""
from app.conf.settings import settings


class MineruConfig:
    BASE_URL = settings.mineru_base_url
    API_TOKEN = settings.mineru_api_token


mineru_config = MineruConfig()
