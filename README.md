# 掌柜智库 — 高级 RAG 系统

基于 LangGraph 编排的高级检索增强生成（RAG）系统，包含完整的**文档导入**和**智能问答**两条流程，全部 AI 能力通过阿里云百炼 API 接入。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (:8000)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  React 前端   │  │  导入 API     │  │   查询 API     │ │
│  │  (Vite 构建)  │  │ /api/import/* │  │  /api/query/*  │ │
│  │  / /import    │  │               │  │  + SSE 流式    │ │
│  │  /chat        │  └───────┬──────┘  └───────┬───────┘ │
│  └──────────────┘          │                 │          │
│  ┌─────────────────────────▼─────────────────▼────────┐ │
│  │         导入 LangGraph (7节点) / 检索 LangGraph     │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
            │                          │
  ┌─────────▼──────────────────────────▼──────────────┐
  │              基础设施层 (Docker Compose)            │
  │  ┌────────┐  ┌────────┐  ┌─────────┐  ┌────────┐ │
  │  │ Milvus │  │ MinIO  │  │ MongoDB │  │  etcd  │ │
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
| **前端** | React 18 + TypeScript + Vite + Tailwind CSS |
| **前端渲染** | react-markdown + remark-gfm + rehype-highlight (代码高亮) |
| **后端** | FastAPI + SSE 流式输出 + LangGraph |
| **向量数据库** | Milvus 2.4（Dense + BM25 混合检索） |
| **文件存储** | MinIO |
| **对话历史** | MongoDB |
| **AI 模型** | 阿里云百炼（Qwen-Plus / Qwen-VL-Plus / text-embedding-v3 / gte-rerank） |
| **PDF 解析** | MinerU (magic-pdf) |
| **基础设施** | Docker Compose |
| **包管理** | uv (后端) + npm (前端) |
| **Python** | 3.11+ |

## 项目结构

```
advanced_rag/
├── docker-compose.yml                   # 基础设施编排
├── .env.example                         # 环境变量模板
├── README.md
│
├── frontend/                            # ═══ 前端 (React + Vite + TS) ═══
│   ├── package.json                     #   npm 依赖
│   ├── vite.config.ts                   #   Vite 配置 (开发代理 → :8000)
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html                       #   HTML 入口
│   └── src/
│       ├── main.tsx                     #   React 入口
│       ├── App.tsx                      #   路由定义
│       ├── index.css                    #   全局样式 + Tailwind + Markdown
│       ├── api/client.ts                #   API 封装 (fetch + SSE)
│       ├── types/index.ts               #   TypeScript 类型定义
│       ├── components/
│       │   ├── Layout.tsx               #   侧边栏布局
│       │   ├── MessageBubble.tsx        #   聊天消息 (Markdown 渲染)
│       │   └── TypingIndicator.tsx      #   打字动画
│       └── pages/
│           ├── Dashboard.tsx            #   系统首页
│           ├── ImportPage.tsx           #   知识库导入
│           └── ChatPage.tsx             #   智能问答 (SSE 流式)
│
├── backend/                             # ═══ 后端 (FastAPI + LangGraph) ═══
│   ├── pyproject.toml                   #   uv 项目配置 + 依赖
│   ├── main.py                          #   FastAPI 主应用入口
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
│   │   │   └── escape_milvus_string_utils.py
│   │   ├── import_process/              #   导入流程
│   │   │   ├── agent/
│   │   │   │   ├── state.py             #     ImportGraphState
│   │   │   │   ├── main_graph.py        #     导入图编排 (7 节点)
│   │   │   │   └── nodes/               #     7 个节点实现
│   │   │   └── api/file_import_service.py
│   │   └── query_process/               #   查询流程
│   │       ├── agent/
│   │       │   ├── state.py             #     QueryGraphState
│   │       │   ├── main_graph.py        #     检索图编排 (7 节点)
│   │       │   └── nodes/               #     7 个节点实现
│   │       └── api/query_service.py
│   │
│   ├── prompts/                         #   Prompt 模板
│   ├── test/                            #   测试脚本
│   └── examples/                        #   示例 PDF
│
├── specs/design-spec.md                 # 设计规格文档
└── docs/                                # 实现计划文档
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone git@github.com:zgsddzwj/advanced_rag.git
cd advanced_rag

# 后端：uv 创建虚拟环境并安装依赖
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -e "."

# 前端：npm 安装依赖
cd ../frontend
npm install
```

### 2. 配置环境变量

```bash
# 在项目根目录
cp .env.example .env
# 编辑 .env，填入真实的 DASHSCOPE_API_KEY
# 同时复制一份到 backend/ 目录（后端从此目录加载）
cp .env backend/.env
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

### 4. 构建前端

```bash
cd frontend
npm run build    # 产物输出到 frontend/dist/
```

### 5. 启动应用

```bash
cd backend
python main.py
```

访问 http://localhost:8000 即可使用：
- 系统首页：http://localhost:8000/
- 导入页面：http://localhost:8000/import
- 聊天页面：http://localhost:8000/chat

### 开发模式（可选）

前端开发时使用 Vite 热更新：

```bash
# 终端 1：启动后端
cd backend && python main.py

# 终端 2：启动 Vite 开发服务器
cd frontend && npm run dev
# 访问 http://localhost:3000 (API 自动代理到 :8000)
```

## 核心流程

### 导入流程（7 节点 LangGraph）

```
入口判断 → PDF转Markdown → 图片处理(VLM) → 文档切分
    → 商品名识别(LLM) → 向量化(Embedding API) → 入库Milvus
```

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
| `/assets/*` | 前端构建产物 (CSS/JS) |

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
cd backend

# 导入图结构测试
python test/02_import_graph_flow.py

# 检索图结构测试（含 RRF 算法验证）
python test/03_query_graph_flow.py

# 端到端集成测试（10 项验证）
python test/04_e2e_integration_test.py
```

## 许可证

MIT License
