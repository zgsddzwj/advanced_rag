# 掌柜智库 RAG 系统 — 设计规格文档

> **版本**: 1.0  
> **日期**: 2026-06-28  
> **状态**: 待审核  
> **基础**: 基于掌柜智库教案，从零构建高级 RAG 系统

---

## 1. 项目概述

### 1.1 目标

将现有 Flask PDF 解析项目重构为基于 LangGraph 的高级 RAG 系统，实现文档导入和智能问答两条完整流程。

### 1.2 技术栈总览

| 层级 | 技术 | 说明 |
|------|------|------|
| 工作流编排 | LangGraph | 导入图（7 节点）+ 检索图（7 节点 + 2 虚拟节点） |
| Web 框架 | FastAPI + Uvicorn | 导入服务(:8000) + 查询服务(:8001) |
| 向量数据库 | Milvus 2.4 | Dense (HNSW+COSINE) + BM25 (SPARSE_INVERTED_INDEX) |
| 对象存储 | MinIO | PDF/图片持久化 |
| 对话历史 | MongoDB 7.0 | 多轮对话上下文 |
| 基础设施 | Docker Compose | 统一编排 Milvus/etcd/MinIO/MongoDB |

### 1.3 AI 模型栈（全部通过阿里云百炼 API）

| 组件 | 模型 | 用途 |
|------|------|------|
| LLM | Qwen-Plus | 意图改写、主体识别、HyDE 生成、答案生成 |
| VLM | Qwen-VL-Plus | 图片语义理解 |
| Embedding | text-embedding-v3 (1024维) | 稠密向量化 |
| Rerank | gte-rerank | 精准重排序 |
| 网络搜索 | 百炼 MCP | 互联网实时信息检索 |

### 1.4 与教案的关键适配

| 组件 | 教案方案 | 本项目方案 | 适配原因 |
|------|---------|-----------|---------|
| Dense Embedding | 本地 BGE-M3 (1024维) | text-embedding-v3 API (1024维) | 不跑本地模型 |
| Sparse Embedding | 本地 BGE-M3 Sparse | Milvus BM25 原生全文检索 | API 不提供稀疏向量 |
| Rerank | 本地 BGE-Reranker | gte-rerank API | 不跑本地模型 |
| LLM | 本地 vLLM/Qwen | Qwen-Plus via 百炼 API | 统一 API |
| VLM | 本地 VLM | Qwen-VL-Plus via 百炼 API | 统一 API |
| 知识图谱检索 | Neo4j KG (node_query_kg) | 省略，3 路召回 | 教案 02 章为 3 路设计 |

---

## 2. 系统架构

### 2.1 全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Web 服务层                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ 导入服务 :8000    │  │ 查询服务 :8001    │  │ SSE 流式推送   │  │
│  │ /upload /status  │  │ /query /stream   │  │ /history      │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────────┘  │
└───────────┼──────────────────────┼──────────────────────────────┘
            │                      │
    ┌───────▼────────┐    ┌───────▼────────┐
    │  导入 LangGraph │    │  检索 LangGraph │
    │  (7 个节点)     │    │  (7+2 个节点)   │
    └───────┬────────┘    └───────┬────────┘
            │                      │
┌───────────┼──────────────────────┼──────────────────────────────┐
│           ▼          基础设施层    ▼                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Milvus     │  │    MinIO     │  │   MongoDB    │           │
│  │ 向量+BM25检索 │  │  图片/PDF存储 │  │  对话历史存储  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
            │                      │
┌───────────┼──────────────────────┼──────────────────────────────┐
│           ▼    阿里云百炼 API 层   ▼                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ Qwen-Plus│ │Qwen-VL   │ │text-     │ │gte-      │ │Bailian ││
│  │  (LLM)   │ │-Plus(VLM)│ │embedding │ │rerank    │ │MCP搜索 ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 项目目录结构

