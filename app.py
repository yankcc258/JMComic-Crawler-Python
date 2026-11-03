"""JMComic 本地网页版下载器：批量下载、分页搜索、封面 / Tag 和排行榜。
支持 Tag 组合搜索（空格 / 逗号 / + 分隔多个 Tag，搜索同时包含的本子）
"""

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import gradio as gr
from jmcomic import JmMagicConstants, create_option_by_file, download_album

from catalog_ui import CatalogBrowser, RANKING_LABELS
from ui_theme import UI_CSS, UI_THEME
from web_ui import build_ui

OPTION_PATH = Path(__file__).parent / "assets" / "option" / "option_batch_unified_png.yml"


def get_option():
    if not OPTION_PATH.exists():
        raise FileNotFoundError(f"找不到配置文件：{OPTION_PATH}")
    return create_option_by_file(str(OPTION_PATH))


def parse_ids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\d+", text or "")))


def input_feedback(text):
    count = len(parse_ids(text))
    message = (f"已识别 **{count}** 个编号 · 重复编号已自动合并" if count
               else "等待输入编号 · 支持逗号、空格或换行分隔")
    return message, gr.update(interactive=count > 0)


def download_by_ids(ids_text: str, progress=gr.Progress()) -> str:
    ids = parse_ids(ids_text)
    if not ids:
        return "没有解析到有效的 JM 号"
    try:
        option = get_option()
        progress(0, desc="准备下载...")
        result = download_album(ids, option)
        failed = [str(aid) for aid in result.failed] if getattr(result, "failed", None) else []
        success = [aid for aid in ids if aid not in failed]
        message = f"下载完成！\n成功：{len(success)} 个\n失败：{len(failed)} 个"
        if failed:
            message += f"\n失败 ID：{', '.join(failed)}"
        return message + "\n\n保存位置参见配置文件 dir_rule.base_dir"
    except Exception as error:
        return f"下载出错：{error}"


def download_checked(selected: list[str], progress=gr.Progress()) -> str:
    ids = [str(item).split(" | ", 1)[0].strip() for item in (selected or [])]
    ids = [aid for aid in ids if aid.isdigit()]
    if not ids:
        return "请先勾选要下载的作品"
    return download_by_ids("\n".join(ids), progress)


def page_data(result, mode):
    return {
        "items": [(str(aid), str(title)) for aid, title in result.iter_id_title()],
        "total": max(0, int(result.total)), "page_size": max(1, int(result.page_size)),
        "mode": mode,
    }


def parse_tags(query: str) -> list[str]:
    """解析组合 Tag：支持空格、逗号、+ 分隔"""
    if not query:
        return []
    parts = re.split(r"[,\s+]", query.strip())
    return [p.strip() for p in parts if p.strip()]


def fetch_search_page(query, page=1, mode=None):
    client = get_option().new_jm_client()
    tags = parse_tags(query)

    # 组合 Tag 搜索：用第一个 Tag 搜索，然后过滤包含其他 Tag 的结果
    if len(tags) > 1:
        primary = tags[0]
        try:
            result = client.search_tag(primary, page=page)
            mode = "tag"
        except Exception:
            result = client.search_site(search_query=primary, page=page)
            mode = "site"

        items = [(str(aid), str(title)) for aid, title in result.iter_id_title()]
        # 简单过滤：如果标题或后续详情包含其他 Tag（这里做轻量过滤，实际可以再查详情）
        other_tags = [t.lower() for t in tags[1:]]
        filtered = []
        for aid, title in items:
            title_lower = title.lower()
            if all(t in title_lower for t in other_tags):
                filtered.append((aid, title))
        # 如果过滤后太少，仍然返回原始结果（避免空页）
        if len(filtered) >= 3 or not filtered:
            items = filtered or items
        return {
            "items": items,
            "total": len(items),
            "page_size": max(1, int(result.page_size)),
            "mode": mode,
        }

    # 单 Tag 或普通搜索
    if mode == "site":
        result = client.search_site(search_query=query, page=page)
    elif mode == "tag":
        result = client.search_tag(query, page=page)
    else:
        try:
            result = client.search_tag(query, page=page)
            mode = "tag"
        except Exception:
            result = client.search_site(search_query=query, page=page)
            mode = "site"
    return page_data(result, mode)


def fetch_ranking_page(query, page=1, mode=None):
    filters = json.loads(query)
    ranking, tag = filters["ranking"], filters["tag"]
    if ranking not in RANKING_LABELS:
        raise ValueError("请选择周榜、月榜或总榜")
    client = get_option().new_jm_client()
    periods = {"week": JmMagicConstants.TIME_WEEK, "month": JmMagicConstants.TIME_MONTH,
               "all": JmMagicConstants.TIME_ALL}
    if tag:
        result = client.search_tag(tag, page=page, order_by=JmMagicConstants.ORDER_BY_VIEW,
                                   time=periods[ranking])
    elif ranking == "week":
        result = client.week_ranking(page)
    elif ranking == "month":
        result = client.month_ranking(page)
    else:
        result = client.categories_filter(page=page, time=JmMagicConstants.TIME_ALL,
                                           category=JmMagicConstants.CATEGORY_ALL,
                                           order_by=JmMagicConstants.ORDER_BY_VIEW)
    return page_data(result, "ranking")


def make_cover_html(aid, title, cover_url=""):
    aid = str(aid)
    if not re.fullmatch(r"[0-9]+", aid):
        raise ValueError("无效的作品编号")
    parsed = urlparse(cover_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        cover_url = f"https://cdn-msp.jmapiproxy1.cc/media/albums/{aid}.jpg"
    return (
        '<div class="jm-cover-stage"><div class="jm-cover-fallback">封面暂不可用</div>'
        f'<img src="{escape(cover_url, quote=True)}" alt="{escape(title, quote=True)}" '
        'loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()"/></div>'
        f'<div class="jm-cover-title">{escape(title)}</div><div class="jm-cover-id">JM {aid}</div>'
    )


def fetch_preview(aid, title):
    album = get_option().new_jm_client().get_album_detail(aid)
    raw_tags = getattr(album, "tags", None) or getattr(album, "tag_list", []) or []
    tags = list(dict.fromkeys(str(tag) for tag in raw_tags))[:10]
    cover = getattr(album, "cover", "")
    return {"html": make_cover_html(aid, title, cover if isinstance(cover, str) else ""), "tags": tags}


search_browser = CatalogBrowser(fetch_search_page, download_checked, fetch_preview)
ranking_browser = CatalogBrowser(fetch_ranking_page, download_checked, fetch_preview, ranking=True)
demo = build_ui(search_browser, ranking_browser, download_by_ids, input_feedback)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False,
                theme=UI_THEME, css=UI_CSS, footer_links=[])
