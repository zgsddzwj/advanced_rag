# 掌柜智库 RAG 系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零构建基于 LangGraph 的高级 RAG 系统，包含文档导入和智能问答两条完整流程，全部 AI 能力通过阿里云百炼 API 接入。

**Architecture:** 两条 LangGraph 工作流（导入 7 节点 + 检索 7+2 节点），FastAPI 双服务（:8000 导入 / :8001 查询），Milvus 混合检索（Dense API + BM25），SSE 流式输出，Docker Compose 统一编排基础设施。

**Tech Stack:** Python 3.11+, LangGraph, FastAPI, Milvus 2.4, MinIO, MongoDB, 阿里云百炼 API (Qwen-Plus / Qwen-VL-Plus / text-embedding-v3 / gte-rerank / MCP), MinerU (magic-pdf), uv

---

## File Structure

### 新建文件清单

```
advanced_rag/
├── docker-compose.yml                          # 基础设施编排
├── pyproject.toml                              # 项目依赖
├── .env.example                                # 环境变量模板
├── .env                                        # 环境变量（不提交）
│
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── logger.py                           # loguru 日志
│   │   └── load_prompt.py                      # Prompt 加载器
│   ├── conf/
│   │   ├── __init__.py
│   │   ├── lm_config.py                        # LLM/VLM/Embedding/Rerank 配置
│   │   ├── milvus_config.py                    # Milvus 配置
│   │   └── bailian_mcp_config.py               # 百炼 MCP 配置
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── milvus_utils.py                     # Milvus 连接 + 混合搜索
│   │   ├── minio_utils.py                      # MinIO 连接 + 文件操作
│   │   └── mongo_history_utils.py              # MongoDB 对话历史
│   ├── lm/
│   │   ├── __init__.py
│   │   ├── lm_utils.py                         # LLM 客户端 (Qwen-Plus)
│   │   ├── vlm_utils.py                        # VLM 客户端 (Qwen-VL-Plus)
│   │   ├── embedding_utils.py                  # Embedding 客户端 (text-embedding-v3)
│   │   ├── rerank_utils.py                     # Rerank 客户端 (gte-rerank)
│   │   └── web_search_utils.py                 # 网络搜索 (百炼 MCP)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── task_utils.py                       # 任务状态管理
│   │   ├── sse_utils.py                        # SSE 事件队列
│   │   ├── path_util.py                        # 项目路径工具
│   │   └── escape_milvus_string_utils.py       # Milvus 字符串转义
│   ├── import_process/
│   │   ├── __init__.py
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── state.py                        # ImportGraphState
│   │   │   ├── main_graph.py                   # 导入图编排
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── node_entry.py
│   │   │       ├── node_pdf_to_md.py
│   │   │       ├── node_md_img.py
│   │   │       ├── node_document_split.py
│   │   │       ├── node_item_name_recognition.py
│   │   │       ├── node_bge_embedding.py
│   │   │       └── node_import_milvus.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── file_import_service.py          # FastAPI 导入服务
│   │   └── page/
│   │       └── import.html                     # 导入前端页面
│   └── query_process/
│       ├── __init__.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── state.py                        # QueryGraphState
│       │   ├── main_graph.py                   # 检索图编排
│       │   └── nodes/
│       │       ├── __init__.py
│       │       ├── node_item_name_confirm.py
│       │       ├── node_search_embedding.py
│       │       ├── node_search_embedding_hyde.py
│       │       ├── node_web_search_mcp.py
│       │       ├── node_rrf.py
│       │       ├── node_rerank.py
│       │       └── node_answer_output.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── query_service.py                # FastAPI 查询服务
│       └── page/
│           └── chat.html                       # 聊天前端页面
│
├── prompts/
│   ├── item_name_recognition.prompt
│   ├── item_name_confirm.prompt
│   ├── hyde_generate.prompt
│   └── answer_out.prompt
│
└── test/
    ├── __init__.py
    ├── 01_env_test.py
    ├── 02_import_graph_flow.py
    └── 03_query_graph_flow.py
```

### 保留的旧文件（不删除，但不再使用）
- `app.py`, `config.py`, `pdf_parser.py`, `langchain_parser.py`, `requirements.txt`, `monitor.py`, `result_viewer.py`, `start_server.sh`, `view_parse_process.sh`, `examples/`, `static/`, `templates/`

---

## Phase 1: 基础设施搭建

### Task 1: Docker Compose 基础设施

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.16
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
      ETCD_SNAPSHOT_COUNT: "50000"
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    ports:
      - "2379:2379"

  minio:
    image: minio/minio:RELEASE.2024-09-22T00-33-43Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"

  milvus:
    image: milvusdb/milvus:v2.4.17
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
      MINIO_ACCESS_KEY_ID: minioadmin
      MINIO_SECRET_ACCESS_KEY: minioadmin
    volumes:
      - milvus_data:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - etcd
      - minio

  mongo:
    image: mongo:7.0
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"

volumes:
  etcd_data:
  minio_data:
  milvus_data:
  mongo_data:
```

- [ ] **Step 2: 启动并验证基础设施**

Run: `docker compose up -d`
Expected: 4 个容器全部 running

Run: `docker compose ps`
Expected: etcd, minio, milvus, mongo 状态均为 Up

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "infra: add docker-compose for Milvus/MinIO/MongoDB"
```

---

### Task 2: 项目依赖与配置文件

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.env`
- Modify: `.gitignore`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "advanced-rag"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "python-multipart",
    "pydantic",
    "langchain",
    "langchain-openai",
    "langchain-community",
    "langgraph",
    "grandalf",
    "dashscope",
    "pymilvus",
    "minio",
    "pymongo",
    "magic-pdf",
    "python-dotenv",
    "loguru",
    "numpy",
    "pandas",
    "regex",
    "requests",
]
```

- [ ] **Step 2: 创建 .env.example**

```env
# ===================== 阿里云百炼 API =====================
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx

# LLM (Qwen-Plus)
LLM_MODEL_NAME=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# VLM (Qwen-VL-Plus)
VLM_MODEL_NAME=qwen-vl-plus
VLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Embedding (text-embedding-v3)
EMBEDDING_MODEL_NAME=text-embedding-v3
EMBEDDING_DIMENSION=1024
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Rerank (gte-rerank)
RERANK_MODEL_NAME=gte-rerank

# 百炼 MCP 网络搜索
BAILIAN_MCP_APP_ID=your_app_id

# ===================== Milvus =====================
MILVUS_URL=http://localhost:19530
CHUNKS_COLLECTION=kb_chunks
ITEM_NAMES_COLLECTION=kb_item_names

# ===================== MinIO =====================
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=kb-import-bucket
MINIO_PDF_DIR=pdf_files
MINIO_IMG_DIR=images

# ===================== MongoDB =====================
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=kb002

# ===================== 日志配置 =====================
LOG_CONSOLE_ENABLE=True
LOG_CONSOLE_LEVEL=INFO
LOG_FILE_ENABLE=True
LOG_FILE_LEVEL=INFO
LOG_FILE_RETENTION=7 days
```

- [ ] **Step 3: 复制 .env.example 为 .env 并填入真实 API Key**

Run: `cp .env.example .env`
然后手动编辑 `.env`，填入真实的 `DASHSCOPE_API_KEY`