```
advanced_rag/
├── .env                          # 环境变量
├── .env.example                  # 环境变量模板
├── pyproject.toml                # 项目依赖（uv管理）
├── docker-compose.yml            # 基础设施编排
│
├── app/
│   ├── core/                     # 核心工具
│   │   ├── logger.py             # loguru 日志
│   │   └── load_prompt.py        # Prompt 模板加载器
│   │
│   ├── conf/                     # 配置模块
│   │   ├── lm_config.py          # LLM/VLM 配置
│   │   ├── embedding_config.py   # Embedding 配置
│   │   ├── milvus_config.py      # Milvus 配置
│   │   └── bailian_mcp_config.py # 百炼 MCP 配置
│   │
│   ├── clients/                  # 外部服务客户端
│   │   ├── milvus_utils.py       # Milvus 连接 + 混合搜索
│   │   ├── minio_utils.py        # MinIO 连接 + 文件操作
│   │   └── mongo_history_utils.py# MongoDB 对话历史
│   │
│   ├── lm/                       # AI 模型封装
│   │   ├── lm_utils.py           # LLM 客户端（Qwen-Plus）
│   │   ├── vlm_utils.py          # VLM 客户端（Qwen-VL-Plus）
│   │   ├── embedding_utils.py    # Embedding 客户端（text-embedding-v3）
│   │   ├── rerank_utils.py       # Rerank 客户端（gte-rerank）
│   │   └── web_search_utils.py   # 网络搜索客户端（百炼 MCP）
│   │
│   ├── utils/                    # 通用工具
│   │   ├── task_utils.py         # 任务状态管理（内存字典）
│   │   ├── sse_utils.py          # SSE 事件队列管理
│   │   ├── path_util.py          # 项目路径工具
│   │   └── escape_milvus_string_utils.py  # Milvus 字符串转义
│   │
│   ├── import_process/           # === 导入流程 ===
│   │   ├── agent/
│   │   │   ├── state.py          # ImportGraphState 状态定义
│   │   │   ├── main_graph.py     # LangGraph 导入图编排
│   │   │   └── nodes/
│   │   │       ├── node_entry.py              # 1.入口路由
│   │   │       ├── node_pdf_to_md.py          # 2.PDF转Markdown (MinerU)
│   │   │       ├── node_md_img.py             # 3.图片处理 (MinIO+VLM)
│   │   │       ├── node_document_split.py     # 4.文档切分
│   │   │       ├── node_item_name_recognition.py # 5.主体识别 (LLM)
│   │   │       ├── node_bge_embedding.py      # 6.向量化 (API)
│   │   │       └── node_import_milvus.py      # 7.Milvus入库
│   │   ├── api/
│   │   │   └── file_import_service.py  # FastAPI 导入服务
│   │   └── page/
│   │       └── import.html             # 导入前端页面
│   │
│   └── query_process/            # === 检索流程 ===
│       ├── agent/
│       │   ├── state.py          # QueryGraphState 状态定义
│       │   ├── main_graph.py     # LangGraph 检索图编排
│       │   └── nodes/
│       │       ├── node_item_name_confirm.py    # 1.意图确认 (LLM)
│       │       ├── node_search_embedding.py     # 2.向量检索 (Milvus混合)
│       │       ├── node_search_embedding_hyde.py # 3.HyDE检索 (LLM+Milvus)
│       │       ├── node_web_search_mcp.py       # 4.网络搜索 (百炼MCP)
│       │       ├── node_rrf.py                  # 5.RRF融合排序
│       │       ├── node_rerank.py               # 6.重排序 (gte-rerank API)
│       │       └── node_answer_output.py        # 7.答案生成 (Qwen+SSE)
│       ├── api/
│       │   └── query_service.py  # FastAPI 查询服务
│       └── page/
│           └── chat.html         # 聊天前端页面
│
├── prompts/                      # Prompt 模板目录
│   ├── item_name_recognition.prompt
│   ├── item_name_confirm.prompt
│   ├── hyde_generate.prompt
│   └── answer_out.prompt
│
├── test/                         # 测试脚本
│   ├── 01_env_test.py
│   ├── 02_import_graph_flow.py
│   └── 03_query_graph_flow.py
│
├── doc/                          # 测试文档
├── logs/                         # 日志输出
├── output/                       # 文件处理临时输出
└── uploads/                      # 上传文件临时存储
```

### 2.3 开发策略

遵循教案的 **Top-Down（自顶向下）** 模式：
1. **搭建节点骨架** — 所有节点先写空函数（仅日志），确保图能跑通
2. **串联主图** — 注册节点 + 条件路由 + 静态边
3. **验证流程** — 运行测试脚本，确认节点执行顺序正确
4. **填充逻辑** — 逐个节点实现核心业务逻辑

---

## 3. 基础设施层设计

### 3.1 Docker Compose 编排

一份 `docker-compose.yml` 统一编排 Milvus + etcd + MinIO + MongoDB：

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

### 3.2 端口分配表

| 服务 | 宿主端口 | 用途 |
|------|---------|------|
| Milvus | 19530 | 向量数据库 gRPC |
| Milvus | 9091 | 健康检查 / metrics |
| MinIO | 9000 | S3 API |
| MinIO | 9001 | Web 管理控制台 |
| etcd | 2379 | Milvus 元数据 |
| MongoDB | 27017 | 对话历史 |
| 导入服务 | 8000 | 文件上传 + 状态查询 |
| 查询服务 | 8001 | 查询 + SSE 流式 |

