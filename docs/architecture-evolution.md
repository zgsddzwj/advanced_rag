# NexusRAG 架构演进记录

本文档记录 2026-09 完成的 8 次深度架构演进。每次演进独立提交、独立可回滚，
全部演进保持向后兼容：环境变量契约、API 路径、SSE 事件协议均未破坏。

| # | 主题 | 核心交付 |
|---|------|---------|
| 1 | 配置中心化 | pydantic-settings 统一配置层 |
| 2 | 异常与响应契约 | 业务异常体系 + 全局错误处理 + 统一响应信封 |
| 3 | 数据访问层 | Repository 模式 + Mongo 懒加载连接 |
| 4 | 服务层与 DI | 用例服务 + FastAPI 依赖注入 |
| 5 | 可观测性 | RequestID 链路 + 进程内指标 + 健康聚合 |
| 6 | 事件驱动可靠性 | 处理器注册表 + 幂等 + 重试 + 死信队列 |
| 7 | 检索管线可插拔 | 检索器注册表 + 按请求检索策略 |
| 8 | 多级缓存 | TTLCache 抽象 + 四个业务缓存 + 指标/健康集成 |

## 演进1：配置中心化

**问题**：6 个配置类分散读取 `os.getenv`，无类型校验，配置错误要运行到相关代码路径才暴露。

**方案**：
- `app/conf/settings.py`：pydantic-settings 单一配置源，启动即校验（fail-fast）
- 环境变量契约 100% 兼容（字段名与 .env 一一对应，大小写不敏感）
- 敏感值脱敏 `describe()`，用于启动日志与健康检查
- 旧配置模块保留为兼容 shim，内部调用点全部迁移

## 演进2：统一异常体系 + 响应信封

**问题**：HTTPException、`{"error": ...}` 字典、裸 dict 混用；前端只能显示 HTTP 状态码。

**方案**：
- `AppError` 语义异常基类（code/status/details）+ 5 个子类；上游依赖失败统一 502
- 全局异常处理器：业务异常/422 校验/HTTPException/未捕获异常 → 统一信封
- 响应信封 `{code, message, data}`，业务数据结构不变；未捕获异常消息脱敏
- 前端 `client.ts` 统一解包，页面获得后端真实错误消息

## 演进3：Repository 数据访问层

**问题**：业务节点与 API 直接拼接 pymongo/pymilvus 调用，无法脱离基础设施测试；
Mongo 在模块导入期同步建连（基础设施未就绪时最长阻塞 30s）。

**方案**：
- `app/repository/`：对话历史 / 文档元数据 / Milvus 三个仓储，支持注入替身
- Mongo 懒加载连接管理器 + 可配置 serverSelection 超时，导入期零开销
- `main.py` shutdown 统一关闭连接

## 演进4：服务层 + 依赖注入

**问题**：业务逻辑写在路由函数里，无法复用、难以测试。

**方案**：
- `app/services/`：ImportService（上传校验/导入编排）、QueryService（问答编排/历史）、
  DocumentService（预览/删除/重导入）
- `app/dependencies.py` 提供 Depends 注入；路由瘦身为纯控制器
- 服务构造函数注入仓储，测试可整体替换依赖

## 演进5：可观测性

**问题**：日志无请求关联，无指标，故障排查靠猜；健康检查只有静态 ping。

**方案**：
- RequestID 中间件（contextvar 跨线程传播）+ 日志格式注入 request_id 列
- 无依赖指标注册表：`http_requests_total`（route 模板防标签爆炸）、耗时 summary、
  SSE 队列 gauge；`/metrics` 输出 Prometheus 文本格式
- `/api/health` 并发探活 Mongo/Milvus/MinIO/Kafka，永不抛错，degraded 不崩溃

## 演进6：事件驱动可靠性

**问题**：消费者主循环内嵌业务分支；事件重复投递会重复处理；失败事件重试后仅记日志。

**方案**：
- `app/events/`：DocumentEvent 模型（消费前强校验）+ `@register_handler` 注册表（开闭原则）
- 幂等消费：`processed_events` 集合 + TTL 索引，重复 event_id 跳过
- 重试配置化（指数退避）→ 耗尽转 `document-events-dlq`（附失败上下文可重放），
  元数据标记 `failed` + `last_error`；坏消息不阻塞消费循环

## 演进7：检索管线可插拔

**问题**：检索参数硬编码在节点中（top_k、RRF k、HyDE/联网搜索路径固定），无法按请求调整。

**方案**：
- `RetrievalConfig`：按请求检索策略（HyDE 开关、联网搜索三态、top_k、RRF 参数），
  默认值与历史常量一致（行为零变更），非法配置回退默认
- 检索器注册表：MilvusHybridRetriever 协议化，embedding/hyde 两路注册即用
- `/query/ask` 带 `retrieval` 可选字段；前端 ChatPage 提供策略开关 UI

## 演进8：多级缓存

**问题**：同一查询重复调用 Embedding/LLM/联网搜索 API，成本与延迟浪费。

**方案**：
- `TTLCache`：线程安全 + LRU 驱逐 + 单调时钟 TTL + 命中统计；指标自动上报
- 四个业务缓存（TTL 可配置）：
  | 缓存 | 内容 | TTL |
  |------|------|-----|
  | embedding | 文本→向量（批量检索合并命中） | 6h |
  | hyde_text | 查询→假设性回答 | 1h |
  | web_search | 查询→联网结果（空结果不缓存） | 30min |
  | item_name_alignment | 主题名→对齐结果 | 10min |
- 失败结果一律不缓存（LLM/外部调用失败可立即重试）
- `/api/health` 输出各缓存命中率与条目数

## 分层架构总览（演进后）

```
路由层 (api/*)            请求解析 → Depends 注入 → ok() 信封包装
    ↓
服务层 (services/*)       用例编排、参数校验、错误翻译（演进4）
    ↓
领域层
 ├─ import_process/agent  LangGraph 导入图（7 节点）
 ├─ query_process/agent   LangGraph 检索图（7 节点）+ 检索器注册表（演进7）
 └─ events/               事件模型 + 处理器注册表（演进6）
    ↓
仓储层 (repository/*)     Mongo / Milvus 数据访问（演进3）
    ↓
基础设施 (clients/*)      Kafka / MinIO 客户端与连接管理
横切面：settings（演进1）· 异常/信封（演进2）· metrics/health/中间件（演进5）· cache（演进8）
```

## 验证

- pytest 单测 104 个（`cd backend && uv run pytest tests/ -q`），全部不依赖真实基础设施
- 前端 `npm run build` 通过；API 路径、SSE 协议、环境变量契约全部保持兼容
