"""
统一 API 响应信封（演进2）
================================================
所有 JSON 接口统一返回三段式结构：

    {"code": "OK", "message": "ok", "data": <原载荷>}

- 成功：ok(data)；业务数据整体放入 data，结构与演进前完全一致
- 失败：由全局异常处理器生成 fail(...)，code 为机器可读错误码
- SSE 流式接口不经过信封（事件格式自有协议），保持不变
"""
from typing import Any, Dict, Optional

SUCCESS_CODE = "OK"


def ok(data: Any = None, *, message: str = "ok") -> Dict[str, Any]:
    """构造成功响应信封"""
    return {"code": SUCCESS_CODE, "message": message, "data": data}


def fail(
    code: str,
    message: str,
    *,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造失败响应信封"""
    payload: Dict[str, Any] = {"code": code, "message": message, "data": None}
    if details:
        payload["details"] = details
    return payload