### 3.3 环境变量配置 (`.env`)

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
RERANK_BASE_URL=https://dashscope.aliyuncs.com/api/v1

# 百炼 MCP 网络搜索
BAILIAN_MCP_APP_ID=your_app_id
BAILIAN_MCP_API_KEY=your_mcp_key

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

### 3.4 Milvus 集合 Schema

#### 集合 1：`kb_chunks`（切片级索引）

| 字段名 | 数据类型 | 说明 |
|--------|---------|------|
| `chunk_id` | Int64 (PK, auto_id) | 自增主键 |
| `content` | VARCHAR(65535), enable_analyzer=True | 切片文本内容（启用中文分词） |
| `title` | VARCHAR(65535) | 完整标题路径 |
| `parent_title` | VARCHAR(65535) | 父标题 |
| `part` | INT8 | 分片编号 |
| `file_title` | VARCHAR(65535) | 源文件名 |
| `item_name` | VARCHAR(65535) | 商品/主体名称 |
| `dense_vector` | FLOAT_VECTOR(1024) | 稠密向量（百炼 API） |
| `sparse_vector` | SPARSE_FLOAT_VECTOR | 稀疏向量（Milvus BM25 自动生成） |

索引设计：
- `dense_vector`: HNSW + COSINE（M=16, efConstruction=200）
- `sparse_vector`: SPARSE_INVERTED_INDEX + BM25

BM25 Function 定义：
```python
schema.add_field("content", DataType.VARCHAR, max_length=65535,
                 enable_analyzer=True, analyzer_params={"type": "chinese"})
schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
function = Function(
    name="content_bm25",
    function_type=FunctionType.BM25,
    input_field_names=["content"],
    output_field_names=["sparse_vector"],
)
schema.add_function(function)
```

#### 集合 2：`kb_item_names`（文档级索引）

| 字段名 | 数据类型 | 说明 |
|--------|---------|------|
| `id` | Int64 (PK, auto_id) | 自增主键 |
| `file_title` | VARCHAR(65535) | 源文件名 |
| `item_name` | VARCHAR(65535) | 商品/主体名称 |
| `dense_vector` | FLOAT_VECTOR(1024) | 商品名稠密向量 |

索引：`dense_vector` HNSW + COSINE

用途：意图确认节点根据用户输入的商品名在此集合中做向量检索，对齐标准型号。

### 3.5 MongoDB 数据结构

集合 `chat_message`：

```json
{
    "session_id": "uuid-string",
    "role": "user | assistant",
    "text": "对话内容",
    "rewritten_query": "改写后的问题",
    "item_names": ["商品A", "商品B"],
    "image_urls": ["http://..."],
    "ts": 1730000000.0
}
```

索引：`(session_id ASC, ts DESC)`

---

## 4. 导入流程 LangGraph 设计

### 4.1 状态定义 (`ImportGraphState`)

```python
class ImportGraphState(TypedDict):
    # --- 流程控制 ---
    task_id: str
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool

    # --- 路径相关 ---
    local_dir: str
    local_file_path: str
    file_title: str
    pdf_path: str
    md_path: str
    split_path: str

    # --- 内容数据 ---
    md_content: str
    chunks: list
    item_name: str

    # --- 向量数据 ---
    embeddings_content: list
```

### 4.2 图流程

```
START → node_entry ──┬─ PDF ──→ node_pdf_to_md ──→ node_md_img
                     ├─ MD  ─────────────────────→ node_md_img
                     └─ 其他 ──────────────────────────→ END
                                                                ↓
                          node_document_split ←──────────────────┘
                                ↓
                    node_item_name_recognition
                                ↓
                      node_bge_embedding
                                ↓
                     node_import_milvus
                                ↓
                              END
```

条件路由（`route_after_entry`）：
- `.pdf` → `is_pdf_read_enabled=True` → `node_pdf_to_md`
- `.md` → `is_md_read_enabled=True` → `node_md_img`（跳过 PDF 转换）
- 其他 → END

### 4.3 节点设计

#### 节点 1：`node_entry`（入口路由）

- **输入**: `local_file_path`
- **输出**: `is_pdf_read_enabled` / `is_md_read_enabled` / `file_title`
- **逻辑**: 判断文件后缀设置路由标记；提取文件名（去后缀）作为 `file_title`