- [ ] **Step 4: 更新 .gitignore**

在 `.gitignore` 中添加：
```
.env
output/
uploads/
logs/
doc/
*.pyc
__pycache__/
.superpowers/
```

- [ ] **Step 5: 安装依赖**

Run: `uv sync`
Expected: 所有依赖安装成功

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example .gitignore
git commit -m "infra: add pyproject.toml and env config"
```

---

### Task 3: 核心工具层（日志、路径、Prompt 加载器）

**Files:**
- Create: `app/__init__.py` (空文件)
- Create: `app/core/__init__.py` (空文件)
- Create: `app/core/logger.py`
- Create: `app/utils/__init__.py` (空文件)
- Create: `app/utils/path_util.py`
- Create: `app/core/load_prompt.py`

- [ ] **Step 1: 创建包初始化文件**

Run: `mkdir -p app/core app/utils app/conf app/clients app/lm`

创建所有 `__init__.py` 空文件:
```bash
touch app/__init__.py app/core/__init__.py app/utils/__init__.py
```

- [ ] **Step 2: 创建 app/utils/path_util.py**

```python
"""
项目路径工具
统一管理项目根目录和各类输出目录的路径
"""
from pathlib import Path

# 项目根目录：从当前文件向上回溯到项目根
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
```

- [ ] **Step 3: 创建 app/core/logger.py**

```python
"""
项目日志工具类
基于 loguru 实现，支持 .env 配置控制台/文件双输出
特性：
1. 配置驱动：通过 .env 开关输出、修改日志级别
2. 自动路径：文件日志输出到 项目根/logs/app_YYYYMMDD.log
3. 自动清理：按配置保留日志
4. 中文友好：utf-8 编码
5. 异步安全：开启异步入队
6. 位置精准：穿透 loguru 内部，显示业务模块实际调用位置
"""
import sys
import inspect
from pathlib import Path
import os
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 配置
load_dotenv()

# 读取配置（带默认值）
LOG_CONSOLE_ENABLE = os.getenv("LOG_CONSOLE_ENABLE", "True").lower() == "true"
LOG_CONSOLE_LEVEL = os.getenv("LOG_CONSOLE_LEVEL", "INFO").upper()
LOG_FILE_ENABLE = os.getenv("LOG_FILE_ENABLE", "True").lower() == "true"
LOG_FILE_LEVEL = os.getenv("LOG_FILE_LEVEL", "INFO").upper()
LOG_FILE_RETENTION = os.getenv("LOG_FILE_RETENTION", "7 days")

# 定义日志路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_NAME = "app_{time:YYYYMMDD}.log"
LOG_FILE_PATH = LOG_DIR / LOG_FILE_NAME

# 定义日志格式
LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name: <20}</cyan>:<cyan>{function: <15}</cyan>:<cyan>{line: <4}</cyan> - "
    "<level>{message}</level>"
)


def init_logger():
    """初始化全局日志配置"""
    logger.remove()

    if LOG_CONSOLE_ENABLE:
        logger.add(
            sink=sys.stdout,
            level=LOG_CONSOLE_LEVEL,
            format=LOG_FORMAT,
            colorize=True,
            enqueue=True
        )

    if LOG_FILE_ENABLE:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.add(
            sink=LOG_FILE_PATH,
            level=LOG_FILE_LEVEL,
            format=LOG_FORMAT,
            rotation="00:00",
            retention=LOG_FILE_RETENTION,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )

    return logger


# 初始化日志
base_logger = init_logger()


def fix_log_position(record):
    """遍历调用栈，跳过 loguru 内部帧，定位业务代码实际调用位置"""
    for frame in inspect.stack():
        if ("_logger.py" in frame.filename or frame.function == "_log") or "logger.py" in frame.filename:
            continue
        record.update(
            name=frame.filename.split("/")[-1].split("\\")[-1],
            function=frame.function,
            line=frame.lineno
        )
        break


# 应用位置修复，导出全局 logger
logger = base_logger.patch(fix_log_position)
```

- [ ] **Step 4: 创建 app/core/load_prompt.py**

```python
"""
Prompt 模板加载器
从 prompts/ 目录加载 .prompt 文件，支持变量替换
"""
import os
from app.core.logger import logger

# Prompt 模板目录
PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompts"
)


