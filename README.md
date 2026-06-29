# 掌柜智库 — 高级 RAG 系统

基于 LangGraph 编排的高级检索增强生成（RAG）系统，包含完整的**文档导入**和**智能问答**两条流程，全部 AI 能力通过阿里云百炼 API 接入。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (:8000)                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  前端服务    │  │  导入 API     │  │   查询 API     │  │
│  │  / /import  │  │ /api/import/* │  │  /api/query/*  │  │
│  │  /chat      │  │               │  │  + SSE 流式    │  │
│  └─────────────┘  └───────┬──────┘  └───────┬───────┘  │
│                           │                 │            │
│  ┌────────────────────────▼─────────────────▼────────┐  │
│  │         导入 LangGraph (7节点) / 检索 LangGraph     │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
            │                          │
  ┌─────────▼──────────────────────────▼──────────────┐
  │              基础设施层 (Docker Compose)            │
  │  ┌────────┐  ┌────────┐  ┌─────────┐  ┌────────┐ │
  │  │ Milvus │  │ MinIO  │  │ MongoDB │  │  etcd  │ │
  │  │ 向量检索 │  │ 文件存储│  │ 对话历史 │  │  服务  │ │
  │  └────────┘  └────────┘  └─────────┘  └────────┘ │
  └───────────────────────────────────────────────────┘
            │                          │
  ┌─────────▼──────────────────────────▼──────────────┐
  │           阿里云百炼 API (DashScope)               │
  │  LLM (Qwen-Plus) · VLM (Qwen-VL-Plus)             │
  │  Embedding (text-embedding-v3) · Rerank (gte-rerank)│
  │  网络搜索 (MCP)                                    │
  └───────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 原生 HTML/CSS/JS，侧边栏布局 + SSE 流式接收 |
| 工作流编排 | LangGraph |
| Web 框架 | FastAPI + SSE 流式输出 |
| 向量数据库 | Milvus 2.4（Dense + BM25 混合检索） |
| 文件存储 | MinIO |
| 对话历史 | MongoDB |
| AI 模型 | 阿里云百炼（Qwen-Plus / Qwen-VL-Plus / text-embedding-v3 / gte-rerank） |
| PDF 解析 | MinerU (magic-pdf) |
| 基础设施 | Docker Compose |
| Python | 3.11+ |

## 项目结构

```
advanced_rag/
├── docker-compose.yml                   # 基础设施编排
├── pyproject.toml                       # 项目依赖
├── .env.example                         # 环境变量模板
├── README.md
│
├── frontend/                            # ═══ 前端服务 ═══
│   ├── index.html                       #   系统首页 (Dashboard)
│   ├── import.html                      #   知识库导入页面
│   ├── chat.html                        #   智能问答页面
│   ├── css/common.css                   #   公共样式 (侧边栏/卡片/按钮)
│   └── js/
│       ├── config.js                    #   API 端点 + 导入节点配置
│       ├── api.js                       #   API 封装层
│       ├── index.js                     #   首页逻辑 (健康检查)
│       ├── import.js                    #   导入逻辑 (上传+轮询)
│       └── chat.js                      #   问答逻辑 (SSE 流式)
│
├── backend/                             # ═══ 后端服务 ═══
│   ├── main.py                          #   FastAPI 主应用入口（前端 + API）
│   │
│   ├── app/
│   │   ├── core/                        #   核心工具
│   │   │   ├── logger.py                #     日志 (loguru)
│   │   │   └── load_prompt.py           #     Prompt 模板加载器
│   │   ├── conf/                        #   配置层
│   │   │   ├── lm_config.py             #     AI 模型配置
│   │   │   ├── milvus_config.py         #     Milvus 配置
│   │   │   ├── bailian_mcp_config.py    #     百炼 MCP 配置
│   │   │   ├── mineru_config.py         #     MinerU 配置
│   │   │   └── embedding_config.py      #     Embedding 配置
│   │   ├── lm/                          #   AI 模型封装层
│   │   │   ├── lm_utils.py              #     LLM (Qwen-Plus)
│   │   │   ├── vlm_utils.py             #     VLM (Qwen-VL-Plus)
│   │   │   ├── embedding_utils.py       #     Embedding (text-embedding-v3)
│   │   │   ├── rerank_utils.py          #     Rerank (gte-rerank)
│   │   │   └── web_search_utils.py      #     网络搜索 (百炼 MCP)
│   │   ├── clients/                     #   基础设施客户端
│   │   │   ├── milvus_utils.py          #     Milvus 连接 + 混合搜索
│   │   │   ├── minio_utils.py           #     MinIO 文件操作
│   │   │   └── mongo_history_utils.py   #     MongoDB 对话历史
│   │   ├── utils/                       #   通用工具
│   │   │   ├── task_utils.py            #     任务状态管理
│   │   │   ├── sse_utils.py             #     SSE 事件队列
│   │   │   ├── path_util.py             #     项目路径工具
│   │   │   └── escape_milvus_string_utils.py  # Milvus 字符串转义
│   │   ├── import_process/              #   导入流程
│   │   │   ├── agent/
│   │   │   │   ├── state.py             #     ImportGraphState
│   │   │   │   ├── main_graph.py        #     导入图编排 (7 节点)
│   │   │   │   └── nodes/
│   │   │   │       ├── node_entry.py        # ① 入口：文件类型判断
│   │   │   │       ├── node_pdf_to_md.py    # ② PDF→Markdown (MinerU)
│   │   │   │       ├── node_md_img.py       # ③ 图片处理 (VLM)
│   │   │   │       ├── node_document_split.py# ④ 文档切分
│   │   │   │       ├── node_item_name_recognition.py # ⑤ 商品名识别
│   │   │   │       ├── node_bge_embedding.py# ⑥ 向量化 (Embedding API)
│   │   │   │       └── node_import_milvus.py# ⑦ 入库 Milvus
│   │   │   └── api/file_import_service.py   # 导入 FastAPI 路由
│   │   └── query_process/               #   查询流程
│   │       ├── agent/
│   │       │   ├── state.py             #     QueryGraphState
│   │       │   ├── main_graph.py        #     检索图编排 (7 节点)
│   │       │   └── nodes/
│   │       │       ├── node_item_name_confirm.py    # ① 商品名确认+查询改写
│   │       │       ├── node_search_embedding.py     # ② 向量+BM25混合检索
│   │       │       ├── node_search_embedding_hyde.py# ③ HyDE假设性文档检索
│   │       │       ├── node_web_search_mcp.py       # ④ 百炼MCP网络搜索
│   │       │       ├── node_rrf.py                  # ⑤ RRF多路融合
│   │       │       ├── node_rerank.py               # ⑥ gte-rerank重排
│   │       │       └── node_answer_output.py        # ⑦ LLM流式回答+SSE
│   │       └── api/query_service.py     #   查询 FastAPI 路由
│   │
│   ├── prompts/                         #   Prompt 模板
│   │   ├── item_name_recognition.prompt
│   │   ├── item_name_confirm.prompt
│   │   ├── hyde_generate.prompt
│   │   └── answer_out.prompt
│   │
│   ├── test/                            #   测试脚本
│   │   ├── 02_import_graph_flow.py      #     导入图测试
│   │   ├── 03_query_graph_flow.py       #     检索图测试
│   │   └── 04_e2e_integration_test.py   #     端到端集成测试
│   │
│   └── examples/                        #   示例文件
│       ├── Sample1.pdf
│       ├── Sample2.pdf
│       └── Sample3.pdf
│
├── specs/design-spec.md                 # 设计规格文档
└── docs/superpowers/plans/              # 实现计划文档
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone git@github.com:zgsddzwj/advanced_rag.git
cd advanced_rag

# 创建虚拟环境
uv venv .venv
source .venv/bin/activate

# 安装依赖
uv pip install -r pyproject.toml
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入真实的 DASHSCOPE_API_KEY
```

### 3. 启动基础设施

```bash
docker compose up -d
```

启动后包含 4 个服务：
- **Milvus** — 向量数据库 (:19530)
- **MinIO** — 文件存储 (:9000, 控制台 :9001)
- **MongoDB** — 对话历史 (:27017)
- **etcd** — Milvus 依赖服务 (:2379)

### 4. 启动应用

```bash
python backend/main.py
```

访问 http://localhost:8000 即可使用：
- 系统首页：http://localhost:8000/
- 导入页面：http://localhost:8000/import
- 聊天页面：http://localhost:8000/chat

## 核心流程

### 导入流程（7 节点 LangGraph）

```
入口判断 → PDF转Markdown → 图片处理(VLM) → 文档切分
    → 商品名识别(LLM) → 向量化(Embedding API) → 入库Milvus
```

1. **入口判断**：识别文件类型（PDF/MD），提取文件名
2. **PDF转Markdown**：调用 MinerU (magic-pdf) 解析 PDF
3. **图片处理**：扫描 Markdown 图片 → 上传 MinIO → VLM 生成描述 → 替换链接
4. **文档切分**：基于标题层级递归切分，拼接标题路径
5. **商品名识别**：LLM 从内容中提取商品/设备名称
6. **向量化**：调用 text-embedding-v3 API 批量生成稠密向量
7. **入库Milvus**：创建集合（含 BM25 Function）→ 批量插入

### 查询流程（7 节点 LangGraph + SSE）

```
商品名确认 → 向量检索 → HyDE检索 → (网络搜索?) → RRF融合 → Rerank重排 → 流式回答
```

1. **商品名确认**：加载历史 → LLM 改写查询+提取商品名 → Milvus 向量对齐
2. **向量检索**：Dense + BM25 混合检索（支持商品名过滤）
3. **HyDE检索**：LLM 生成假设性回答 → 向量化 → 混合检索
4. **网络搜索**：结果不足时调用百炼 MCP 联网搜索
5. **RRF融合**：三路结果 Reciprocal Rank Fusion 融合排序
6. **Rerank重排**：gte-rerank API 精准重排序 + 动态截断
7. **回答输出**：LLM 流式生成 → SSE 推送 → 图片提取 → MongoDB 写入

## API 接口

### 前端页面

| 路径 | 说明 |
|------|------|
| `/` | 系统首页 (Dashboard) |
| `/import` | 知识库导入页面 |
| `/chat` | 智能问答页面 |
| `/static/*` | 静态资源 (CSS/JS) |

### 导入 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/import/upload` | 上传文件并触发导入 |
| GET | `/api/import/status/{task_id}` | 查询导入状态 |

### 查询 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/query/ask` | 提交查询 |
| GET | `/api/query/stream/{task_id}` | SSE 流式回答 |
| GET | `/api/query/history/{session_id}` | 获取对话历史 |
| DELETE | `/api/query/history/{session_id}` | 清空对话历史 |
| GET | `/api/query/health` | 健康检查 |

## 测试

```bash
# 导入图结构测试
python backend/test/02_import_graph_flow.py

# 检索图结构测试（含 RRF 算法验证）
python backend/test/03_query_graph_flow.py

# 端到端集成测试（10 项验证）
python backend/test/04_e2e_integration_test.py
```

## 许可证

MIT License