#### 节点 2：`node_pdf_to_md`（PDF 结构化解析）

- **输入**: `local_file_path` / `local_dir`
- **输出**: `md_content` / `md_path`
- **逻辑**: 调用 MinerU (magic-pdf) 解析 PDF → 输出保留多级标题和表格结构的 Markdown
- **适配**: MinerU 是本地工具（非 AI 模型），无需 API 替换

#### 节点 3：`node_md_img`（多模态图片处理）

- **输入**: `md_content`
- **输出**: `md_content`（更新后的，图片链接替换为 MinIO URL + VLM 描述）
- **逻辑**: ① 扫描 Markdown 中 `![](本地路径)` 图片 → ② 上传至 MinIO → ③ 调用 Qwen-VL-Plus API 生成语义描述 → ④ 替换为 `![VLM描述](MinIO URL)`
- **适配**: VLM 从本地改为 Qwen-VL-Plus API（百炼）

#### 节点 4：`node_document_split`（智能文档切分）

- **输入**: `md_content` / `file_title`
- **输出**: `chunks`（列表，每个元素含 `content` / `title` / `parent_title` / `part` / `file_title`）
- **逻辑**: 基于 Markdown 标题层级递归切分 → 超长段落二次切分 → 每个 Chunk 前拼接标题路径

#### 节点 5：`node_item_name_recognition`（主体识别）

- **输入**: `chunks`（取前几段内容）
- **输出**: `item_name`
- **逻辑**: 提取文档头部内容 → 调用 Qwen-Plus API 识别主体对象 → 将 `item_name` 附加到所有 chunks
- **适配**: LLM 改为 Qwen-Plus API（百炼）

#### 节点 6：`node_bge_embedding`（向量化）

- **输入**: `chunks`（含 `item_name` + `content`）
- **输出**: `chunks`（每个元素新增 `dense_vector` 字段）
- **逻辑**: ① 拼接 `商品：{item_name}，介绍：{content}` → ② 调用 text-embedding-v3 API 批量生成稠密向量（1024维） → ③ 绑定到每个 chunk
- **关键适配**: 仅生成 dense 向量（百炼 API），sparse 由 Milvus BM25 在入库时自动处理
- **批处理**: batch_size=10

#### 节点 7：`node_import_milvus`（Milvus 入库）

- **输入**: `chunks`（含 `dense_vector`）
- **输出**: `chunks`（回填 `chunk_id`）
- **逻辑**: ① 校验数据 → ② 集合不存在则自动创建 Schema + 索引 + BM25 Function → ③ 按 `item_name` 删除旧数据（幂等性）→ ④ 批量插入 `kb_chunks` → ⑤ 回填自增主键 `chunk_id` → ⑥ 将 `item_name` 向量化后写入 `kb_item_names` 集合（供检索流程的商品名对齐使用）
- **关键适配**: Schema 中 `content` 启用 `enable_analyzer=True`，定义 BM25 Function，Milvus 自动从 `content` 生成 `sparse_vector`
- **双集合写入**: 同时写入 `kb_chunks`（切片级）和 `kb_item_names`（文档级，存储 `item_name` + 其稠密向量）

### 4.4 图编译代码

```python
workflow = StateGraph(ImportGraphState)

workflow.add_node("node_entry", node_entry)
workflow.add_node("node_pdf_to_md", node_pdf_to_md)
workflow.add_node("node_md_img", node_md_img)
workflow.add_node("node_document_split", node_document_split)
workflow.add_node("node_item_name_recognition", node_item_name_recognition)
workflow.add_node("node_bge_embedding", node_bge_embedding)
workflow.add_node("node_import_milvus", node_import_milvus)

workflow.set_entry_point("node_entry")

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

### 4.5 导入 Web 服务接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/import.html` | GET | 返回导入前端页面 |
| `/upload` | POST | 接收文件 → 本地保存 → MinIO 上传 → 启动后台 LangGraph 任务 |
| `/status/{task_id}` | GET | 查询任务进度（pending/processing/completed/failed + 已完成节点列表） |

流程：上传文件 → 返回 `task_id` → 前端轮询 `/status/{task_id}` → 展示各节点执行进度。

---

## 5. 检索流程 LangGraph 设计

### 5.1 状态定义 (`QueryGraphState`)

