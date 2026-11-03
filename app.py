"""
JMComic 本地网页版下载器（Gradio）
支持：直接下载、搜索下载、排行榜（周/月/总）+ 封面预览
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
    return list(dict.fromkeys(re.findall(r"\d+", text)))

def download_by_ids(ids_text: str, progress=gr.Progress()) -> str:
    ids = parse_ids(ids_text)
    if not ids:
        return "没有解析到有效的 JM 号"
    try:
        option = get_option()
        progress(0, desc="准备下载...")
        result = download_album(ids, option)
        failed = list(result.failed.keys()) if hasattr(result, "failed") and result.failed else []
        success = [i for i in ids if i not in failed]
        msg = f"下载完成！\n成功：{len(success)} 个\n失败：{len(failed)} 个"
        if failed:
            msg += f"\n失败 ID：{', '.join(failed)}"
        msg += "\n\n保存位置参见配置文件 dir_rule.base_dir"
        return msg
    except Exception as e:
        return f"下载出错：{e}"

# ==================== 搜索 ====================
def do_search(query: str, page: int):
    if not query or not query.strip():
        return gr.update(choices=[], value=[]), "请输入关键词"
    try:
        client = get_option().new_jm_client()
        try:
            result = client.search_tag(query.strip(), page=int(page))
        except Exception:
            result = client.search_site(search_query=query.strip(), page=int(page))
        items = [(str(aid), str(title)) for aid, title in result.iter_id_title()]
        if not items:
            return gr.update(choices=[], value=[]), "没有搜到结果"
        choices = [f"{aid} | {title}" for aid, title in items]
        return gr.update(choices=choices, value=[]), f"第 {page} 页，找到 {len(items)} 个"
    except Exception as e:
        return gr.update(choices=[], value=[]), f"搜索出错：{e}"

def download_checked(selected: list[str], progress=gr.Progress()) -> str:
    if not selected:
        return "请先勾选"
    ids = [s.split(" | ")[0].strip() for s in selected if s.split(" | ")[0].strip().isdigit()]
    if not ids:
        return "没有有效 ID"
    return download_by_ids("\n".join(ids), progress)

# ==================== 排行榜 ====================
def load_ranking(mode: str, page: int):
    try:
        client = get_option().new_jm_client()
        if mode == "week":
            result = client.week_ranking(int(page))
        elif mode == "month":
            result = client.month_ranking(int(page))
        else:
            result = client.categories_filter(
                page=int(page),
                time=JmMagicConstants.TIME_ALL,
                category=JmMagicConstants.CATEGORY_ALL,
                order_by=JmMagicConstants.ORDER_BY_VIEW,
            )
        items = [(str(aid), str(title)) for aid, title in result.iter_id_title()]
        if not items:
            return gr.update(choices=[], value=[]), "没有数据", "<div style='color:#888;text-align:center;padding:40px;'>暂无数据</div>"
        choices = [f"{aid} | {title}" for aid, title in items]
        return (
            gr.update(choices=choices, value=[]),
            f"{mode} 榜 第 {page} 页，共 {len(items)} 个",
            "<div style='color:#888;text-align:center;padding:40px;'>勾选一个查看封面</div>",
        )
    except Exception as e:
        return gr.update(choices=[], value=[]), f"加载失败：{e}", ""

def show_cover(selected: list[str]):
    if not selected:
        return "<div style='color:#888;text-align:center;padding:40px;'>勾选一个查看封面</div>"
    item = selected[0]
    parts = item.split(" | ")
    aid = parts[0].strip()
    title = parts[1].strip() if len(parts) > 1 else ""
    cover = f"https://cdn-msp.jmapiproxy1.cc/media/albums/{aid}.jpg"
    return f'''
    <div style="text-align:center;padding:12px;">
      <img src="{cover}" style="max-width:180px;max-height:240px;border-radius:8px;box-shadow:0 2px 8px #0002;"
           onerror="this.style.display='none'"/>
      <div style="margin-top:8px;font-size:13px;font-weight:500;">{title}</div>
      <div style="font-size:11px;color:#888;">JM{aid}</div>
    </div>
    '''

# ==================== 界面 ====================
with gr.Blocks(title="JMComic 下载器") as demo:
    gr.Markdown("# JMComic 本地下载器\n直接下载 · 搜索 · 排行榜")

    with gr.Tab("直接下载"):
        ids_box = gr.Textbox(label="JM 号（多个用逗号/空格/换行分隔）", lines=5, placeholder="123456, 234567")
        dl_btn = gr.Button("开始下载", variant="primary")
        dl_out = gr.Textbox(label="结果", lines=6)
        dl_btn.click(download_by_ids, inputs=ids_box, outputs=dl_out)

    with gr.Tab("搜索下载"):
        with gr.Row():
            q_box = gr.Textbox(label="Tag 或关键词", scale=4)
            p_box = gr.Number(label="页码", value=1, minimum=1, precision=0, scale=1)
            s_btn = gr.Button("搜索", variant="primary")
        s_status = gr.Textbox(label="状态", interactive=False)
        s_list = gr.CheckboxGroup(label="结果（勾选后下载）", choices=[])
        s_dl = gr.Button("下载选中", variant="primary")
        s_out = gr.Textbox(label="下载结果", lines=4)
        s_btn.click(do_search, inputs=[q_box, p_box], outputs=[s_list, s_status])
        s_dl.click(download_checked, inputs=s_list, outputs=s_out)

    with gr.Tab("排行榜"):
        with gr.Row():
            r_mode = gr.Radio(["week", "month", "all"], value="week", label="榜单")
            r_page = gr.Number(value=1, minimum=1, precision=0, label="页码")
            r_btn = gr.Button("加载", variant="primary")
        r_status = gr.Textbox(label="状态", interactive=False)
        with gr.Row():
            r_list = gr.CheckboxGroup(label="作品", choices=[], scale=3)
            r_cover = gr.HTML("<div style='color:#888;text-align:center;padding:40px;'>勾选一个查看封面</div>", scale=2)
        r_dl = gr.Button("下载选中", variant="primary")
        r_out = gr.Textbox(label="下载结果", lines=4)
        r_btn.click(load_ranking, inputs=[r_mode, r_page], outputs=[r_list, r_status, r_cover])
        r_list.change(show_cover, inputs=r_list, outputs=r_cover)
        r_dl.click(download_checked, inputs=r_list, outputs=r_out)

    gr.Markdown("""
    ---
    - 下载使用 `assets/option/option_batch_unified_png.yml`（统一文件夹 + PNG）
    - 排行榜：week=周榜，month=月榜，all=总榜（按观看数）
    """)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, theme=gr.themes.Soft())
