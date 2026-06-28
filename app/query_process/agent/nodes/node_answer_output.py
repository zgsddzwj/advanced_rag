"""
回答输出节点（节点7）
1. 构建回答 Prompt
2. LLM 流式生成回答
3. SSE 推送 delta/final 事件
4. 图片 URL 提取
5. 助手消息写入 MongoDB
"""
import sys
import re
from typing import List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage

from app.query_process.agent.state import QueryGraphState
from app.core.logger import logger
from app.core.load_prompt import load_prompt
from app.lm.lm_utils import get_llm_client
from app.clients.mongo_history_utils import save_chat_message
from app.utils.task_utils import add_running_task, add_done_task
from app.utils.sse_utils import push_to_session, SSEEvent

# 参考内容每个切片最大长度
MAX_CHUNK_CONTENT_LEN = 800
# 上下文最大切片数
MAX_CONTEXT_CHUNKS = 8
# 图片区块正则
IMAGE_BLOCK_PATTERN = re.compile(r"【图片】\s*\n((?:[^\n]+\n?)+)", re.MULTILINE)


def node_answer_output(state: QueryGraphState) -> QueryGraphState:
    """回答输出节点：LLM 流式生成 + SSE 推送 + MongoDB 写入"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    is_stream = state.get("is_stream", False)
    add_running_task(state["task_id"], func_name, is_stream)

    try:
        reranked_docs = state.get("reranked_docs", [])
        query = state.get("rewritten_query") or state.get("query", "")
        history = state.get("history", [])
        item_names = state.get("item_names", [])
        session_id = state.get("session_id", "")
        task_id = state.get("task_id", "")

        # Step 1: 构建上下文
        context = _build_context(reranked_docs)

        # Step 2: 构建 Prompt
        prompt = _build_prompt(context, history, item_names, query)
        state["prompt"] = prompt

        # Step 3: LLM 生成回答
        if is_stream:
            answer = _stream_generate(prompt, task_id)
        else:
            answer = _invoke_generate(prompt)

        state["answer"] = answer

        # Step 4: 提取图片 URL
        image_urls = _extract_image_urls(answer)
        state["image_urls"] = image_urls

        # Step 5: 助手消息写入 MongoDB（使用 session_id）
        _save_assistant_message(state, answer, image_urls)

        # Step 6: SSE final 事件（使用 task_id，与队列创建时的 key 一致）
        if is_stream and task_id:
            push_to_session(task_id, SSEEvent.FINAL, {
                "answer": answer,
                "image_urls": image_urls,
                "item_names": item_names,
            })

        logger.info(f"回答生成完成，长度: {len(answer)}，图片: {len(image_urls)} 张")

    except Exception as e:
        logger.error(f"回答输出失败: {str(e)}", exc_info=True)
        state["answer"] = "抱歉，生成回答时出现错误，请稍后重试。"
        state["image_urls"] = []
        if is_stream:
            task_id = state.get("task_id", "")
            if task_id:
                push_to_session(task_id, SSEEvent.ERROR, {
                    "message": str(e),
                })
    finally:
        add_done_task(state["task_id"], func_name, is_stream)

    return state


def _build_context(reranked_docs: List[Dict[str, Any]]) -> str:
    """从重排结果构建参考上下文"""
    if not reranked_docs:
        return "（无相关参考内容）"

    parts = []
    for idx, doc in enumerate(reranked_docs[:MAX_CONTEXT_CHUNKS]):
        title = doc.get("title", "")
        content = doc.get("content", "")
        if len(content) > MAX_CHUNK_CONTENT_LEN:
            content = content[:MAX_CHUNK_CONTENT_LEN] + "..."

        part = f"【切片{idx + 1}】\n标题：{title}\n内容：{content}"
        parts.append(part)

    return "\n\n".join(parts)


def _build_prompt(
    context: str,
    history: List[Dict[str, Any]],
    item_names: List[str],
    query: str,
) -> str:
    """构建回答 Prompt"""
    # 格式化历史对话
    history_text = _format_history(history)
    item_names_text = "、".join(item_names) if item_names else "无"

    prompt = load_prompt(
        "answer_out",
        context=context,
        history=history_text,
        item_names=item_names_text,
        question=query,
    )
    return prompt


def _format_history(history: List[Dict[str, Any]]) -> str:
    """格式化历史对话"""
    if not history:
        return "（无历史对话）"

    lines = []
    for msg in history:
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            lines.append(f"用户：{text}")
        elif role == "assistant":
            lines.append(f"助手：{text}")
    return "\n".join(lines) if lines else "（无历史对话）"


def _stream_generate(prompt: str, task_id: str) -> str:
    """流式生成回答，逐 token 推送 SSE（使用 task_id 作为 SSE 队列 key）"""
    llm = get_llm_client()
    messages = [
        SystemMessage(content="你是一个智能助手，请根据参考内容准确回答用户问题。"),
        HumanMessage(content=prompt),
    ]

    full_answer = []
    for chunk in llm.stream(messages):
        token = getattr(chunk, "content", "")
        if token:
            full_answer.append(token)
            # 推送 delta 事件（task_id 与 SSE 队列创建时的 key 一致）
            if task_id:
                push_to_session(task_id, SSEEvent.DELTA, {"text": token})

    return "".join(full_answer)


def _invoke_generate(prompt: str) -> str:
    """非流式生成回答"""
    llm = get_llm_client()
    messages = [
        SystemMessage(content="你是一个智能助手，请根据参考内容准确回答用户问题。"),
        HumanMessage(content=prompt),
    ]
    resp = llm.invoke(messages)
    return getattr(resp, "content", "")


def _extract_image_urls(answer: str) -> List[str]:
    """从回答中提取图片 URL"""
    urls = []
    match = IMAGE_BLOCK_PATTERN.search(answer)
    if match:
        block = match.group(1)
        for line in block.strip().split("\n"):
            line = line.strip()
            if line and line.startswith("http"):
                urls.append(line)

    return urls


def _save_assistant_message(
    state: QueryGraphState, answer: str, image_urls: List[str]
):
    """将助手回答写入 MongoDB"""
    session_id = state.get("session_id", "")
    if not session_id:
        return

    try:
        save_chat_message(
            session_id=session_id,
            role="assistant",
            text=answer,
            rewritten_query=state.get("rewritten_query", ""),
            item_names=state.get("item_names", []),
            image_urls=image_urls,
        )
    except Exception as e:
        logger.warning(f"保存助手消息到 MongoDB 失败: {e}")