```python
class QueryGraphState(TypedDict):
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

### 5.2 图流程

```
START → node_item_name_confirm ──┬─ 有answer(反问/拒绝) ──→ node_answer_output → END
                                 │
                                 └─ 正常检索 ──→ node_multi_search
                                                    ├─→ node_search_embedding ──────┐
                                                    ├─→ node_search_embedding_hyde ─┤
                                                    └─→ node_web_search_mcp ────────┤
                                                                                      ↓
                                                                                 node_join
                                                                                      ↓
                                                                                  node_rrf
                                                                                      ↓
                                                                                 node_rerank
                                                                                      ↓
                                                                              node_answer_output
                                                                                      ↓
                                                                                     END
```

- `node_multi_search` 和 `node_join` 是虚拟节点（`lambda x: {}`），作为并行分叉点和合并点
- 3 路并行召回：向量检索、HyDE 检索、网络搜索
- KG 检索已省略（教案 02 章为 3 路设计）

条件路由（`route_after_item_confirm`）：
```python
def route_after_item_confirm(state):
    if state.get("answer"):
        return "node_answer_output"   # 反问/拒绝，跳过检索
    return "node_multi_search"         # 正常进入多路召回
```

### 5.3 节点设计

#### 节点 1：`node_item_name_confirm`（意图确认与改写）

- **输入**: `original_query` / `history`（从 MongoDB 加载最近对话）
- **输出**: `item_names` / `rewritten_query` / `answer`（可能为空）
- **逻辑**:
  1. 调用 Qwen-Plus，结合历史对话提取商品名，将模糊问题改写为完整精准问题
  2. 将商品名向量化（text-embedding-v3），在 Milvus `kb_item_names` 集合中做稠密检索
  3. 标准化对齐：评分高且唯一→确认；多个候选→反问；无匹配→拒绝
  4. 将用户问题、改写后的问题、确认的商品名写入 MongoDB

#### 节点 2：`node_search_embedding`（向量混合检索）

- **输入**: `rewritten_query` / `item_names`
- **输出**: `embedding_chunks`（Top 5）
- **逻辑**: ① 调用 text-embedding-v3 API 向量化 → ② 构造 `item_name in [...]` 过滤 → ③ 执行 Milvus 混合检索（Dense + BM25）→ ④ 返回 Top 5
- **关键适配**: 传入 dense_vector + 查询文本，BM25 由 Milvus 自动分词生成稀疏向量

混合搜索请求构造：
```python
dense_req = AnnSearchRequest(
    data=[dense_vector],
    anns_field="dense_vector",
    param={"metric_type": "COSINE"},
    expr=expr,
    limit=10
)
sparse_req = AnnSearchRequest(
    data=[query_text],            # 查询文本，Milvus BM25 自动分词
    anns_field="sparse_vector",
    param={"metric_type": "BM25"},
    expr=expr,
    limit=10
)
hybrid_search(reqs=[dense_req, sparse_req],
              ranker_weights=(0.8, 0.2),
              limit=5)
```

#### 节点 3：`node_search_embedding_hyde`（HyDE 假设检索）

- **输入**: `rewritten_query` / `item_names`
- **输出**: `hyde_embedding_chunks`（Top 5）
- **逻辑**: ① 调用 Qwen-Plus 生成假设性答案 → ② 对假设答案调用 text-embedding-v3 生成稠密向量 → ③ 执行 Milvus 混合检索（Dense + BM25）→ ④ 返回 Top 5

#### 节点 4：`node_web_search_mcp`（网络搜索）

- **输入**: `rewritten_query`
- **输出**: `web_search_docs`（含标题、链接、摘要的文档列表）
- **逻辑**: 调用百炼 MCP 联网搜索接口 → 获取实时互联网信息

#### 节点 5：`node_rrf`（倒排秩融合）

- **输入**: `embedding_chunks` / `hyde_embedding_chunks` / `web_search_docs`
- **输出**: `rrf_chunks`（融合排序后的 Top 10）
- **逻辑**: RRF 公式 `score = Σ 1/(k + rank)`，k=60 → 去重合并 → 按总分降序取 Top 10
- **无适配**: 纯算法实现

#### 节点 6：`node_rerank`（精准重排序）

- **输入**: `rrf_chunks`（Top 10）
- **输出**: `reranked_docs`（Top K，动态截断）
- **逻辑**: ① 合并候选池 → ② 调用 gte-rerank API 计算"问题-文档"对相关性得分 → ③ 按得分降序 → ④ 检测断崖式下跌截取 Top K（最多 10 条）
- **适配**: 教案用本地 BGE-Reranker，本项目改为 gte-rerank API（百炼）

gte-rerank API 调用：
```python
import dashscope
result = dashscope.TextReRank.call(
    model="gte-rerank",
    query=rewritten_query,
    documents=[doc["content"] for doc in rrf_chunks],
    top_n=10,
    return_documents=False
)
```

动态截断逻辑：
```python
DROP_THRESHOLD = 0.15
for i in range(1, len(scored_docs)):
    drop = scored_docs[i-1]["score"] - scored_docs[i]["score"]
    if drop > DROP_THRESHOLD:
        return {"reranked_docs": scored_docs[:i]}
