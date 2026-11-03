"""
JMComic 本地网页版下载器（Gradio）

功能：
- 直接输入 JM 号批量下载
- 按 tag/关键词搜索下载
- 排行榜（周榜/月榜/总榜）+ 封面预览
- 使用 option_batch_unified_png.yml 配置
"""

import re
from pathlib import Path

import gradio as gr
import jmcomic
from jmcomic import create_option_by_file, download_album, JmMagicConstants

OPTION_PATH = Path(__file__).parent / "assets" / "option" / "option_batch_unified_png.yml"

def get_option():
    if not OPTION_PATH.exists():
        raise FileNotFoundError(f"找不到配置文件：{OPTION_PATH}")
    return create_option_by_file(str(OPTION_PATH))

def parse_ids(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    ids = re.findall(r"\d+", text)
    return list(dict.fromkeys(ids))

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
        msg += "\n\n保存位置参见配置文件 dir_rule.base_dir"
        return msg
    except Exception as e:
        return f"下载出错：{e}"

def search_by_tag(query: str, page: int = 1):
    if not query or not query.strip():
        return []
    try:
        option = get_option()
        client = option.new_jm_client()
        try:
            page_result = client.search_tag(query.strip(), page=page)
        except Exception:
            page_result = client.search_site(search_query=query.strip(), page=page)
        return [(aid, title) for aid, title in page_result.iter_id_title()]
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

# ==================== 排行榜 ====================
def fetch_ranking(mode: str, page: int = 1):
    client = get_option().new_jm_client()
    if mode == "week":
        page_result = client.week_ranking(page)
    elif mode == "month":
        page_result = client.month_ranking(page)
    else:
        page_result = client.categories_filter(
            page=page,
            time=JmMagicConstants.TIME_ALL,
            category=JmMagicConstants.CATEGORY_ALL,
            order_by=JmMagicConstants.ORDER_BY_VIEW,
        )
    return [(str(aid), str(title)) for aid, title in page_result.iter_id_title()]

def show_ranking(mode: str, page: int):
    try:
        items = fetch_ranking(mode, int(page))
        if not items:
            return gr.update(choices=[], value=[]), "没有数据", ""
        choices = [f"{aid} | {title}" for aid, title in items]
        return gr.update(choices=choices, value=[]), f"{mode} 榜 第 {page} 页，共 {len(items)} 个", ""
    except Exception as e:
        return gr.update(choices=[], value=[]), f"加载失败：{e}", ""

def preview_cover(selected: list[str]):
    if not selected:
        return "<div style='color:#888;text-align:center;padding:40px;'>勾选一个查看封面</div>"
    item = selected[0]
    aid = item.split(" | ")[0].strip()
    title = item.split(" | ")[1].strip() if " | " in item else ""
    cover = f"https://cdn-msp.jmapiproxy1.cc/media/albums/{aid}.jpg"
    return f'''
    <div style="text-align:center;padding:16px;">
      <img src="{cover}" style="max-width:200px;max-height:280px;border-radius:10px;box-shadow:0 4px 12px #0003;"
           onerror="this.style.display='none'"/>
      <div style="margin-top:12px;font-size:14px;font-weight:500;color:#223239;">{title}</div>
      <div style="font-size:12px;color:#888;margin-top:4px;">JM{aid}</div>
    </div>
    '''

# ==================== 界面 ====================
with gr.Blocks(title="JMComic 下载器") as demo:
    gr.Markdown("# JMComic 本地下载器\n输入 JM 号、搜索、或浏览排行榜")

    with gr.Tab("直接下载"):
        ids_input = gr.Textbox(label="JM 号（多个用逗号/空格/换行分隔）", lines=5, placeholder="123456, 234567")
        download_btn = gr.Button("开始下载", variant="primary")
        download_output = gr.Textbox(label="结果", lines=6)
        download_btn.click(download_by_ids, inputs=ids_input, outputs=download_output)

    with gr.Tab("搜索下载"):
        with gr.Row():
            search_input = gr.Textbox(label="Tag 或关键词", scale=4)
            page_input = gr.Number(label="页码", value=1, minimum=1, precision=0, scale=1)
            search_btn = gr.Button("搜索")
        search_status = gr.Textbox(label="状态", interactive=False)
        results_check = gr.CheckboxGroup(label="结果", choices=[])
        download_selected_btn = gr.Button("下载选中", variant="primary")
        selected_output = gr.Textbox(label="下载结果", lines=4)
        search_btn.click(search_and_show, inputs=[search_input, page_input], outputs=[results_check, search_status])
        download_selected_btn.click(download_selected, inputs=results_check, outputs=selected_output)

    with gr.Tab("排行榜"):
        with gr.Row():
            rank_mode = gr.Radio(["week", "month", "all"], value="week", label="榜单类型", scale=2)
            rank_page = gr.Number(value=1, minimum=1, precision=0, label="页码", scale=1)
            rank_btn = gr.Button("加载排行榜", variant="primary", scale=1)
        rank_status = gr.Textbox(label="状态", interactive=False)
        with gr.Row():
            rank_list = gr.CheckboxGroup(label="排行榜作品", choices=[], scale=3)
            cover_preview = gr.HTML("<div style='color:#888;text-align:center;padding:40px;'>勾选一个查看封面</div>", scale=2)
        rank_download_btn = gr.Button("下载选中的本子", variant="primary")
        rank_output = gr.Textbox(label="下载结果", lines=4)

        rank_btn.click(show_ranking, inputs=[rank_mode, rank_page], outputs=[rank_list, rank_status, cover_preview])
        rank_list.change(preview_cover, inputs=rank_list, outputs=cover_preview)
        rank_download_btn.click(download_selected, inputs=rank_list, outputs=rank_output)

    gr.Markdown("""
    ---
    - 下载使用 `assets/option/option_batch_unified_png.yml`（统一文件夹 + PNG）
    - 排行榜按观看数排序，支持周榜 / 月榜 / 总榜
    - 封面预览依赖网络
    """)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, theme=gr.themes.Soft())
