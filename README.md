# NexusRAG — 智能知识检索引擎

> 基于 LangGraph 编排的企业级 RAG 系统，支持 PDF/MD 智能导入、Dense+BM25 混合检索、HyDE 增强、RRF 融合与 Rerank 精排，提供流式问答体验。

## 项目简介

NexusRAG 是一套完整的检索增强生成（RAG）系统，包含**文档导入**和**智能问答**两条核心流程，全部 AI 能力通过阿里云百炼 API 接入。系统采用 LangGraph 进行节点编排，实现从文档上传、解析、切分、向量化到多路混合检索、融合重排、流式回答的全链路自动化。

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI (:8000)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  React 前端   │  │  导入 API     │  │   查询 API     │ │
│  │  (Vite 构建)  │  │ /api/import/* │  │  /api/query/*  │ │
│  │  / /import    │  │ /api/documents│  │  + SSE 流式    │ │
│  │  /chat        │  └───────┬──────┘  └───────┬───────┘ │
│  └──────────────┘          │                 │          │
│  ┌─────────────────────────▼─────────────────▼────────┐ │
│  │     导入 LangGraph (7节点) / 检索 LangGraph        │ │
│  │          + Kafka Producer (事件发布)               │ │
│  └───────────────────────────┬────────────────────────┘ │
└──────────────────────────────┼──────────────────────────┘
                               │
  ┌────────────────────────────▼──────────────────────────┐
  │              Kafka (document-events)                   │
  │          + Kafka Consumer (后台常驻)                   │
  │   ADD→全量导入  UPDATE→删旧+重导  DELETE→清除          │
  └───────────────────────────┬──────────────────────────┘
            │                          │
  ┌─────────▼──────────────────────────▼──────────────┐
  │              基础设施层 (Docker Compose)            │
  │  ┌────────┐  ┌────────┐  ┌─────────┐  ┌────────┐ │
  │  │ Milvus │  │ MinIO  │  │ MongoDB │  │ Kafka  │ │
  │  └────────┘  └────────┘  └─────────┘  └────────┘ │
  │  ┌────────┐                                     │
  │  │  etcd  │                                     │
  │  └────────┘                                     │
  └─────────────────────────────────────────────────┘
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
| **向量数据库** | Milvus 2.5（Dense + BM25 混合检索） |
| **消息队列** | Apache Kafka 3.7 (KRaft) — 文档事件驱动同步 |
| **文件存储** | MinIO |
| **对话历史** | MongoDB |
| **AI 模型** | 阿里云百炼（Qwen-Plus / Qwen-VL-Plus / text-embedding-v3 / gte-rerank） |
| **PDF 解析** | MinerU 云端 API |
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
│       │   ├── ThinkingProcess.tsx      #   思考过程展示
│       │   └── TypingIndicator.tsx      #   打字动画
│       └── pages/
│           ├── Dashboard.tsx            #   系统首页
│           ├── ImportPage.tsx           #   知识库导入
│           ├── ChatPage.tsx             #   智能问答 (SSE 流式)
│           └── DocumentsPage.tsx        #   文档预览
│
├── backend/                             # ═══ 后端 (FastAPI + LangGraph) ═══
│   ├── pyproject.toml                   #   uv 项目配置 + 依赖
│   ├── uv.lock                          #   依赖版本锁定
│   ├── main.py                          #   FastAPI 主应用入口
│   │
│   ├── app/
│   │   ├── core/                        #   核心工具
│   │   │   ├── logger.py                #     日志 (loguru)
│   │   │   └── load_prompt.py           #     Prompt 模板加载器
│   │   ├── conf/                        #   配置层
│   │   │   ├── lm_config.py             #     AI 模型配置
│   │   │   ├── milvus_config.py         #     Milvus 配置
│   │   │   ├── kafka_config.py          #     Kafka 配置
│   │   │   ├── bailian_mcp_config.py    #     百炼 MCP 配置
│   │   │   └── mineru_config.py         #     MinerU 配置
│   │   ├── lm/                          #   AI 模型封装层
│   │   │   ├── lm_utils.py              #     LLM (Qwen-Plus)
│   │   │   ├── vlm_utils.py             #     VLM (Qwen-VL-Plus)
│   │   │   ├── embedding_utils.py       #     Embedding (text-embedding-v3)
│   │   │   ├── rerank_utils.py          #     Rerank (gte-rerank)
│   │   │   └── web_search_utils.py      #     网络搜索 (百炼 MCP)
│   │   ├── clients/                     #   基础设施客户端
│   │   │   ├── milvus_utils.py          #     Milvus 连接 + 混合搜索
│   │   │   ├── minio_utils.py           #     MinIO 文件操作
│   │   │   ├── mongo_history_utils.py   #     MongoDB 对话历史
│   │   │   ├── document_meta_utils.py   #     文档元数据管理 (content_hash)
│   │   │   ├── kafka_producer.py        #     Kafka 生产者 (事件发布)
│   │   │   └── kafka_consumer.py        #     Kafka 消费者 (增量同步)
│   │   ├── utils/                       #   通用工具
│   │   │   ├── task_utils.py            #     任务状态管理
│   │   │   ├── sse_utils.py             #     SSE 事件队列
│   │   │   ├── thinking_utils.py        #     思考过程推送
│   │   │   ├── path_util.py             #     项目路径工具
│   │   │   └── escape_milvus_string_utils.py
│   │   ├── import_process/              #   导入流程
│   │   │   ├── agent/
│   │   │   │   ├── state.py             #     ImportGraphState
│   │   │   │   ├── main_graph.py        #     导入图编排 (7 节点)
│   │   │   │   └── nodes/               #     7 个节点实现
│   │   │   └── api/
│   │   │       ├── file_import_service.py      # 文件上传导入
│   │   │       ├── document_preview_service.py # 文档列表/切片预览
│   │   │       └── document_event_service.py   # 文档删除/重导入(Kafka)
│   │   └── query_process/               #   查询流程
│   │       ├── agent/
│   │       │   ├── state.py             #     QueryGraphState
│   │       │   ├── main_graph.py        #     检索图编排 (7 节点)
│   │       │   └── nodes/               #     7 个节点实现
│   │       └── api/query_service.py
│   │
│   ├── prompts/                         #   Prompt 模板
│   ├── test/                            #   测试脚本
│   ├── examples/                        #   示例 PDF
│   └── logs/                            #   运行日志
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

# 后端：uv 自动创建虚拟环境并安装依赖
cd backend
uv sync

# 前端：npm 安装依赖
cd ../frontend
npm install
```

### 2. 配置环境变量

```bash
# 复制模板到 backend/ 目录（后端从此目录加载 .env）
cp .env.example backend/.env
# 编辑 backend/.env，填入真实的 DASHSCOPE_API_KEY
# 获取地址：https://bailian.console.aliyun.com/ → 模型广场 → API Key
```

### 3. 启动基础设施

```bash
docker compose up -d
```

启动后包含 5 个服务：
- **Milvus** — 向量数据库 (:19530)
- **MinIO** — 文件存储 (:9000, 控制台 :9001)
- **MongoDB** — 对话历史 + 文档元数据 (:27017)
- **Kafka** — 消息队列，文档事件驱动 (:29092)
- **etcd** — Milvus 依赖服务 (:2379)

### 4. 构建前端

```bash
cd frontend
npm run build    # 产物输出到 frontend/dist/
```

### 5. 启动应用

```bash
cd backend
uv run python main.py
```

启动时会自动校验 `DASHSCOPE_API_KEY` 配置，若为占位符会输出警告提示。

访问 http://localhost:8000 即可使用：
- 系统首页：http://localhost:8000/
- 导入页面：http://localhost:8000/import
- 聊天页面：http://localhost:8000/chat
- 文档预览：http://localhost:8000/documents

### 开发模式（可选）

前端开发时使用 Vite 热更新：

```bash
# 终端 1：启动后端
cd backend && uv run python main.py

# 终端 2：启动 Vite 开发服务器
cd frontend && npm run dev
# 访问 http://localhost:3000 (API 自动代理到 :8000)
```

## 核心流程

### 导入流程（7 节点 LangGraph）

```
入口判断 → PDF转Markdown → 图片处理(VLM) → 文档切分
    → 主题识别(LLM) → 向量化(Embedding API) → 入库Milvus
```

### 查询流程（7 节点 LangGraph + SSE）

```
主题确认 → 向量检索 → HyDE检索 → (网络搜索?) → RRF融合 → Rerank重排 → 流式回答
```

1. **主题确认**：加载历史 → LLM 改写查询+提取文档主题 → Milvus 向量对齐
2. **向量检索**：Dense + BM25 混合检索（支持主题过滤）
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
| `/documents` | 文档预览页面 |
| `/assets/*` | 前端构建产物 (CSS/JS) |

### 导入 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/import/upload` | 上传文件并触发导入（限制 100MB） |
| GET | `/api/import/status/{task_id}` | 查询导入状态 |
| GET | `/api/import/health` | 导入服务健康检查 |

### 查询 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/query/ask` | 提交查询 |
| GET | `/api/query/stream/{task_id}` | SSE 流式回答 |
| GET | `/api/query/history/{session_id}` | 获取对话历史 |
| DELETE | `/api/query/history/{session_id}` | 清空对话历史 |
| GET | `/api/query/health` | 健康检查 |

### 文档预览 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/documents/list` | 获取已导入文档列表 |
| GET | `/api/documents/chunks/{file_title}` | 获取文档切分详情 |
| GET | `/api/documents/meta/list` | 获取文档元数据（含同步状态） |

### 文档事件 API (Kafka 驱动)

| 方法 | 路径 | 说明 |
|------|------|------|
| DELETE | `/api/documents/{file_title}` | 删除文档（发布 DELETE 事件，异步清除 chunks） |
| POST | `/api/documents/reimport/{file_title}` | 重新导入文档（发布 UPDATE 事件，删旧 chunks 后重导） |

## Kafka 文档事件同步

系统通过 Kafka 实现文档变更的实时监听和 chunks 增量更新：

### 事件类型

| 事件类型 | 触发场景 | 消费者处理 |
|---------|---------|-----------|
| `DOCUMENT_ADD` | 新文档导入完成 | 触发完整 LangGraph 导入流程 → 入库 Milvus |
| `DOCUMENT_UPDATE` | 同标题文档内容变更 | 先删 Milvus 旧 chunks → 重新导入 |
| `DOCUMENT_DELETE` | 调用删除 API | 删除 Milvus chunks + item_names + 元数据 |

### 工作流程

1. 文档上传 → LangGraph 导入 → 计算内容哈希 → 与 MongoDB 元数据比对
2. 判断事件类型（ADD/UPDATE）→ 发布到 Kafka `document-events` topic
3. Kafka 消费者后台常驻监听，收到事件后异步处理
4. 更新 Milvus chunks + MongoDB 元数据

### 降级机制

- Kafka 不可用时，导入流程正常完成，仅跳过事件发布（降级为日志告警）
- 消费者处理失败自动重试 3 次，失败后记录死信日志
- 设置 `KAFKA_ENABLED=false` 可完全关闭 Kafka 功能

## 测试

```bash
cd backend

# 导入图结构测试
uv run python test/02_import_graph_flow.py

# 检索图结构测试（含 RRF 算法验证）
uv run python test/03_query_graph_flow.py

# 端到端集成测试（10 项验证）
uv run python test/04_e2e_integration_test.py
```

## 项目成熟度评估

### ✅ 已具备的能力

| 维度 | 说明 |
|------|------|
| **架构设计** | LangGraph 双流程编排，导入7节点 + 检索7节点，职责清晰 |
| **检索能力** | Dense + BM25 混合检索 + HyDE 假设性检索 + 网络搜索补充 |
| **排序能力** | RRF 多路融合 + gte-rerank 精排 + 动态截断 |
| **流式体验** | SSE 流式回答 + 实时思考过程推送 |
| **文档处理** | MinerU 云端 PDF 解析 + VLM 图片描述 + 智能切分 |
| **错误容错** | 各节点 try/catch 降级处理，失败不阻断主流程 |
| **基础设施** | Docker Compose 一键编排（Milvus + MinIO + MongoDB + etcd） |
| **配置管理** | .env 环境变量 + 启动时自动校验 |
| **文档预览** | 支持查看已导入文档列表及切分详情 |
| **消息队列** | Kafka 事件驱动，文档变更实时同步 chunks |
| **结构测试** | 导入图/检索图/端到端集成测试（10 项验证） |

### ⚠️ 距离生产级还需补齐

| 维度 | 现状 | 建议 |
|------|------|------|
| **认证鉴权** | 无认证，API 完全开放 | 添加 JWT / API Key 认证中间件 |
| **限流防护** | 无限流 | 添加 rate limiter（如 slowapi） |
| **任务队列** | ~~threading + BackgroundTasks~~ Kafka 事件驱动 + 后台消费者 |
| **监控告警** | 仅 loguru 本地日志 | 接入 Prometheus + Grafana 指标监控 |
| **CI/CD** | 无自动化流水线 | 搭建 GitHub Actions 自动测试 + 部署 |
| **HTTPS** | 仅 HTTP | 配置 Nginx 反向代理 + TLS 证书 |
| **负载测试** | 未做压测 | 使用 Locust / k6 验证并发承载能力 |
| **数据备份** | 无备份策略 | Milvus 快照 + MongoDB 定期备份 |

> **总结**：当前系统已具备完整的核心功能和良好的架构基础，可作为 **生产级 MVP** 投入小规模使用。要达到真正的企业级生产部署，建议优先补齐认证鉴权、任务队列和监控告警三项。

## 许可证

MIT License