return {"reranked_docs": scored_docs}
```

#### 节点 7：`node_answer_output`（答案生成与流式输出）

- **输入**: `reranked_docs` / `rewritten_query` / `history` / `item_names` / `answer`（可能已有）
- **输出**: `answer` / `prompt`
- **逻辑**:
  1. 检查前置答案：若已存在（反问/拒绝），直接流式推送，跳过 LLM 生成
  2. 构建 Prompt：从 `reranked_docs` 提取文本 + 元数据头，总长度不超过 12000 字符；格式化历史对话；加载 `prompts/answer_out.prompt` 模板
  3. LLM 生成与流式推送：流式模式调用 Qwen-Plus `stream()` 逐字 SSE 推送；非流式模式 `invoke()` 直接返回
  4. 图片提取：从 `reranked_docs` 正则提取 Markdown 图片链接 + 检查 `url` 字段，去重
  5. 写入 MongoDB + Final 推送：答案存入历史 → 发送 SSE `final` 事件（含完整答案 + 图片 URL 列表）
- **适配**: LLM 改为 Qwen-Plus API（百炼）

### 5.4 图编译代码

```python
builder = StateGraph(QueryGraphState)

builder.add_node("node_item_name_confirm", node_item_name_confirm)
builder.add_node("node_multi_search", lambda x: {})
builder.add_node("node_search_embedding", node_search_embedding)
builder.add_node("node_search_embedding_hyde", node_search_embedding_hyde)
builder.add_node("node_web_search_mcp", node_web_search_mcp)
builder.add_node("node_join", lambda x: {})
builder.add_node("node_rrf", node_rrf)
builder.add_node("node_rerank", node_rerank)
builder.add_node("node_answer_output", node_answer_output)

builder.set_entry_point("node_item_name_confirm")
builder.add_conditional_edges("node_item_name_confirm", route_after_item_confirm)

builder.add_edge("node_multi_search", "node_search_embedding")
builder.add_edge("node_multi_search", "node_search_embedding_hyde")
builder.add_edge("node_multi_search", "node_web_search_mcp")

builder.add_edge("node_search_embedding", "node_join")
builder.add_edge("node_search_embedding_hyde", "node_join")
builder.add_edge("node_web_search_mcp", "node_join")

builder.add_edge("node_join", "node_rrf")
builder.add_edge("node_rrf", "node_rerank")
builder.add_edge("node_rerank", "node_answer_output")
builder.add_edge("node_answer_output", END)

query_app = builder.compile()
```

### 5.5 检索 Web 服务接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/chat.html` | GET | 返回聊天前端页面 |
| `/query` | POST | 接收查询 → 启动后台 LangGraph 任务 → 返回 `session_id` |
| `/stream/{session_id}` | GET | 建立 SSE 长连接，实时推送 |
| `/history/{session_id}` | GET | 获取会话历史记录 |
| `/history/{session_id}` | DELETE | 清空会话历史 |
| `/health` | GET | 健康检查 |

### 5.6 SSE 事件类型

| 事件 | 数据 | 触发时机 |
|------|------|---------|
| `ready` | `{"session_id": "xxx"}` | SSE 连接建立 |
| `progress` | `{"done_list": [...], "running_list": [...]}` | 每个节点开始/完成 |
| `delta` | `{"delta": "增量文本"}` | LLM 逐字生成 |
| `final` | `{"answer": "完整答案", "image_urls": [...]}` | 答案生成完毕 |
| `error` | `{"error": "错误详情"}` | 流程异常 |

### 5.7 前后端交互时序

```
前端                      后端                      LangGraph
  │                         │                         │
  │── POST /query ─────────→│                         │
  │← session_id ────────────│                         │
  │                         │── 启动后台任务 ────────→│
  │── GET /stream/{id} ────→│                         │
  │← event: ready ──────────│                         │
  │← event: progress ───────│← 节点状态更新 ──────────│
  │← event: progress ───────│← 节点状态更新 ──────────│
  │← event: delta ──────────│← LLM 流式生成 ──────────│
  │← event: delta ──────────│← LLM 流式生成 ──────────│
  │← event: final ──────────│← 答案+图片 ─────────────│
  │   (关闭连接)             │                         │
```

---

## 6. AI 模型封装层设计

