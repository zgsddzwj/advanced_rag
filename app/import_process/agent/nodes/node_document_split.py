"""
文档切分节点
基于Markdown标题层级递归切分，超长段落二次切分，过短段落合并
"""
import re
import json
import os
import sys
from typing import List, Dict, Any, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.task_utils import add_running_task, add_done_task
from app.import_process.agent.state import ImportGraphState
from app.core.logger import logger

# 配置参数
DEFAULT_MAX_CONTENT_LENGTH = 2000
MIN_CONTENT_LENGTH = 500


def node_document_split(state: ImportGraphState) -> ImportGraphState:
    """文档切分主节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        content, file_title, max_len = _step_1_get_inputs(state)
        if content is None:
            return state

        sections, title_count, lines_count = _step_2_split_by_titles(content, file_title)
        sections = _step_3_handle_no_title(content, sections, title_count, file_title)
        sections = _step_4_refine_chunks(sections, max_len)
        _step_5_print_stats(lines_count, sections)

        state["chunks"] = sections
        _step_6_backup(state, sections)

        logger.info(f"文档切分完成，生成 {len(sections)} 个Chunk")

    except Exception as e:
        logger.error(f"文档切分失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state


def _step_1_get_inputs(state: ImportGraphState) -> Tuple[Any, str, int]:
    """获取并预处理输入数据"""
    content = state.get("md_content")
    if not content:
        logger.warning("状态字典中无有效MD内容，终止文档切分")
        return None, None, None

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    file_title = state.get("file_title", "Unknown File")
    max_len = DEFAULT_MAX_CONTENT_LENGTH
    logger.info(f"输入数据加载完成，文件标题: {file_title}，最大Chunk长度: {max_len}")
    return content, file_title, max_len


def _step_2_split_by_titles(content: str, file_title: str) -> Tuple[List[Dict[str, Any]], int, int]:
    """按Markdown标题初次切分"""
    title_pattern = r'^\s*#{1,6}\s+.+'
    lines = content.split("\n")
    sections = []
    current_title = ""
    current_lines = []
    title_count = 0
    in_code_block = False

    def _flush_section():
        if not current_lines:
            return
        sections.append({
            "title": current_title,
            "content": "\n".join(current_lines),
            "file_title": file_title,
        })

    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("```") or stripped_line.startswith("~~~"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        is_valid_title = (not in_code_block) and re.match(title_pattern, line)
        if is_valid_title:
            _flush_section()
            current_title = line.strip()
            current_lines = [current_title]
            title_count += 1
        else:
            current_lines.append(line)

    _flush_section()
    logger.info(f"MD标题切分完成，识别到 {title_count} 个有效标题，共 {len(lines)} 行")
    return sections, title_count, len(lines)


def _step_3_handle_no_title(content, sections, title_count, file_title):
    """无标题兜底处理"""
    if title_count == 0:
        logger.warning(f"未识别到任何MD标题，将全文作为单个章节处理")
        return [{"title": "无标题", "content": content, "file_title": file_title}]
    return sections


def _split_long_section(section: Dict[str, Any], max_length: int = DEFAULT_MAX_CONTENT_LENGTH) -> List[Dict[str, Any]]:
    """超长章节二次切分"""
    content = section.get("content", "") or ""
    if len(content) <= max_length:
        return [section]

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    title = section.get("title", "") or ""
    prefix = f"{title}\n\n" if title else ""
    available_len = max_length - len(prefix)
    if available_len <= 0:
        return [section]

    body = content
    if title and body.lstrip().startswith(title):
        body = body[body.find(title) + len(title):].lstrip()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=available_len,
        chunk_overlap=0,
        separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
    )

    sub_sections = []
    for idx, chunk in enumerate(splitter.split_text(body), start=1):
        text = chunk.strip()
        if not text:
            continue
        full_text = (prefix + text).strip()
        sub_sections.append({
            "title": f"{title}-{idx}" if title else f"chunk-{idx}",
            "content": full_text,
            "parent_title": title,
            "part": idx,
            "file_title": section.get("file_title"),
        })

    return sub_sections


def _merge_short_sections(sections: List[Dict[str, Any]], min_length: int = MIN_CONTENT_LENGTH) -> List[Dict[str, Any]]:
    """过短章节合并"""
    if not sections:
        return []

    merged_sections = []
    current_chunk = None

    for sec in sections:
        if current_chunk is None:
            current_chunk = sec
            continue

        is_current_short = len(current_chunk["content"]) < min_length
        is_same_parent = current_chunk.get("parent_title") == sec.get("parent_title")

        if is_current_short and is_same_parent:
            parent_title = sec.get("parent_title", "")
            next_content = sec["content"]
            if parent_title and next_content.startswith(parent_title):
                next_content = next_content[len(parent_title):].lstrip()
            current_chunk["content"] += "\n\n" + next_content
            if "part" in sec:
                current_chunk["part"] = sec["part"]
        else:
            merged_sections.append(current_chunk)
            current_chunk = sec

    if current_chunk is not None:
        merged_sections.append(current_chunk)

    return merged_sections


def _step_4_refine_chunks(sections: List[Dict[str, Any]], max_len: int) -> List[Dict[str, Any]]:
    """Chunk精细化处理：长切短合"""
    if not max_len or max_len <= 0:
        return sections

    refined_split = []
    for sec in sections:
        refined_split.extend(_split_long_section(sec, max_len))
    logger.info(f"超长章节切分完成，共生成 {len(refined_split)} 个子Chunk")

    final_sections = _merge_short_sections(refined_split)
    logger.info(f"过短章节合并完成，最终 {len(final_sections)} 个Chunk")

    for sec in final_sections:
        if not isinstance(sec, dict):
            continue
        if "part" not in sec:
            sec["part"] = 0
        if not sec.get("parent_title"):
            sec["parent_title"] = sec.get("title") or ""

    return final_sections


def _step_5_print_stats(lines_count: int, sections: List[Dict[str, Any]]) -> None:
    """输出统计信息"""
    logger.info("-" * 50 + " 文档切分统计 " + "-" * 50)
    logger.info(f"MD原始文本总行数: {lines_count}")
    logger.info(f"最终生成Chunk数量: {len(sections)}")
    if sections:
        logger.info(f"首个Chunk标题预览: {sections[0].get('title', '无标题')}")
    logger.info("-" * 113)


def _step_6_backup(state: ImportGraphState, sections: List[Dict[str, Any]]) -> None:
    """Chunk结果本地JSON备份"""
    local_dir = state.get("local_dir")
    if not local_dir:
        return

    try:
        os.makedirs(local_dir, exist_ok=True)
        backup_path = os.path.join(local_dir, "chunks.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(sections, f, ensure_ascii=False, indent=2)
        logger.info(f"Chunk结果备份成功: {backup_path}")
    except Exception as e:
        logger.error(f"Chunk结果备份失败: {str(e)}")
