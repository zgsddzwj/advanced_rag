"""
服务层（演进4）
================================================
承载业务用例编排，位于 API 路由与仓储/图执行之间：

- 路由层（controller）：解析请求 → 调用服务 → 包装信封，不含业务逻辑
- 服务层（service）：参数校验、任务编排、跨仓储协作、错误翻译
- 仓储层（repository）：纯数据访问

服务通过构造函数注入仓储依赖（默认取全局单例），可替换为测试替身。
"""
from app.services.import_service import ImportService
from app.services.query_service import QueryService
from app.services.document_service import DocumentService

__all__ = ["ImportService", "QueryService", "DocumentService"]