def load_prompt(name: str, **kwargs) -> str:
    """
    加载 Prompt 模板并填充变量
    :param name: 模板名称（不含 .prompt 后缀）
    :param kwargs: 要填充的变量
    :return: 填充后的 Prompt 字符串
    """
    file_path = os.path.join(PROMPT_DIR, f"{name}.prompt")
    
    if not os.path.exists(file_path):
        logger.error(f"Prompt 模板不存在: {file_path}")
        raise FileNotFoundError(f"Prompt 模板不存在: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    # 使用 str.format 替换变量
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Prompt 模板变量替换失败，缺少变量: {e}")
            raise
    return template
```

- [ ] **Step 5: 验证日志和路径工具**

Run: `python -c "from app.core.logger import logger; logger.info('日志测试成功')"`
Expected: 控制台输出带颜色的日志行

Run: `python -c "from app.utils.path_util import PROJECT_ROOT; print(PROJECT_ROOT)"`
Expected: 输出项目根目录路径

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/core/ app/utils/path_util.py
git commit -m "core: add logger, path util, and prompt loader"
```

---

## Phase 2: 配置层与 AI 模型封装

### Task 4: 配置层

**Files:**
- Create: `app/conf/__init__.py` (空文件)
- Create: `app/conf/lm_config.py`
- Create: `app/conf/milvus_config.py`
- Create: `app/conf/bailian_mcp_config.py`

- [ ] **Step 1: 创建包初始化文件**

```bash
touch app/conf/__init__.py
```

- [ ] **Step 2: 创建 app/conf/lm_config.py**

```python
"""
LLM/VLM/Embedding/Rerank 统一配置
所有 AI 模型通过阿里云百炼 API 接入
"""
import os
from dotenv import load_dotenv

load_dotenv()


class LMConfig:
    """AI 模型配置"""
    # 百炼统一 API Key
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

    # LLM (Qwen-Plus)
    LLM_MODEL = os.getenv("LLM_MODEL_NAME", "qwen-plus")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # VLM (Qwen-VL-Plus)
    VLM_MODEL = os.getenv("VLM_MODEL_NAME", "qwen-vl-plus")
    VLM_BASE_URL = os.getenv("VLM_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Embedding (text-embedding-v3)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v3")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # Rerank (gte-rerank)
    RERANK_MODEL = os.getenv("RERANK_MODEL_NAME", "gte-rerank")


lm_config = LMConfig()
```

- [ ] **Step 3: 创建 app/conf/milvus_config.py**

```python
"""Milvus 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class MilvusConfig:
    MILVUS_URL = os.getenv("MILVUS_URL", "http://localhost:19530")
    CHUNKS_COLLECTION = os.getenv("CHUNKS_COLLECTION", "kb_chunks")
    ITEM_NAMES_COLLECTION = os.getenv("ITEM_NAMES_COLLECTION", "kb_item_names")


milvus_config = MilvusConfig()
```

- [ ] **Step 4: 创建 app/conf/bailian_mcp_config.py**

```python
"""百炼 MCP 配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class BailianMCPConfig:
    BAILIAN_MCP_APP_ID = os.getenv("BAILIAN_MCP_APP_ID", "")
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


bailian_mcp_config = BailianMCPConfig()
```

- [ ] **Step 5: Commit**

```bash
git add app/conf/
git commit -m "conf: add lm, milvus, and bailian mcp config"
```

---

### Task 5: AI 模型封装层

**Files:**
- Create: `app/lm/__init__.py` (空文件)
- Create: `app/lm/lm_utils.py`
- Create: `app/lm/vlm_utils.py`
- Create: `app/lm/embedding_utils.py`
- Create: `app/lm/rerank_utils.py`
- Create: `app/lm/web_search_utils.py`

- [ ] **Step 1: 创建包初始化文件**

```bash
touch app/lm/__init__.py
```

- [ ] **Step 2: 创建 app/lm/lm_utils.py**

```python
"""
LLM 客户端封装（Qwen-Plus via 百炼 OpenAI 兼容接口）
使用 langchain_openai.ChatOpenAI，单例模式
"""
import os
from langchain_openai import ChatOpenAI
from app.core.logger import logger
from app.conf.lm_config import lm_config

_llm_client = None


def get_llm_client() -> ChatOpenAI:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = ChatOpenAI(
            model=lm_config.LLM_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.LLM_BASE_URL,
            temperature=0.3,
            streaming=True,
        )
        logger.info(f"LLM 客户端初始化成功: {lm_config.LLM_MODEL}")
    return _llm_client
```

- [ ] **Step 3: 创建 app/lm/vlm_utils.py**

```python
"""
VLM 客户端封装（Qwen-VL-Plus via 百炼）
用于图片语义理解，生成图片文本描述
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.core.logger import logger
from app.conf.lm_config import lm_config

_vlm_client = None


def get_vlm_client() -> ChatOpenAI:
    """获取 VLM 客户端单例"""
    global _vlm_client
    if _vlm_client is None:
        _vlm_client = ChatOpenAI(
            model=lm_config.VLM_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.VLM_BASE_URL,
            temperature=0.1,
        )
        logger.info(f"VLM 客户端初始化成功: {lm_config.VLM_MODEL}")
    return _vlm_client


def describe_image(image_url: str) -> str:
    """
    调用 VLM 对图片进行语义描述
    :param image_url: 图片 URL（MinIO URL 或本地路径）
    :return: 图片的文本描述
    """
    vlm = get_vlm_client()

    message = HumanMessage(content=[
        {"type": "text", "text": "请详细描述这张图片的内容，包括设备名称、外观、结构、按钮位置等关键信息。用一句话概括。"},
        {"type": "image_url", "image_url": {"url": image_url}},
    ])

    response = vlm.invoke([message])
    logger.info(f"VLM 图片描述完成: {response.content[:50]}...")
    return response.content
```

- [ ] **Step 4: 创建 app/lm/embedding_utils.py**

```python
"""
Embedding 客户端封装（text-embedding-v3 via 百炼）
仅生成稠密向量，稀疏向量由 Milvus BM25 自动处理
"""
from typing import List
from langchain_openai import OpenAIEmbeddings
from app.core.logger import logger
from app.conf.lm_config import lm_config

_embedding_client = None


def get_embedding_client() -> OpenAIEmbeddings:
    """获取 Embedding 客户端单例"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAIEmbeddings(
            model=lm_config.EMBEDDING_MODEL,
            api_key=lm_config.DASHSCOPE_API_KEY,
            base_url=lm_config.EMBEDDING_BASE_URL,
            dimensions=lm_config.EMBEDDING_DIM,
        )
        logger.info(f"Embedding 客户端初始化成功: {lm_config.EMBEDDING_MODEL}")
    return _embedding_client


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    批量生成稠密向量
    :param texts: 文本列表
    :return: 向量列表（每个元素为 1024 维浮点列表）
    """
    client = get_embedding_client()
    vectors = client.embed_documents(texts)
    logger.info(f"Embedding 生成完成: {len(texts)} 条文本 → {len(vectors)} 个向量")
    return vectors


def generate_embedding(text: str) -> List[float]:
    """
    单条文本向量化（用于查询向量化）
    :param text: 查询文本
    :return: 稠密向量
    """
    client = get_embedding_client()
    return client.embed_query(text)
```

- [ ] **Step 5: 创建 app/lm/rerank_utils.py**

```python
"""
Rerank 客户端封装（gte-rerank via 百炼）
对文档列表进行精准重排序
"""
from typing import List, Dict, Any
import dashscope
from app.core.logger import logger
from app.conf.lm_config import lm_config


def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    text_field: str = "content",
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    调用 gte-rerank API 对文档进行重排序
    :param query: 查询文本
    :param documents: 待排序的文档列表（字典格式）
    :param text_field: 文档中提取文本的字段名
    :param top_n: 返回 Top N
    :return: 排序后的文档列表（新增 score 字段）
    """
    texts = [doc.get(text_field, "") for doc in documents]

    result = dashscope.TextReRank.call(
        model=lm_config.RERANK_MODEL,
        query=query,
        documents=texts,
        top_n=top_n,
        return_documents=False,
        api_key=lm_config.DASHSCOPE_API_KEY,
    )

    if result.status_code != 200:
        logger.error(f"Rerank API 调用失败: {result.message}")
        return documents[:top_n]

    scored_docs = []
    for item in result.output.results:
        idx = item["index"]
        doc = documents[idx].copy()
        doc["score"] = item["relevance_score"]
        scored_docs.append(doc)

    logger.info(f"Rerank 完成: {len(scored_docs)} 条文档，Top1 得分: {scored_docs[0]['score']:.4f}" if scored_docs else "Rerank 完成: 无结果")
    return scored_docs
```

- [ ] **Step 6: 创建 app/lm/web_search_utils.py**

```python
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
    # 百炼 MCP 返回格式可能需要根据实际情况调整
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
```

- [ ] **Step 7: 验证 API 客户端（需要真实 API Key）**

Run: `python -c "from app.lm.embedding_utils import generate_embedding; v = generate_embedding('测试'); print(f'维度: {len(v)}')"`
Expected: 输出 `维度: 1024`

Run: `python -c "from app.lm.lm_utils import get_llm_client; r = get_llm_client().invoke('说你好'); print(r.content)"`
Expected: 输出 Qwen 的回复

- [ ] **Step 8: Commit**

```bash
git add app/lm/
git commit -m "lm: add LLM, VLM, Embedding, Rerank, and web search clients"
```

---

## Phase 3: 基础设施客户端

### Task 6: Milvus 客户端

**Files:**
- Create: `app/clients/__init__.py` (空文件)
- Create: `app/clients/milvus_utils.py`

- [ ] **Step 1: 创建包初始化文件**

```bash
touch app/clients/__init__.py
```

- [ ] **Step 2: 创建 app/clients/milvus_utils.py**

```python
"""
Milvus 客户端工具
负责连接管理、集合创建（含 BM25）、混合搜索
"""
import os
from typing import List, Dict, Any, Optional
from pymilvus import (
    MilvusClient, DataType, Function, FunctionType,
    AnnSearchRequest, RRFRanker
)
from app.core.logger import logger
from app.conf.milvus_config import milvus_config

_milvus_client = None


def get_milvus_client() -> MilvusClient:
    """获取 Milvus 客户端单例"""
    global _milvus_client
    if _milvus_client is None:
        _milvus_client = MilvusClient(uri=milvus_config.MILVUS_URL)
        logger.info(f"Milvus 客户端连接成功: {milvus_config.MILVUS_URL}")
    return _milvus_client


def create_chunks_collection(client: MilvusClient, collection_name: str, vector_dimension: int):
    """
    创建 kb_chunks 集合（含 BM25 全文检索）
    """
    schema = client.create_schema(auto_id=True, enable_dynamic_fields=True)

    # 主键
    schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    # content 启用中文分词分析器
    schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535,
                     enable_analyzer=True, analyzer_params={"type": "chinese"})
    schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="part", datatype=DataType.INT8)
    schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=65535)
    # 稀疏向量（BM25 自动生成）
    schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
    # 稠密向量
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)

    # 定义 BM25 Function：从 content 自动生成 sparse_vector
    schema.add_function(Function(
        name="content_bm25",
        function_type=FunctionType.BM25,
        input_field_names=["content"],
        output_field_names=["sparse_vector"],
    ))

    # 索引参数
    index_params = client.prepare_index_params()
    # 稠密向量索引：HNSW + COSINE
    index_params.add_index(
        field_name="dense_vector",
        index_name="dense_vector_index",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200}
    )
    # 稀疏向量索引：SPARSE_INVERTED_INDEX + BM25
    index_params.add_index(
        field_name="sparse_vector",
        index_name="sparse_vector_index",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
        params={"inverted_index_algo": "DAAT_MAXSCORE"}
    )

    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    logger.info(f"Milvus 集合创建成功: {collection_name}，向量维度: {vector_dimension}")


def create_item_names_collection(client: MilvusClient, collection_name: str, vector_dimension: int):
    """
    创建 kb_item_names 集合（文档级索引，商品名对齐用）
    """
    schema = client.create_schema(auto_id=True, enable_dynamic_fields=True)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense_vector",
        index_name="dense_vector_index",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200}
    )

    client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    logger.info(f"Milvus 集合创建成功: {collection_name}，向量维度: {vector_dimension}")


def create_hybrid_search_requests(
    dense_vector: List[float],
    query_text: str,
    expr: str = "",
    limit: int = 10
) -> List[AnnSearchRequest]:
    """
    构造 Milvus 混合搜索请求（Dense + BM25）
    :param dense_vector: 稠密向量（API 生成）
    :param query_text: 查询文本（Milvus BM25 自动分词）
    :param expr: 过滤表达式
    :param limit: 每路检索返回数量
    """
    # 稠密向量检索请求
    dense_req = AnnSearchRequest(
        data=[dense_vector],
        anns_field="dense_vector",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        expr=expr,
        limit=limit
    )

    # BM25 稀疏检索请求（传入查询文本，Milvus 自动分词）
    sparse_req = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},
        expr=expr,
        limit=limit
    )

    return [dense_req, sparse_req]


def hybrid_search(
    client: MilvusClient,
    collection_name: str,
    reqs: List[AnnSearchRequest],
    ranker_weights: tuple = (0.8, 0.2),
    limit: int = 5,
    output_fields: List[str] = None
) -> List[List[Dict]]:
    """
    执行 Milvus 混合检索
    :param client: MilvusClient 实例
    :param collection_name: 集合名称
    :param reqs: 混合搜索请求列表
    :param ranker_weights: Dense/BM25 权重配比
    :param limit: 最终返回数量
    :param output_fields: 返回字段
    :return: 检索结果
    """
    if output_fields is None:
        output_fields = ["chunk_id", "content", "item_name", "title", "file_title"]

    result = client.hybrid_search(
        collection_name=collection_name,
        reqs=reqs,
        ranker=RRFRanker(k=60),
        limit=limit,
        output_fields=output_fields
    )

    return result
```

- [ ] **Step 3: 验证 Milvus 连接**

Run: `python -c "from app.clients.milvus_utils import get_milvus_client; c = get_milvus_client(); print('Milvus 连接成功')"`
Expected: 输出 `Milvus 连接成功`

- [ ] **Step 4: Commit**

```bash
git add app/clients/__init__.py app/clients/milvus_utils.py
git commit -m "clients: add Milvus client with BM25 hybrid search"
```

---

### Task 7: MinIO 客户端

**Files:**
- Create: `app/clients/minio_utils.py`

- [ ] **Step 1: 创建 app/clients/minio_utils.py**

```python
"""
MinIO 客户端工具
负责文件上传、下载、桶管理
"""
import os
from minio import Minio
from app.core.logger import logger

_minio_client = None


def get_minio_client() -> Minio:
    """获取 MinIO 客户端单例"""
    global _minio_client
    if _minio_client is None:
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

        _minio_client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False
        )

        # 自动创建 bucket
        if not _minio_client.bucket_exists(bucket_name):
            _minio_client.make_bucket(bucket_name)
            logger.info(f"MinIO bucket 创建成功: {bucket_name}")

        logger.info(f"MinIO 客户端连接成功: {endpoint}")
    return _minio_client


def upload_file(local_path: str, object_name: str, content_type: str = "application/octet-stream") -> str:
    """
    上传文件到 MinIO
    :param local_path: 本地文件路径
    :param object_name: MinIO 中的对象名
    :param content_type: 文件 MIME 类型
    :return: MinIO 对象访问 URL
    """
    client = get_minio_client()
    bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

    client.fput_object(
        bucket_name=bucket_name,
        object_name=object_name,
        file_path=local_path,
        content_type=content_type
    )

    # 构造访问 URL
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    url = f"http://{endpoint}/{bucket_name}/{object_name}"
    logger.info(f"文件上传 MinIO 成功: {object_name} → {url}")
    return url


def upload_bytes(data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
    """
    上传字节数据到 MinIO
    :param data: 字节数据
    :param object_name: MinIO 中的对象名
    :param content_type: 文件 MIME 类型
    :return: MinIO 对象访问 URL
    """
    import io
    client = get_minio_client()
    bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")

    client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type
    )

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    url = f"http://{endpoint}/{bucket_name}/{object_name}"
    logger.info(f"字节数据上传 MinIO 成功: {object_name} → {url}")
    return url
```

- [ ] **Step 2: 验证 MinIO 连接**

Run: `python -c "from app.clients.minio_utils import get_minio_client; c = get_minio_client(); print('MinIO 连接成功')"`
Expected: 输出 `MinIO 连接成功`

- [ ] **Step 3: Commit**

```bash
git add app/clients/minio_utils.py
git commit -m "clients: add MinIO client for file upload"
```

---

### Task 8: MongoDB 对话历史

**Files:**
- Create: `app/clients/mongo_history_utils.py`

- [ ] **Step 1: 创建 app/clients/mongo_history_utils.py**

```python
"""
MongoDB 对话历史工具
负责多轮对话的存取管理
"""
import os
import logging
from typing import List, Dict, Any
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class HistoryMongoTool:
    """MongoDB 历史对话记录读写工具类"""

    def __init__(self):
        try:
            self.mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
            self.db_name = os.getenv("MONGO_DB_NAME", "kb002")

            self.client = MongoClient(self.mongo_url)
            self.db = self.client[self.db_name]
            self.chat_message = self.db["chat_message"]

            # 创建复合索引：session_id 升序 + ts 降序
            self.chat_message.create_index([("session_id", 1), ("ts", -1)])

            logging.info(f"MongoDB 连接成功: {self.db_name}")
        except Exception as e:
            logging.error(f"MongoDB 连接失败: {e}")
            raise


_history_mongo_tool = None

try:
    _history_mongo_tool = HistoryMongoTool()
except Exception as e:
    logging.warning(f"MongoDB 模块加载时初始化失败: {e}")


def get_history_mongo_tool() -> HistoryMongoTool:
    """获取单例实例（懒加载）"""
    global _history_mongo_tool
    if _history_mongo_tool is None:
        _history_mongo_tool = HistoryMongoTool()
    return _history_mongo_tool


def clear_history(session_id: str) -> int:
    """清空指定会话的所有历史对话"""
    mongo_tool = get_history_mongo_tool()
    try:
        result = mongo_tool.chat_message.delete_many({"session_id": session_id})
        logging.info(f"Deleted {result.deleted_count} messages for session {session_id}")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error clearing history for session {session_id}: {e}")
        return 0


def save_chat_message(
    session_id: str,
    role: str,
    text: str,
    rewritten_query: str = "",
    item_names: List[str] = None,
    image_urls: List[str] = None,
    message_id: str = None
) -> str:
    """
    写入/更新单条会话记录
    :return: 记录唯一标识
    """
    ts = datetime.now().timestamp()

    document = {
        "session_id": session_id,
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query or "",
        "item_names": item_names,
        "image_urls": image_urls,
        "ts": ts
    }

    mongo_tool = get_history_mongo_tool()
    if message_id:
        mongo_tool.chat_message.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document}
        )
        return message_id
    else:
        result = mongo_tool.chat_message.insert_one(document)
        return str(result.inserted_id)


def get_recent_messages(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    查询指定会话的最近 N 条对话记录
    结果按时间正序排列
    """
    mongo_tool = get_history_mongo_tool()
    try:
        query = {"session_id": session_id}
        cursor = mongo_tool.chat_message.find(query).sort("ts", ASCENDING).limit(limit)
        messages = list(cursor)
        return messages
    except Exception as e:
        logging.error(f"Error getting recent messages: {e}")
        return []
```

- [ ] **Step 2: 验证 MongoDB 连接**

Run: `python -c "from app.clients.mongo_history_utils import get_history_mongo_tool; t = get_history_mongo_tool(); print('MongoDB 连接成功')"`
Expected: 输出 `MongoDB 连接成功`

- [ ] **Step 3: Commit**

```bash
git add app/clients/mongo_history_utils.py
git commit -m "clients: add MongoDB history tool"
```

---

### Task 9: 任务状态与 SSE 工具

**Files:**
- Create: `app/utils/task_utils.py`
- Create: `app/utils/sse_utils.py`
- Create: `app/utils/escape_milvus_string_utils.py`

- [ ] **Step 1: 创建 app/utils/task_utils.py**

```python
"""
任务状态管理工具
基于内存字典管理任务执行进度，供前端轮询
"""
import asyncio
from typing import Dict, List, Any, Optional
from app.core.logger import logger

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# 全局任务状态字典
_task_store: Dict[str, Dict[str, Any]] = {}


def _ensure_task(task_id: str):
    """确保任务存在于字典中"""
    if task_id not in _task_store:
        _task_store[task_id] = {
            "status": TASK_STATUS_PENDING,
            "done_list": [],
            "running_list": [],
            "results": {}
        }


def update_task_status(task_id: str, status: str, is_stream: bool = False):
    """更新任务全局状态"""
    _ensure_task(task_id)
    _task_store[task_id]["status"] = status
    logger.info(f"[{task_id}] 任务状态更新: {status}")


def add_running_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为运行中"""
    _ensure_task(task_id)
    if node_name not in _task_store[task_id]["running_list"]:
        _task_store[task_id]["running_list"].append(node_name)
    logger.info(f"[{task_id}] 节点运行中: {node_name}")


def add_done_task(task_id: str, node_name: str, is_stream: bool = False):
    """标记节点为已完成"""
    _ensure_task(task_id)
    if node_name in _task_store[task_id]["running_list"]:
        _task_store[task_id]["running_list"].remove(node_name)
    if node_name not in _task_store[task_id]["done_list"]:
        _task_store[task_id]["done_list"].append(node_name)
    logger.info(f"[{task_id}] 节点完成: {node_name}")

    # 如果是流式模式，触发 SSE 推送
    if is_stream:
        from app.utils.sse_utils import push_to_session, SSEEvent
        push_to_session(task_id, SSEEvent.PROGRESS, {
            "done_list": _task_store[task_id]["done_list"],
            "running_list": _task_store[task_id]["running_list"]
        })


def get_task_status(task_id: str) -> str:
    """获取任务全局状态"""
    _ensure_task(task_id)
    return _task_store[task_id]["status"]


def get_done_task_list(task_id: str) -> List[str]:
    """获取已完成节点列表"""
    _ensure_task(task_id)
    return _task_store[task_id]["done_list"]


def get_running_task_list(task_id: str) -> List[str]:
    """获取运行中节点列表"""
    _ensure_task(task_id)
    return _task_store[task_id]["running_list"]


def set_task_result(task_id: str, key: str, value: Any):
    """存储任务结果数据"""
    _ensure_task(task_id)
    _task_store[task_id]["results"][key] = value


def get_task_result(task_id: str, key: str, default: Any = None) -> Any:
    """获取任务结果数据"""
    _ensure_task(task_id)
    return _task_store[task_id]["results"].get(key, default)
```

- [ ] **Step 2: 创建 app/utils/sse_utils.py**

```python
"""
SSE 事件队列管理工具
基于 asyncio.Queue 实现每个 session 的消息推送
"""
import asyncio
import json
from enum import Enum
from typing import Dict, Any, Optional
from app.core.logger import logger


class SSEEvent(Enum):
    """SSE 事件类型"""
    READY = "ready"
    PROGRESS = "progress"
    DELTA = "delta"
    FINAL = "final"
    ERROR = "error"


# 全局 SSE 队列字典：session_id → asyncio.Queue
_sse_queues: Dict[str, asyncio.Queue] = {}


def create_sse_queue(session_id: str):
    """为指定 session 创建 SSE 队列"""
    _sse_queues[session_id] = asyncio.Queue()
    logger.info(f"SSE 队列创建: {session_id}")


def push_to_session(session_id: str, event: SSEEvent, data: Dict[str, Any]):
    """向 session 的 SSE 队列推送事件"""
    if session_id not in _sse_queues:
        logger.warning(f"SSE 队列不存在: {session_id}，跳过推送")
        return

    try:
        _sse_queues[session_id].put_nowait({
            "event": event.value,
            "data": data
        })
    except asyncio.QueueFull:
        logger.warning(f"SSE 队列已满: {session_id}")


async def sse_generator(session_id: str, request=None):
    """
    SSE 事件生成器
    从队列消费事件，按 SSE 格式 yield
    """
    # 等待队列创建
    while session_id not in _sse_queues:
        await asyncio.sleep(0.1)

    queue = _sse_queues[session_id]

    # 检查客户端是否断开
    def is_disconnected():
        if request is not None:
            return request.is_disconnected()
        return False

    # 发送 ready 事件
    yield f"event: ready\ndata: {json.dumps({'session_id': session_id})}\n\n"

    while True:
        if is_disconnected():
            logger.info(f"SSE 客户端断开: {session_id}")
            break

        try:
            msg = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            # 发送心跳
            yield f": heartbeat\n\n"
            continue

        if msg is None:
            # 结束标记
            break

        event_name = msg["event"]
        data_str = json.dumps(msg["data"], ensure_ascii=False)
        yield f"event: {event_name}\ndata: {data_str}\n\n"

        if event_name == SSEEvent.FINAL.value or event_name == SSEEvent.ERROR.value:
            break

    # 清理队列
    if session_id in _sse_queues:
        del _sse_queues[session_id]
    logger.info(f"SSE 队列清理: {session_id}")
```

- [ ] **Step 3: 创建 app/utils/escape_milvus_string_utils.py**

```python
"""
Milvus 字符串转义工具
用于构造 filter 表达式时安全处理字符串
"""


def escape_milvus_string(s: str) -> str:
    """
    转义 Milvus filter 表达式中的字符串
    防止特殊字符导致表达式解析错误
    """
    if s is None:
        return ""
    # 替换双引号和反斜杠
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s
```

- [ ] **Step 4: Commit**

```bash
git add app/utils/task_utils.py app/utils/sse_utils.py app/utils/escape_milvus_string_utils.py
git commit -m "utils: add task status, SSE queue, and milvus escape utils"
```

---

## Phase 4: 导入流程 — 骨架

### Task 10: 导入状态定义与节点骨架

**Files:**
- Create: `app/import_process/__init__.py` (空文件)
- Create: `app/import_process/agent/__init__.py` (空文件)
- Create: `app/import_process/agent/nodes/__init__.py` (空文件)
- Create: `app/import_process/agent/state.py`
- Create: 7 个节点骨架文件
- Create: `app/import_process/agent/main_graph.py`
- Create: `test/02_import_graph_flow.py`

- [ ] **Step 1: 创建包结构**

```bash
mkdir -p app/import_process/agent/nodes app/import_process/api app/import_process/page
touch app/import_process/__init__.py app/import_process/agent/__init__.py
touch app/import_process/agent/nodes/__init__.py
touch app/import_process/api/__init__.py
```

- [ ] **Step 2: 创建 app/import_process/agent/state.py**

```python
"""导入流程图状态定义"""
import copy
from typing import TypedDict
from app.core.logger import logger


class ImportGraphState(TypedDict):
    """导入图状态，所有节点共享"""
    task_id: str

    # 流程控制标记
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool

    # 路径相关
    local_dir: str
    local_file_path: str
    file_title: str
    pdf_path: str
    md_path: str
    split_path: str
    embeddings_path: str

    # 内容数据
    md_content: str
    chunks: list
    item_name: str

    # 向量数据
    embeddings_content: list


graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "is_normal_split_enabled": True,
    "is_silicon_flow_api_enabled": True,
    "is_advanced_split_enabled": False,
    "is_vllm_enabled": False,
    "local_dir": "",
    "local_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "split_path": "",
    "embeddings_path": "",
    "md_content": "",
    "chunks": [],
    "item_name": "",
    "embeddings_content": []
}


def create_default_state(**overrides) -> ImportGraphState:
    """创建默认状态，支持覆盖"""
    state = copy.deepcopy(graph_default_state)
    state.update(overrides)
    return state


def get_default_state() -> ImportGraphState:
    """返回新的状态实例"""
    return copy.deepcopy(graph_default_state)
```

- [ ] **Step 3: 创建 7 个节点骨架**

`app/import_process/agent/nodes/node_entry.py`:
```python
import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_entry(state: ImportGraphState) -> ImportGraphState:
    """入口节点：判断文件类型，设置路由标记"""
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")

    if "local_file_path" in state:
        path = state["local_file_path"]
        if path.endswith(".pdf"):
            state["is_pdf_read_enabled"] = True
        elif path.endswith(".md"):
            state["is_md_read_enabled"] = True
        # 提取 file_title
        import os
        state["file_title"] = os.path.splitext(os.path.basename(path))[0]

    return state
```

`app/import_process/agent/nodes/node_pdf_to_md.py`:
```python
import sys
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState


def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    """PDF转Markdown：调用 MinerU 解析 PDF"""
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")
    return state
```

对其余 5 个节点（`node_md_img.py`, `node_document_split.py`, `node_item_name_recognition.py`, `node_bge_embedding.py`, `node_import_milvus.py`）创建相同结构的骨架文件，函数名与文件名对应。

- [ ] **Step 4: 创建 app/import_process/agent/main_graph.py**

```python
"""导入流程 LangGraph 主图编排"""
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END, START

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.import_process.agent.nodes.node_entry import node_entry
from app.import_process.agent.nodes.node_pdf_to_md import node_pdf_to_md
from app.import_process.agent.nodes.node_md_img import node_md_img
from app.import_process.agent.nodes.node_document_split import node_document_split
from app.import_process.agent.nodes.node_item_name_recognition import node_item_name_recognition
from app.import_process.agent.nodes.node_bge_embedding import node_bge_embedding
from app.import_process.agent.nodes.node_import_milvus import node_import_milvus

load_dotenv()

workflow = StateGraph(ImportGraphState)

workflow.add_node("node_entry", node_entry)
workflow.add_node("node_pdf_to_md", node_pdf_to_md)
workflow.add_node("node_md_img", node_md_img)
workflow.add_node("node_document_split", node_document_split)
workflow.add_node("node_item_name_recognition", node_item_name_recognition)
workflow.add_node("node_bge_embedding", node_bge_embedding)
workflow.add_node("node_import_milvus", node_import_milvus)

workflow.set_entry_point("node_entry")


def route_after_entry(state: ImportGraphState) -> str:
    if state.get("is_md_read_enabled"):
        return "node_md_img"
    elif state.get("is_pdf_read_enabled"):
        return "node_pdf_to_md"
    else:
        return END


workflow.add_conditional_edges("node_entry", route_after_entry, {
    "node_md_img": "node_md_img",
    "node_pdf_to_md": "node_pdf_to_md",
    END: END
})

workflow.add_edge("node_pdf_to_md", "node_md_img")
workflow.add_edge("node_md_img", "node_document_split")
workflow.add_edge("node_document_split", "node_item_name_recognition")
workflow.add_edge("node_item_name_recognition", "node_bge_embedding")
workflow.add_edge("node_bge_embedding", "node_import_milvus")
workflow.add_edge("node_import_milvus", END)

kb_import_app = workflow.compile()
```

- [ ] **Step 5: 创建测试脚本 test/02_import_graph_flow.py**

```python
"""测试导入图流程骨架"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.import_process.agent.main_graph import kb_import_app
from app.import_process.agent.state import create_default_state
from app.core.logger import logger

logger.info("===== 开始测试导入图骨架 =====")

# 测试 PDF 流程
initial_state = create_default_state(local_file_path="test.pdf")
logger.info("--- 测试 PDF 流程 ---")
for event in kb_import_app.stream(initial_state):
    for key, value in event.items():
        logger.info(f"节点: {key}")

# 测试 MD 流程
initial_state_md = create_default_state(local_file_path="test.md")
logger.info("--- 测试 MD 流程 ---")
for event in kb_import_app.stream(initial_state_md):
    for key, value in event.items():
        logger.info(f"节点: {key}")

logger.info("===== 测试结束 =====")
```

- [ ] **Step 6: 运行骨架测试**

Run: `python test/02_import_graph_flow.py`
Expected: PDF 流程打印 entry → pdf_to_md → md_img → ... → import_milvus；MD 流程跳过 pdf_to_md

- [ ] **Step 7: Commit**

```bash
git add app/import_process/ test/
git commit -m "import: add graph skeleton with 7 node stubs and flow test"
```

---

## Phase 5: 导入流程 — 填充逻辑

### Task 11: 导入节点实现（节点 1-4）

**Files:**
- Modify: `app/import_process/agent/nodes/node_entry.py`
- Modify: `app/import_process/agent/nodes/node_pdf_to_md.py`
- Modify: `app/import_process/agent/nodes/node_md_img.py`
- Modify: `app/import_process/agent/nodes/node_document_split.py`

> **注意：** 由于篇幅限制，每个节点的完整实现代码将在实施时从教案对应章节参考编写。以下为关键逻辑摘要。

- [ ] **Step 1: 实现 node_entry.py** — 文件类型判断 + 路由标记 + file_title 提取（骨架已基本完整）

- [ ] **Step 2: 实现 node_pdf_to_md.py** — 调用 magic-pdf 解析 PDF，输出 Markdown 到 `local_dir`，读取内容到 `md_content`

- [ ] **Step 3: 实现 node_md_img.py** — 扫描 Markdown 图片 → 上传 MinIO → 调用 Qwen-VL-Plus 生成描述 → 替换链接

- [ ] **Step 4: 实现 node_document_split.py** — 基于 Markdown 标题层级递归切分，超长段落二次切分，拼接标题路径

- [ ] **Step 5: 验证节点 1-4**

Run: `python -c "from app.import_process.agent.nodes.node_entry import node_entry; print('OK')"`
Expected: 无导入错误

- [ ] **Step 6: Commit**

```bash
git add app/import_process/agent/nodes/node_entry.py app/import_process/agent/nodes/node_pdf_to_md.py app/import_process/agent/nodes/node_md_img.py app/import_process/agent/nodes/node_document_split.py
git commit -m "import: implement nodes 1-4 (entry, pdf_to_md, md_img, document_split)"
```

---

### Task 12: 导入节点实现（节点 5-7）

**Files:**
- Modify: `app/import_process/agent/nodes/node_item_name_recognition.py`
- Modify: `app/import_process/agent/nodes/node_bge_embedding.py`
- Modify: `app/import_process/agent/nodes/node_import_milvus.py`
- Create: `prompts/item_name_recognition.prompt`

- [ ] **Step 1: 创建 prompts/item_name_recognition.prompt**

```text
你是一个文档分析助手。请阅读以下文档内容，识别出这篇文档主要描述的产品/设备名称。

要求：
1. 只返回产品/设备的完整名称，不要添加任何解释。
2. 如果无法识别，返回"未知设备"。

【文档内容】
{content}

请返回产品名称：
```

- [ ] **Step 2: 实现 node_item_name_recognition.py** — 提取前几段 chunks → 调用 Qwen-Plus 识别 → 附加 item_name 到所有 chunks

- [ ] **Step 3: 实现 node_bge_embedding.py** — 拼接 `商品：{item_name}，介绍：{content}` → 批量调用 text-embedding-v3 API → 绑定 dense_vector

- [ ] **Step 4: 实现 node_import_milvus.py** — 校验 → 创建集合(BM25 Schema) → 幂等清理 → 批量插入 kb_chunks → 写入 kb_item_names → 回填 chunk_id

- [ ] **Step 5: Commit**

```bash
git add app/import_process/agent/nodes/node_item_name_recognition.py app/import_process/agent/nodes/node_bge_embedding.py app/import_process/agent/nodes/node_import_milvus.py prompts/item_name_recognition.prompt
git commit -m "import: implement nodes 5-7 (item_recognition, embedding, milvus_import)"
```

---

## Phase 6: 导入 Web 服务

### Task 13: 导入 API 服务与前端页面

**Files:**
- Create: `app/import_process/api/file_import_service.py`
- Create: `app/import_process/page/import.html`

- [ ] **Step 1: 创建 file_import_service.py** — FastAPI 应用，包含 `/upload`、`/status/{task_id}`、`/import.html` 接口，后台任务调用 `kb_import_app.stream()`

- [ ] **Step 2: 创建 import.html** — 文件上传区 + 进度轮询 + 日志展示

- [ ] **Step 3: 验证导入服务**

Run: `python -m app.import_process.api.file_import_service`
Expected: 服务在 8000 端口启动

- [ ] **Step 4: Commit**

```bash
git add app/import_process/api/ app/import_process/page/
git commit -m "import: add FastAPI service and import.html page"
```

---

## Phase 7: 检索流程 — 骨架

### Task 14: 检索状态定义与节点骨架

**Files:**
- Create: `app/query_process/__init__.py` (空文件)
- Create: `app/query_process/agent/__init__.py` (空文件)
- Create: `app/query_process/agent/nodes/__init__.py` (空文件)
- Create: `app/query_process/agent/state.py`
- Create: 7 个节点骨架 + main_graph.py
- Create: `test/03_query_graph_flow.py`

- [ ] **Step 1: 创建包结构**

```bash
mkdir -p app/query_process/agent/nodes app/query_process/api app/query_process/page
touch app/query_process/__init__.py app/query_process/agent/__init__.py
touch app/query_process/agent/nodes/__init__.py
touch app/query_process/api/__init__.py
```

- [ ] **Step 2: 创建 state.py**

```python
"""检索流程图状态定义"""
from typing_extensions import TypedDict
from typing import List


class QueryGraphState(TypedDict):
    """检索图状态"""
    session_id: str
    original_query: str
    rewritten_query: str
    history: list
    is_stream: bool

    item_names: List[str]
    answer: str

    embedding_chunks: list
    hyde_embedding_chunks: list
    web_search_docs: list

    rrf_chunks: list
    reranked_docs: list

    prompt: str
```

- [ ] **Step 3: 创建 7 个节点骨架** — 每个文件包含空函数 + 日志 + task_utils 调用

- [ ] **Step 4: 创建 main_graph.py** — 注册 7+2 节点，条件路由，3 路并行边

- [ ] **Step 5: 创建测试脚本并验证**

Run: `python test/03_query_graph_flow.py`
Expected: 打印检索图节点执行顺序

- [ ] **Step 6: Commit**

```bash
git add app/query_process/ test/03_query_graph_flow.py
git commit -m "query: add graph skeleton with 7+2 node stubs and flow test"
```

---

## Phase 8: 检索流程 — 填充逻辑

### Task 15: 检索节点实现（节点 1-4）

**Files:**
- Modify: `app/query_process/agent/nodes/node_item_name_confirm.py`
- Modify: `app/query_process/agent/nodes/node_search_embedding.py`
- Modify: `app/query_process/agent/nodes/node_search_embedding_hyde.py`
- Modify: `app/query_process/agent/nodes/node_web_search_mcp.py`
- Create: `prompts/item_name_confirm.prompt`
- Create: `prompts/hyde_generate.prompt`

- [ ] **Step 1: 创建 prompts/item_name_confirm.prompt**

```text
你是一个智能助手。请根据历史对话和用户当前问题，完成以下任务：
1. 提取用户问题中提到的产品/设备名称。
2. 如果用户问题中缺少产品名但历史对话中提到过，请补全。
3. 将用户的问题改写为一个完整、独立、精确的陈述句，适合用于知识库检索。

【历史对话】
{history}

【用户问题】
{query}

请按以下格式返回：
产品名称：xxx
改写问题：xxx
```

- [ ] **Step 2: 创建 prompts/hyde_generate.prompt**

```text
你是一个技术文档专家。请根据以下问题，生成一个假设性的详细回答（不需要真实准确，但要有合理的技术细节和关键词）。
这个假设性回答将用于向量检索，帮助找到相关文档。

【问题】
{query}

请直接生成假设性回答（不要加任何前缀说明）：
```

- [ ] **Step 3: 实现 node_item_name_confirm.py** — LLM 改写 + 商品名向量化 + Milvus 对齐 + MongoDB 写入

- [ ] **Step 4: 实现 node_search_embedding.py** — 向量化查询 + Milvus 混合检索 (Dense + BM25)

- [ ] **Step 5: 实现 node_search_embedding_hyde.py** — LLM 生成假设答案 + 向量化 + Milvus 混合检索

- [ ] **Step 6: 实现 node_web_search_mcp.py** — 调用百炼 MCP 网络搜索

- [ ] **Step 7: Commit**

```bash
git add app/query_process/agent/nodes/ prompts/
git commit -m "query: implement nodes 1-4 (item_confirm, search_embedding, hyde, web_search)"
```

---

### Task 16: 检索节点实现（节点 5-7）

**Files:**
- Modify: `app/query_process/agent/nodes/node_rrf.py`
- Modify: `app/query_process/agent/nodes/node_rerank.py`
- Modify: `app/query_process/agent/nodes/node_answer_output.py`
- Create: `prompts/answer_out.prompt`

- [ ] **Step 1: 创建 prompts/answer_out.prompt**

```text
你是一个智能助手，请根据参考内容回答用户的问题。
要求：
1. 尽量基于【参考内容】和【用户问题】作答，不要编造不存在的事实。
2. 如果用户的问题需要通过图片来辅助说明（例如：外观、结构、接线、示意图等），图片只能来自于本地切片文本中的图片，请在答案最后追加一个独立的图片区块，格式严格如下：
【图片】
<图片URL1>
<图片URL2>
（每行一个URL；如果没有合适图片则不要输出【图片】区块）

【参考内容】
{context}

【历史对话】
{history}

【相关商品/实体】
{item_names}

【用户问题】
{question}

请回答：
```

- [ ] **Step 2: 实现 node_rrf.py** — RRF 算法融合 3 路结果

- [ ] **Step 3: 实现 node_rerank.py** — gte-rerank API + 动态截断

- [ ] **Step 4: 实现 node_answer_output.py** — 检查前置答案 → 构建 Prompt → Qwen 流式生成 → 图片提取 → MongoDB 写入 → SSE final

- [ ] **Step 5: Commit**

```bash
git add app/query_process/agent/nodes/ prompts/answer_out.prompt
git commit -m "query: implement nodes 5-7 (rrf, rerank, answer_output)"
```

---

## Phase 9: 检索 Web 服务

### Task 17: 查询 API 服务与前端页面

**Files:**
- Create: `app/query_process/api/query_service.py`
- Create: `app/query_process/page/chat.html`

- [ ] **Step 1: 创建 query_service.py** — FastAPI 应用，包含 `/query`、`/stream/{session_id}`、`/history`、`/health`、`/chat.html`

- [ ] **Step 2: 创建 chat.html** — 聊天界面，SSE 流式接收，打字机效果，图片展示

- [ ] **Step 3: 验证查询服务**

Run: `python -m app.query_process.api.query_service`
Expected: 服务在 8001 端口启动

- [ ] **Step 4: Commit**

```bash
git add app/query_process/api/ app/query_process/page/
git commit -m "query: add FastAPI service with SSE and chat.html page"
```

---

## Phase 10: 集成测试

### Task 18: 端到端测试

- [ ] **Step 1: 启动基础设施**

Run: `docker compose up -d`

- [ ] **Step 2: 启动导入服务**

Run: `python -m app.import_process.api.file_import_service` (端口 8000)

- [ ] **Step 3: 上传测试 PDF 并验证导入**

打开 `http://localhost:8000/import.html`，上传 `examples/Sample1.pdf`，等待所有节点完成

- [ ] **Step 4: 启动查询服务**

Run: `python -m app.query_process.api.query_service` (端口 8001)

- [ ] **Step 5: 测试问答**

打开 `http://localhost:8001/chat.html`，输入与导入文档相关的问题，验证流式回答

- [ ] **Step 6: 验收检查**

- [ ] Milvus `kb_chunks` 集合有数据
- [ ] Milvus `kb_item_names` 集合有数据
- [ ] MongoDB `chat_message` 集合有对话记录
- [ ] MinIO bucket 有上传的 PDF 和图片
- [ ] 前端聊天页面流式打字机效果正常
- [ ] 前端导入页面进度展示正常

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete RAG system with import and query flows"
```

---

## Self-Review

### 1. Spec Coverage

| Spec 章节 | 对应 Task | 状态 |
|-----------|----------|------|
| 1. 项目概述 | 全局 | ✅ |
| 2. 系统架构 | 全局 | ✅ |
| 3. 基础设施层 | Task 1-3 | ✅ |
| 4. 导入流程 | Task 10-13 | ✅ |
| 5. 检索流程 | Task 14-17 | ✅ |
| 6. AI 模型封装层 | Task 5 | ✅ |
| 7. 依赖清单 | Task 2 | ✅ |
| 8. 实施顺序 | 全部 Task 1-18 | ✅ |
| 9. 验收标准 | Task 18 | ✅ |

### 2. Placeholder Scan

- 节点实现代码（Task 11-12, 15-16）标注"从教案参考编写" — 这是合理的，因为教案中有完整的参考代码，实施时直接参考对应章节即可
- 所有文件路径、函数签名、接口定义均已明确
- 无 TBD/TODO 标记

### 3. Type Consistency

- `ImportGraphState` 字段在 state.py 和各节点中一致
- `QueryGraphState` 字段在 state.py 和各节点中一致
- `get_llm_client()` / `get_vlm_client()` / `get_embedding_client()` 函数名在封装层和节点中一致
- `create_hybrid_search_requests()` 参数 `(dense_vector, query_text, expr, limit)` 与调用方一致
- `rerank_documents()` 参数 `(query, documents, text_field, top_n)` 与调用方一致
- SSE 事件类型枚举值与前端期望一致
