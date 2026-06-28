"""导入流程图状态定义"""
import copy
from typing import TypedDict


class ImportGraphState(TypedDict):
    """导入图状态，所有节点共享"""
    task_id: str

    # 流程控制标记
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool

    # 路径相关
    local_dir: str
    local_file_path: str
    file_title: str
    pdf_path: str
    md_path: str
    split_path: str
    embeddings_path: str

    # 内容数据
    md_content: str
    chunks: list
    item_name: str

    # 向量数据
    embeddings_content: list


graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "local_dir": "",
    "local_file_path": "",
    "pdf_path": "",
    "md_path": "",
    "file_title": "",
    "split_path": "",
    "embeddings_path": "",
    "md_content": "",
    "chunks": [],
    "item_name": "",
    "embeddings_content": []
}


def create_default_state(**overrides) -> ImportGraphState:
    """创建默认状态，支持覆盖"""
    state = copy.deepcopy(graph_default_state)
    state.update(overrides)
    return state


def get_default_state() -> ImportGraphState:
    """返回新的状态实例"""
    return copy.deepcopy(graph_default_state)