### 6.1 封装层总览

```
app/lm/
├── lm_utils.py           # LLM（Qwen-Plus）— langchain_openai.ChatOpenAI
├── vlm_utils.py          # VLM（Qwen-VL-Plus）— langchain_openai.ChatOpenAI 多模态
├── embedding_utils.py    # Embedding（text-embedding-v3）— langchain_openai.OpenAIEmbeddings
├── rerank_utils.py       # Rerank（gte-rerank）— dashscope.TextReRank
└── web_search_utils.py   # 网络搜索（百炼 MCP）— dashscope.Application
```

### 6.2 LLM 客户端 (`lm_utils.py`)

- **模型**: Qwen-Plus via 百炼 OpenAI 兼容接口
- **封装**: `langchain_openai.ChatOpenAI`，单例模式
- **参数**: temperature=0.3, streaming=True
- **接口**: `get_llm_client()` 返回单例
- **使用**: `llm.stream(prompt)` 流式 / `llm.invoke(prompt)` 非流式
- **调用节点**: `node_item_name_confirm`、`node_search_embedding_hyde`、`node_answer_output`

### 6.3 VLM 客户端 (`vlm_utils.py`)

- **模型**: Qwen-VL-Plus via 百炼
- **封装**: `langchain_openai.ChatOpenAI` 多模态消息
- **接口**: `get_vlm_client()` + `describe_image(image_path)`
- **调用节点**: `node_md_img`（图片语义描述）

### 6.4 Embedding 客户端 (`embedding_utils.py`)

- **模型**: text-embedding-v3 (1024维) via 百炼
- **封装**: `langchain_openai.OpenAIEmbeddings`，单例模式
- **接口**: `generate_embeddings(texts)` 批量 / `generate_embedding(text)` 单条
- **返回**: 仅 dense 向量列表（sparse 交给 Milvus BM25）
- **调用节点**: `node_bge_embedding`、`node_search_embedding`、`node_search_embedding_hyde`、`node_item_name_confirm`

关键区别：
```python
# 教案 BGE-M3: {"dense": [...], "sparse": [...]}
# 本项目 API: [[0.01, 0.02, ...]]  # 仅 dense
```

### 6.5 Rerank 客户端 (`rerank_utils.py`)

- **模型**: gte-rerank via 百炼
- **封装**: `dashscope.TextReRank.call()`
- **接口**: `rerank_documents(query, documents, top_n=10)` 返回带 score 的排序列表
- **调用节点**: `node_rerank`

### 6.6 网络搜索客户端 (`web_search_utils.py`)

- **模型**: 百炼 MCP
- **封装**: `dashscope.Application.call()`
- **接口**: `web_search(query, count=5)` 返回 `[{title, url, content, source}]`
- **调用节点**: `node_web_search_mcp`

### 6.7 统一配置 (`lm_config.py`)

所有 API 共享 `DASHSCOPE_API_KEY`。配置分文件管理：`app/conf/lm_config.py` 管理 LLM/VLM/Embedding/Rerank 的模型名和 Base URL；`app/conf/milvus_config.py` 管理 Milvus 集合名和连接地址；`app/conf/bailian_mcp_config.py` 管理百炼 MCP 的 App ID。

### 6.8 各节点与 API 调用关系

```
导入流程:
  node_md_img                → VLM (Qwen-VL-Plus)     图片语义描述
  node_item_name_recognition → LLM (Qwen-Plus)        主体识别
  node_bge_embedding         → Embedding (v3)         稠密向量化
  node_import_milvus         → Milvus BM25 自动        稀疏向量(自动)

检索流程:
  node_item_name_confirm     → LLM + Embedding + Milvus  意图改写+商品名对齐
  node_search_embedding      → Embedding + Milvus        Dense+BM25混合检索
  node_search_embedding_hyde → LLM + Embedding + Milvus  HyDE+混合检索
  node_web_search_mcp        → 百炼 MCP                  网络搜索
  node_rrf                   → (纯算法)                  无 API
  node_rerank                → Rerank (gte-rerank)       精准重排序
  node_answer_output         → LLM (Qwen-Plus)           答案生成(流式)
```

---

## 7. 依赖清单

### 7.1 Python 依赖 (`pyproject.toml`)

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

### 7.2 与教案依赖差异

| 教案依赖 | 本项目 | 原因 |
|---------|--------|------|
| `torch` | 移除 | 不跑本地模型 |
| `FlagEmbedding` | 移除 | Embedding 改用 API |
| `pymilvus-model` | 移除 | 不使用 BGE-M3 EmbeddingFunction |
| `modelscope` | 移除 | 不需要本地下载模型 |
| — | 新增 `dashscope` | 百炼 API SDK（rerank/mcp） |

