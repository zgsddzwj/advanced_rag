"""
MD文件图片处理节点
流程：扫描图片 → VLM生成摘要 → 上传MinIO → 替换MD链接 → 备份新MD
"""
import os
import re
import sys
import base64
from pathlib import Path
from typing import Dict, List, Tuple

from app.clients.minio_utils import get_minio_client
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task
from app.lm.vlm_utils import get_vlm_client
from langchain_core.messages import HumanMessage
from app.core.logger import logger

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def node_md_img(state: ImportGraphState) -> ImportGraphState:
    """MD文件图片处理核心节点"""
    func_name = sys._getframe().f_code.co_name
    logger.info(f">>> 执行节点: {func_name}")
    add_running_task(state["task_id"], func_name)

    try:
        # 步骤1：获取MD内容和路径
        md_content, path_obj, images_dir = _step_1_get_content(state)
        state["md_content"] = md_content

        if not images_dir.exists():
            logger.info(f"图片文件夹不存在，跳过图片处理: {images_dir}")
            return state

        # 步骤2：扫描并筛选MD中引用的图片
        targets = _step_2_scan_images(md_content, images_dir)
        if not targets:
            logger.info("未检测到MD中引用的支持格式图片，跳过处理")
            return state

        # 步骤3：调用VLM生成图片摘要
        summaries = _step_3_generate_summaries(path_obj.stem, targets)

        # 步骤4：上传图片至MinIO，替换MD图片路径
        new_md_content = _step_4_upload_and_replace(path_obj.stem, targets, summaries, md_content)
        state["md_content"] = new_md_content

        # 步骤5：保存新MD文件
        new_md_file_name = _step_5_backup_new_md_file(state['md_path'], new_md_content)
        state["md_path"] = new_md_file_name
        logger.info(f"MD图片处理完成，新文件: {new_md_file_name}")

    except Exception as e:
        logger.error(f"MD图片处理失败: {str(e)}", exc_info=True)
    finally:
        add_done_task(state["task_id"], func_name)

    return state


def _step_1_get_content(state: ImportGraphState) -> Tuple[str, Path, Path]:
    """获取MD内容、文件路径、图片文件夹路径"""
    md_file_path = state["md_path"]
    if not md_file_path:
        raise FileNotFoundError(f"状态中无有效MD文件路径: {state.get('md_path')}")

    path_obj = Path(md_file_path)
    if not state.get("md_content"):
        with open(path_obj, "r", encoding="utf-8") as f:
            md_content = f.read()
    else:
        md_content = state["md_content"]

    images_dir = path_obj.parent / "images"
    return md_content, path_obj, images_dir


def _is_supported_image(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def _find_image_in_md(md_content: str, image_filename: str, context_len: int = 100) -> List[Tuple[str, str]]:
    pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_filename) + r".*?\)")
    results = []
    for m in pattern.finditer(md_content):
        start, end = m.span()
        pre_text = md_content[max(0, start - context_len):start]
        post_text = md_content[end:min(len(md_content), end + context_len)]
        results.append((pre_text, post_text))
    return results


def _step_2_scan_images(md_content: str, images_dir: Path) -> List[Tuple[str, str, Tuple[str, str]]]:
    """扫描图片文件夹，筛选MD中实际引用的支持格式图片"""
    targets = []
    for image_file in os.listdir(images_dir):
        if not _is_supported_image(image_file):
            continue
        img_path = str(images_dir / image_file)
        context_list = _find_image_in_md(md_content, image_file)
        if not context_list:
            logger.warning(f"图片未在MD中引用，跳过: {image_file}")
            continue
        targets.append((image_file, img_path, context_list[0]))
        logger.info(f"图片加入待处理列表: {image_file}")

    logger.info(f"图片扫描完成，共筛选出待处理图片: {len(targets)} 张")
    return targets


def _encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def _summarize_image(image_path: str, root_folder: str, image_content: Tuple[str, str]) -> str:
    """调用VLM生成图片内容摘要"""
    base64_image = _encode_image_to_base64(image_path)
    try:
        vlm = get_vlm_client()
        prompt_text = (
            f"这是「{root_folder}」文件中的一张图片，"
            f"图片上文部分为「{image_content[0]}」，"
            f"下文部分为「{image_content[1]}」，"
            f"请用中文简要总结这张图片的内容，用于Markdown图片标题，控制在50字以内。"
        )
        messages = [HumanMessage(content=[
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ])]
        response = vlm.invoke(messages)
        summary = response.content.strip().replace("\n", "")
        logger.info(f"图片摘要生成成功: {image_path} → {summary}")
        return summary
    except Exception as e:
        logger.error(f"图片摘要生成失败: {image_path}，错误: {str(e)}")
        return "图片描述"


def _step_3_generate_summaries(doc_stem: str, targets: List[Tuple[str, str, Tuple[str, str]]]) -> Dict[str, str]:
    """批量为待处理图片生成内容摘要"""
    summaries = {}
    for img_file, image_path, context in targets:
        import time
        time.sleep(0.5)  # 简单限速，避免API限流
        summaries[img_file] = _summarize_image(image_path, root_folder=doc_stem, image_content=context)
    logger.info(f"图片摘要批量生成完成，共处理 {len(summaries)} 张图片")
    return summaries


def _step_4_upload_and_replace(doc_stem: str, targets, summaries: Dict[str, str], md_content: str) -> str:
    """上传图片至MinIO，替换MD图片路径"""
    from app.clients.minio_utils import upload_file

    img_dir = os.getenv("MINIO_IMG_DIR", "images")
    upload_dir = f"{img_dir}/{doc_stem}".replace(" ", "")

    # 上传图片并获取URL映射
    urls = {}
    for img_file, img_path, _ in targets:
        object_name = f"{upload_dir}/{img_file}"
        try:
            img_url = upload_file(img_path, object_name, f"image/{os.path.splitext(img_file)[1][1:]}")
            urls[img_file] = img_url
        except Exception as e:
            logger.error(f"图片上传MinIO失败: {img_file}，错误: {str(e)}")

    # 合并摘要和URL
    image_info = {}
    for image_file, summary in summaries.items():
        if url := urls.get(image_file):
            image_info[image_file] = (summary, url)

    # 替换MD内容中的本地图片引用
    for img_filename, (summary, new_url) in image_info.items():
        pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(img_filename) + r".*?\)", re.IGNORECASE)
        md_content = pattern.sub(f"![{summary}]({new_url})", md_content)

    logger.info(f"MD图片引用替换完成，共替换 {len(image_info)} 处")
    return md_content


def _step_5_backup_new_md_file(origin_md_path: str, md_content: str) -> str:
    """将处理后的MD内容保存为新文件"""
    new_md_file_name = os.path.splitext(origin_md_path)[0] + "_new.md"
    with open(new_md_file_name, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"处理后MD文件已保存: {new_md_file_name}")
    return new_md_file_name
