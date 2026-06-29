"""
商品名识别节点
利用LLM从文档切片中提取商品/设备名称，生成稠密向量存入Milvus
"""
import os
import sys
from typing import List, Dict, Any, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.lm.lm_utils import get_llm_client
from app.lm.embedding_utils import generate_embedding
from app.clients.milvus_utils import get_milvus_client, create_item_names_collection
from app.utils.escape_milvus_string_utils import escape_milvus_string
from app.conf.lm_config import lm_config
from app.conf.milvus_config import milvus_config
from app.core.logger import logger

DEFAULT_ITEM_NAME_CHUNK_K = 5
SINGLE_CHUNK_CONTENT_MAX_LEN = 800
CONTEXT_TOTAL_MAX_CHARS = 2500


def node_item_name_recognition(state: ImportGraphState) -> ImportGraphState:
    """商品主体名称识别节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        file_title, chunks = _step_1_get_inputs(state)
        if not chunks:
            logger.warning("无有效切片数据，跳过识别")
            return state

        context = _step_2_build_context(chunks)
        item_name = _step_3_call_llm(file_title, context)
        _step_4_update_chunks(state, chunks, item_name)
        _step_5_save_to_milvus(state, file_title, item_name)

        logger.info(f"商品名称识别完成: {item_name}")

    except Exception as e:
        logger.error(f"商品名称识别失败: {str(e)}", exc_info=True)
        state["item_name"] = state.get("file_title", "未知商品")
    finally:
        add_done_task(state["task_id"], func_name)

    return state


def _step_1_get_inputs(state: ImportGraphState) -> Tuple[str, List[Dict]]:
    """提取并校验输入数据"""
    file_title = state.get("file_title", "") or state.get("file_name", "")
    chunks = state.get("chunks") or []

    if not file_title and chunks and isinstance(chunks[0], dict):
        file_title = chunks[0].get("file_title", "")

    if not isinstance(chunks, list) or not chunks:
        logger.warning("chunks为空或非列表类型")
        return file_title, []

    logger.info(f"输入校验完成，获取到 {len(chunks)} 个切片")
    return file_title, chunks


def _step_2_build_context(chunks: List[Dict], k: int = DEFAULT_ITEM_NAME_CHUNK_K,
                          max_chars: int = CONTEXT_TOTAL_MAX_CHARS) -> str:
    """构建大模型识别上下文"""
    if not chunks:
        return ""

    parts: List[str] = []
    total_chars = 0

    for idx, chunk in enumerate(chunks[:k]):
        if not isinstance(chunk, dict):
            continue
        chunk_title = chunk.get("title", "").strip()
        chunk_content = chunk.get("content", "").strip()
        if not (chunk_title or chunk_content):
            continue
        if len(chunk_content) > SINGLE_CHUNK_CONTENT_MAX_LEN:
            chunk_content = chunk_content[:SINGLE_CHUNK_CONTENT_MAX_LEN]

        piece = f"【切片{idx + 1}】\n标题：{chunk_title} \n内容：{chunk_content}"
        parts.append(piece)
        total_chars += len(piece)
        if total_chars > max_chars:
            break

    context = "\n\n".join(parts).strip()[:max_chars]
    logger.info(f"上下文构建完成，长度: {len(context)} 字符")
    return context


def _step_3_call_llm(file_title: str, context: str) -> str:
    """调用LLM识别商品名称"""
    if not context:
        return file_title

    try:
        llm = get_llm_client()

        system_prompt = "你是一个商品识别专家。请从用户提供的文档内容中，精准识别出该文档描述的商品或设备名称。仅返回纯文本的商品名称，不要有任何额外解释。"
        human_prompt = f"文件标题：{file_title}\n\n文档内容：\n{context}\n\n请识别这个文档描述的商品/设备名称："

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        resp = llm.invoke(messages)
        item_name = getattr(resp, "content", "").strip()
        item_name = item_name.replace("\n", "").replace("\r", "").replace("\t", "")

        if not item_name:
            return file_title

        logger.info(f"LLM识别商品名称: {item_name}")
        return item_name

    except Exception as e:
        logger.error(f"LLM调用失败: {str(e)}")
        return file_title


def _step_4_update_chunks(state: ImportGraphState, chunks: List[Dict], item_name: str):
    """回填商品名称到状态和切片"""
    state["item_name"] = item_name
    for chunk in chunks:
        chunk["item_name"] = item_name
    state["chunks"] = chunks
    logger.info(f"商品名称回填完成: {item_name}")


def _step_5_save_to_milvus(state: ImportGraphState, file_title: str, item_name: str):
    """将商品名称及稠密向量保存到Milvus"""
    collection_name = milvus_config.ITEM_NAMES_COLLECTION

    try:
        client = get_milvus_client()

        # 集合不存在则创建
        if not client.has_collection(collection_name=collection_name):
            create_item_names_collection(client, collection_name, lm_config.EMBEDDING_DIM)

        # 生成稠密向量
        dense_vector = generate_embedding(item_name) if item_name else None

        # 幂等性处理：删除同名数据
        if item_name:
            client.load_collection(collection_name=collection_name)
            safe_item_name = escape_milvus_string(item_name)
            client.delete(collection_name=collection_name, filter=f'item_name=="{safe_item_name}"')

        # 插入数据
        data = {
            "file_title": file_title,
            "item_name": item_name,
        }
        if dense_vector is not None:
            data["dense_vector"] = dense_vector

        client.insert(collection_name=collection_name, data=[data])
        client.load_collection(collection_name=collection_name)
        logger.info(f"商品名称存入Milvus成功: {item_name}")

    except Exception as e:
        logger.error(f"商品名称存入Milvus失败: {str(e)}", exc_info=True)
