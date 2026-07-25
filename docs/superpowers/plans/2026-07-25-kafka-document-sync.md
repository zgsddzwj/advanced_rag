# Kafka 文档实时同步计划

> **目标**: 接入 Kafka 消息队列，监听文档新增/变更/删除事件，实时增量更新 Milvus 中的 chunks 数据。

## 1. 背景分析

### 现状
- 文档导入通过 HTTP 上传 → BackgroundTasks 执行 LangGraph 7 节点流程 → 同步入库 Milvus
- 无事件驱动机制，无法响应文档变更/删除
- 无文档元数据管理，无法检测内容变更
- `node_import_milvus` 已有按 `file_title` 删旧插新的幂等逻辑，但仅在重新导入时触发

### 目标
- Kafka 生产者：导入完成/文档删除时发布事件
- Kafka 消费者：后台常驻监听，收到事件后增量更新 chunks
- 文档元数据：MongoDB 记录 `file_title → content_hash`，用于判断 ADD vs UPDATE
- 三类事件：`DOCUMENT_ADD` / `DOCUMENT_UPDATE` / `DOCUMENT_DELETE`

## 2. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 消息队列 | Apache Kafka 3.7 (KRaft) | 无需 Zookeeper，生产级，高吞吐 |
| Python 客户端 | aiokafka | 原生 async，与 FastAPI 无缝集成 |
| 元数据存储 | MongoDB | 已有基础设施，复用现有连接 |
| 事件格式 | JSON | 可读性好，易于扩展 |

## 3. 架构设计

```
┌──────────────┐      ┌─────────┐      ┌──────────────────┐
│  FastAPI     │      │  Kafka  │      │  Kafka Consumer  │
│  (Producer)  │─────▶│  Topic  │─────▶│  (后台常驻)       │
│              │      │ doc-    │      │                  │
│ POST /upload │      │ events  │      │ ADD:    全量导入  │
│ DELETE /doc  │      │         │      │ UPDATE: 删旧+重导 │
│              │      │         │      │ DELETE: Milvus删除│
└──────────────┘      └─────────┘      └────────┬─────────┘
                                                │
                                       ┌────────▼────────┐
                                       │  Milvus         │
                                       │  kb_chunks      │
                                       │  kb_item_names  │
                                       └─────────────────┘
                                       ┌─────────────────┐
                                       │  MongoDB        │
                                       │  document_meta  │
                                       │  (元数据+哈希)    │
                                       └─────────────────┘
```

## 4. 实施步骤

### Step 1: 基础设施 — Kafka Docker 服务
- `docker-compose.yml` 新增 Kafka 服务 (KRaft 模式，无 Zookeeper)
- 端口: 9092 (内部) / 29092 (外部)

### Step 2: 配置层 — `kafka_config.py`
- Kafka broker 地址、Topic 名称、Consumer Group
- 环境变量: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`

### Step 3: 文档元数据管理 — `document_meta_utils.py`
- MongoDB `document_meta` 集合
- `upsert_metadata(file_title, content_hash, ...)` — 插入或更新
- `get_metadata(file_title)` — 查询元数据
- `delete_metadata(file_title)` — 删除元数据
- `compute_content_hash(file_path)` — MD5 哈希

### Step 4: Kafka 生产者 — `kafka_producer.py`
- `publish_document_event(event_type, file_title, file_path, ...)`
- 事件类型: ADD / UPDATE / DELETE
- 启动时延迟初始化 (lifespan)
- 发送失败降级为日志告警，不阻断主流程

### Step 5: Kafka 消费者 — `kafka_consumer.py`
- 后台 asyncio task，FastAPI lifespan 中启动
- 消费 `document-events` topic
- 事件处理:
  - `DOCUMENT_ADD`: 触发完整 LangGraph 导入流程
  - `DOCUMENT_UPDATE`: 先删 Milvus 旧 chunks → 再触发导入流程
  - `DOCUMENT_DELETE`: 删除 Milvus 中该 file_title 的所有 chunks + item_names
- 错误重试: 最多 3 次，失败后记录死信日志
- 优雅关闭: lifespan exit 时取消 consumer task

### Step 6: API 端点 — `document_event_service.py`
- `DELETE /api/documents/{file_title}` — 删除文档，发布 DELETE 事件
- `POST /api/documents/reimport/{file_title}` — 重新导入，发布 UPDATE 事件
- 文档列表 API 增加 `status` 字段 (active/deleted/syncing)

### Step 7: 集成到现有导入流程
- `file_import_service.py` 的 `_run_import` 完成后:
  - 计算内容哈希
  - 与 MongoDB 元数据比对
  - 发布 ADD 或 UPDATE 事件到 Kafka
- `main.py` lifespan 中启动 Kafka consumer

### Step 8: 依赖与配置更新
- `pyproject.toml` 添加 `aiokafka`
- `.env` / `.env.example` 添加 Kafka 配置项
- `README.md` 更新架构图和说明

## 5. 事件 Schema

```json
{
  "event_id": "uuid",
  "event_type": "DOCUMENT_ADD | DOCUMENT_UPDATE | DOCUMENT_DELETE",
  "file_title": "文档标题",
  "file_path": "/path/to/file.pdf",
  "content_hash": "md5hash",
  "timestamp": "2026-07-25T10:00:00Z",
  "metadata": {
    "chunk_count": 15,
    "item_name": "主题"
  }
}
```

## 6. 验收标准

- [x] Kafka 服务可通过 `docker compose up -d` 启动
- [x] 上传文档后自动发布 ADD 事件，consumer 自动处理入库
- [x] 重新上传同标题文档自动发布 UPDATE 事件，旧 chunks 被删除后重新导入
- [x] DELETE API 触发后，Milvus 中对应 chunks 被清除
- [x] Consumer 启停跟随 FastAPI 生命周期
- [x] 所有异常有降级处理，不崩溃
