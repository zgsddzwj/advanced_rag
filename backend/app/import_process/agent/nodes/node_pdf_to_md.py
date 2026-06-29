"""
PDF转Markdown节点
通过 MinerU 云端 API 将 PDF 解析为 Markdown
流程：路径校验 → 上传PDF → 轮询解析 → 下载ZIP → 解压提取MD
"""
import os
import sys
import time
import requests
import zipfile
import shutil
from pathlib import Path

from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.conf.mineru_config import mineru_config
from app.core.logger import logger

MINERU_BASE_URL = mineru_config.BASE_URL
MINERU_API_TOKEN = mineru_config.API_TOKEN


def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    """PDF转MD核心处理节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        pdf_path_obj, output_dir_obj = _step_1_validate_paths(state)
        zip_url = _step_2_upload_and_poll(pdf_path_obj, output_dir_obj)
        md_path = _step_3_download_and_extract(zip_url, output_dir_obj, pdf_path_obj.stem)

        state["md_path"] = md_path
        logger.info(f"MD文件生成成功，路径: {md_path}")

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                state["md_content"] = f.read()
            logger.info(f"MD文件内容读取成功，长度: {len(state['md_content'])} 字符")
        except Exception as e:
            logger.error(f"读取MD文件内容失败: {str(e)}")

    except Exception as e:
        logger.error(f"PDF转MD流程执行失败: {str(e)}", exc_info=True)
        raise
    finally:
        add_done_task(state["task_id"], func_name)

    return state


def _step_1_validate_paths(state: ImportGraphState):
    """校验PDF文件路径和输出目录"""
    pdf_path = state.get("pdf_path", "").strip()
    local_dir = state.get("local_dir", "").strip()

    if not pdf_path:
        raise ValueError(f"工作流状态缺失参数: pdf_path")
    if not local_dir:
        raise ValueError(f"工作流状态缺失参数: local_dir")

    pdf_path_obj = Path(pdf_path)
    output_dir_obj = Path(local_dir)

    if not pdf_path_obj.exists():
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path_obj.absolute()}")

    if not output_dir_obj.exists():
        output_dir_obj.mkdir(parents=True, exist_ok=True)

    return pdf_path_obj, output_dir_obj


def _step_2_upload_and_poll(pdf_path_obj: Path, output_dir_obj: Path) -> str:
    """上传PDF至MinerU并轮询解析结果"""
    if not MINERU_BASE_URL or not MINERU_API_TOKEN:
        raise ValueError("MinerU配置缺失：请在.env中配置 MINERU_BASE_URL 和 MINERU_API_TOKEN")

    request_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINERU_API_TOKEN}"
    }

    # 1. 获取上传链接和 batch_id
    url_get_upload = f"{MINERU_BASE_URL}/file-urls/batch"
    req_data = {
        "files": [{"name": pdf_path_obj.name}],
        "model_version": "vlm"
    }
    resp = requests.post(url=url_get_upload, headers=request_headers, json=req_data, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"获取上传链接失败，状态码: {resp.status_code}")

    resp_data = resp.json()
    if resp_data["code"] != 0:
        raise RuntimeError(f"获取上传链接API错误: {resp_data}")

    signed_url = resp_data["data"]["file_urls"][0]
    batch_id = resp_data["data"]["batch_id"]
    logger.info(f"获取上传链接成功，batch_id: {batch_id}")

    # 2. 上传文件
    with open(pdf_path_obj, "rb") as f:
        file_data = f.read()

    upload_session = requests.Session()
    upload_session.trust_env = False

    try:
        put_resp = upload_session.put(url=signed_url, data=file_data, timeout=60)
        if put_resp.status_code != 200:
            pdf_headers = {"Content-Type": "application/pdf"}
            put_resp = upload_session.put(url=signed_url, data=file_data, headers=pdf_headers, timeout=60)
            if put_resp.status_code != 200:
                raise RuntimeError(f"文件上传失败，状态码: {put_resp.status_code}")
        logger.info(f"文件上传成功: {pdf_path_obj.name}")
    finally:
        upload_session.close()

    # 3. 轮询任务状态
    poll_url = f"{MINERU_BASE_URL}/extract-results/batch/{batch_id}"
    start_time = time.time()
    timeout_seconds = 600
    poll_interval = 3

    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout_seconds:
            raise TimeoutError(f"任务超时({int(timeout_seconds)}s)，batch_id: {batch_id}")

        try:
            poll_resp = requests.get(url=poll_url, headers=request_headers, timeout=10)
        except Exception as e:
            logger.warning(f"轮询请求异常，{poll_interval}秒后重试: {str(e)}")
            time.sleep(poll_interval)
            continue

        if poll_resp.status_code != 200:
            if 500 <= poll_resp.status_code < 600:
                time.sleep(poll_interval)
                continue
            raise RuntimeError(f"轮询HTTP失败，状态码: {poll_resp.status_code}")

        poll_data = poll_resp.json()
        if poll_data["code"] != 0:
            raise RuntimeError(f"轮询API错误: {poll_data}")

        extract_results = poll_data["data"]["extract_result"]
        if not extract_results:
            time.sleep(poll_interval)
            continue

        result_item = extract_results[0]
        state_status = result_item["state"]

        if state_status == "done":
            logger.info(f"解析任务完成！总耗时: {int(elapsed_time)}s")
            full_zip_url = result_item.get("full_zip_url")
            if not full_zip_url:
                raise RuntimeError(f"任务完成但未返回ZIP下载链接")
            return full_zip_url
        elif state_status == "failed":
            err_msg = result_item.get("err_msg", "未知错误")
            raise RuntimeError(f"解析任务失败: {err_msg}")
        else:
            time.sleep(poll_interval)


def _step_3_download_and_extract(zip_url: str, output_dir_obj: Path, pdf_stem: str) -> str:
    """下载ZIP包并解压，提取目标MD文件"""
    # 1. 下载ZIP
    resp = requests.get(zip_url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"ZIP包下载失败，HTTP状态码: {resp.status_code}")

    zip_save_path = output_dir_obj / f"{pdf_stem}_result.zip"
    with open(zip_save_path, "wb") as f:
        f.write(resp.content)
    logger.info(f"ZIP包下载成功: {zip_save_path}")

    # 2. 解压
    extract_target_dir = output_dir_obj / pdf_stem
    if extract_target_dir.exists():
        try:
            shutil.rmtree(extract_target_dir)
        except Exception as e:
            logger.warning(f"清理旧目录失败: {str(e)}")
    extract_target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_save_path, 'r') as zip_file_obj:
        zip_file_obj.extractall(extract_target_dir)
    logger.info(f"ZIP包解压完成: {extract_target_dir}")

    # 3. 查找MD文件
    md_file_list = list(extract_target_dir.rglob("*.md"))
    if not md_file_list:
        raise FileNotFoundError(f"解压目录中未找到MD文件: {extract_target_dir}")

    # 4. 按优先级匹配目标MD文件
    target_md_file = None
    for md_file in md_file_list:
        if md_file.stem == pdf_stem:
            target_md_file = md_file
            break
    if not target_md_file:
        for md_file in md_file_list:
            if md_file.name.lower() == "full.md":
                target_md_file = md_file
                break
    if not target_md_file:
        target_md_file = md_file_list[0]

    # 重命名统一为PDF同名
    if target_md_file.stem != pdf_stem:
        new_md_path = target_md_file.with_name(f"{pdf_stem}.md")
        try:
            target_md_file.rename(new_md_path)
            target_md_file = new_md_path
        except OSError as e:
            logger.warning(f"MD文件重命名失败: {str(e)}")

    final_md_path = str(target_md_file.absolute())
    logger.info(f"MD文件处理完成: {final_md_path}")
    return final_md_path