---

## 8. 实施顺序

### 阶段 1：基础设施搭建
1. 编写 `docker-compose.yml`，启动 Milvus/MinIO/MongoDB
2. 初始化项目结构，创建 `pyproject.toml`，安装依赖
3. 配置 `.env` / `.env.example`
4. 实现 `app/core/logger.py`（日志）
5. 实现 `app/utils/path_util.py`（路径工具）

### 阶段 2：AI 模型封装层
6. 实现 `app/conf/lm_config.py`（统一配置）
7. 实现 `app/lm/lm_utils.py`（LLM 客户端）
8. 实现 `app/lm/vlm_utils.py`（VLM 客户端）
9. 实现 `app/lm/embedding_utils.py`（Embedding 客户端）
10. 实现 `app/lm/rerank_utils.py`（Rerank 客户端）
11. 实现 `app/lm/web_search_utils.py`（网络搜索客户端）

### 阶段 3：基础设施客户端
12. 实现 `app/clients/milvus_utils.py`（Milvus 连接 + 混合搜索）
13. 实现 `app/clients/minio_utils.py`（MinIO 连接 + 文件操作）
14. 实现 `app/clients/mongo_history_utils.py`（MongoDB 对话历史）
15. 实现 `app/utils/task_utils.py`（任务状态管理）
16. 实现 `app/utils/sse_utils.py`（SSE 事件队列）
17. 实现 `app/utils/escape_milvus_string_utils.py`（字符串转义）
18. 实现 `app/core/load_prompt.py`（Prompt 加载器）

### 阶段 4：导入流程 — 骨架
19. 实现 `app/import_process/agent/state.py`（状态定义）
20. 创建 7 个节点骨架文件（仅日志）
21. 实现 `app/import_process/agent/main_graph.py`（图编排）
22. 编写图流程测试脚本，验证骨架跑通

### 阶段 5：导入流程 — 填充逻辑
23. 实现 `node_entry.py`
24. 实现 `node_pdf_to_md.py`（MinerU 集成）
25. 实现 `node_md_img.py`（MinIO + VLM）
26. 实现 `node_document_split.py`
27. 实现 `node_item_name_recognition.py`（LLM）
28. 实现 `node_bge_embedding.py`（API 向量化）
29. 实现 `node_import_milvus.py`（BM25 Schema + 入库）

### 阶段 6：导入 Web 服务
30. 实现 `app/import_process/api/file_import_service.py`
31. 实现 `app/import_process/page/import.html`
32. 端到端测试导入流程

### 阶段 7：检索流程 — 骨架
33. 实现 `app/query_process/agent/state.py`（状态定义）
34. 创建 7 个节点骨架文件 + 2 虚拟节点
35. 实现 `app/query_process/agent/main_graph.py`（图编排）
36. 编写图流程测试脚本，验证骨架跑通

### 阶段 8：检索流程 — 填充逻辑
37. 实现 `node_item_name_confirm.py`（LLM + 向量对齐）
38. 实现 `node_search_embedding.py`（Milvus 混合检索）
39. 实现 `node_search_embedding_hyde.py`（HyDE + 混合检索）
40. 实现 `node_web_search_mcp.py`（百炼 MCP）
41. 实现 `node_rrf.py`（RRF 算法）
42. 实现 `node_rerank.py`（gte-rerank API）
43. 实现 `node_answer_output.py`（Qwen 流式 + SSE）

### 阶段 9：检索 Web 服务
44. 实现 `app/query_process/api/query_service.py`
45. 实现 `app/query_process/page/chat.html`
46. 端到端测试检索流程

### 阶段 10：集成测试
47. 完整流程测试：导入 PDF → 查询问答 → 验证结果
48. 编写 README 和部署说明

---

## 9. 验收标准

1. **基础设施**: `docker-compose up` 一键启动所有服务，端口正常监听
2. **导入流程**: 上传 PDF → MinerU 解析 → 图片 VLM 描述 → 切分 → 向量化 → Milvus 入库（含 BM25）
3. **检索流程**: 用户提问 → 意图改写 → 3 路并行召回（向量+HyDE+网络）→ RRF 融合 → gte-rerank 重排 → Qwen 流式生成 → SSE 前端展示
4. **对话历史**: MongoDB 正确保存多轮对话，历史查询/清空接口正常
5. **前端**: 导入页面显示进度，聊天页面支持流式打字机效果和图片展示
