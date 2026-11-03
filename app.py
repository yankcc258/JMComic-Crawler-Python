"""
JMComic 本地网页版下载器（Gradio）

功能：
- 直接输入 JM 号（支持多个，逗号/换行/空格分隔）批量下载
- 按 tag 或关键词搜索，勾选后下载
- 使用 assets/option/option_batch_unified_png.yml 配置（统一文件夹 + PNG）

使用方法：
1. pip install gradio jmcomic zhconv
2. python app.py
3. 浏览器打开提示的本地地址（通常是 http://127.0.0.1:7860）
"""

import re
from pathlib import Path

import gradio as gr
import jmcomic
from jmcomic import create_option_by_file, download_album

# 默认使用之前添加的配置文件
OPTION_PATH = Path(__file__).parent / "assets" / "option" / "option_batch_unified_png.yml"

def get_option():
    if not OPTION_PATH.exists():
        raise FileNotFoundError(f"找不到配置文件：{OPTION_PATH}")
    return create_option_by_file(str(OPTION_PATH))

def parse_ids(text: str) -> list[str]:
    """从输入文本中提取所有数字 ID"""
    if not text or not text.strip():
        return []
    ids = re.findall(r"\d+", text)
    return list(dict.fromkeys(ids))  # 去重保持顺序

def download_by_ids(ids_text: str, progress=gr.Progress()) -> str:
    ids = parse_ids(ids_text)
    if not ids:
        return "没有解析到有效的 JM 号"

    try:
        option = get_option()
        progress(0, desc="准备下载...")
        result = download_album(ids, option)
        
        success = []
        failed = []
        if hasattr(result, "failed") and result.failed:
            failed = list(result.failed.keys())
            success = [i for i in ids if i not in failed]
        else:
            success = ids

        msg = f"下载完成！\n成功：{len(success)} 个\n失败：{len(failed)} 个"
        if failed:
            msg += f"\n失败 ID：{', '.join(failed)}"
        msg += f"\n\n保存位置参见配置文件 dir_rule.base_dir"
        return msg
    except Exception as e:
        return f"下载出错：{e}"

def search_by_tag(query: str, page: int = 1) -> list[tuple[str, str]]:
    """搜索 tag 或关键词，返回 (id, title) 列表"""
    if not query or not query.strip():
        return []
    
    try:
        option = get_option()
        client = option.new_jm_client()
        
        # 优先尝试按 tag 搜索，失败则用普通搜索
        try:
            page_result = client.search_tag(query.strip(), page=page)
        except Exception:
            page_result = client.search_site(search_query=query.strip(), page=page)
        
        results = []
        for aid, title in page_result.iter_id_title():
            results.append((aid, title))
        return results
    except Exception as e:
        return [("error", str(e))]

def search_and_show(query: str, page: int):
    results = search_by_tag(query, page)
    if not results:
        return gr.update(choices=[], value=[]), "没有搜到结果"
    if results[0][0] == "error":
        return gr.update(choices=[], value=[]), f"搜索出错：{results[0][1]}"
    
    choices = [f"{aid} | {title}" for aid, title in results]
    return gr.update(choices=choices, value=[]), f"找到 {len(results)} 个结果（第 {page} 页）"

def download_selected(selected: list[str], progress=gr.Progress()) -> str:
    if not selected:
        return "请先勾选要下载的本子"
    
    ids = []
    for item in selected:
        aid = item.split(" | ")[0].strip()
        if aid.isdigit():
            ids.append(aid)
    
    if not ids:
        return "没有有效的 ID"
    
    return download_by_ids("\n".join(ids), progress)

# ==================== Gradio 界面 ====================
with gr.Blocks(title="JMComic 下载器") as demo:
    gr.Markdown("# JMComic 本地下载器\n支持直接输入 JM 号，或按 tag/关键词搜索后下载")
    
    with gr.Tab("直接下载"):
        ids_input = gr.Textbox(
            label="JM 号（支持多个，用逗号、空格或换行分隔）",
            placeholder="例如：123456, 234567\n或直接换行贴多个",
            lines=6
        )
        download_btn = gr.Button("开始下载", variant="primary")
        download_output = gr.Textbox(label="结果", lines=8)
        download_btn.click(download_by_ids, inputs=ids_input, outputs=download_output)
    
    with gr.Tab("搜索下载"):
        with gr.Row():
            search_input = gr.Textbox(label="Tag 或关键词", placeholder="例如：無修正 或 MANA", scale=4)
            page_input = gr.Number(label="页码", value=1, minimum=1, precision=0, scale=1)
            search_btn = gr.Button("搜索", variant="secondary")
        
        search_status = gr.Textbox(label="搜索状态", interactive=False)
        results_check = gr.CheckboxGroup(label="搜索结果（勾选后下载）", choices=[])
        download_selected_btn = gr.Button("下载选中的本子", variant="primary")
        selected_output = gr.Textbox(label="下载结果", lines=6)
        
        search_btn.click(
            search_and_show,
            inputs=[search_input, page_input],
            outputs=[results_check, search_status]
        )
        download_selected_btn.click(
            download_selected,
            inputs=results_check,
            outputs=selected_output
        )
    
    gr.Markdown("""
    ---
    **使用提示**
    - 下载会使用 `assets/option/option_batch_unified_png.yml` 中的配置（统一文件夹 + 转 PNG）
    - 如需修改保存路径，直接编辑那个 yml 文件里的 `dir_rule.base_dir`
    - 搜索功能依赖网络，建议配好代理（如需）
    """)

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft()
    )
