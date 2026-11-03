"""Session-local search pagination and cross-page selection for the Gradio UI."""

from copy import deepcopy
from math import ceil

import gradio as gr

RESULTS_PER_PAGE = 6


def new_search_state():
    return {"query": "", "page": 0, "total": 0, "page_size": 80,
            "mode": None, "cache": {}, "selected": {}}


def visible_results(state):
    if not state["page"]:
        return []
    start = (state["page"] - 1) * RESULTS_PER_PAGE
    stop = min(start + RESULTS_PER_PAGE, state["total"])
    return [state["cache"][index // state["page_size"] + 1][index % state["page_size"]]
            for index in range(start, stop)]


def remember_selection(state, selected):
    updated = deepcopy(state)
    checked = set(selected or [])
    for aid, title in visible_results(state):
        if aid in checked:
            updated["selected"][aid] = title
        else:
            updated["selected"].pop(aid, None)
    return updated


def selection_feedback(state, busy=False):
    count = len(state["selected"])
    return (
        f"已选择 **{count}** 部作品 · 翻页后仍保留",
        gr.update(value=f"下载选中作品（{count}）" if count else "下载选中作品",
                  interactive=count > 0 and not busy),
        gr.update(interactive=count > 0 and not busy),
    )


class SearchBrowser:
    def __init__(self, fetch_page, download, empty_view):
        self.fetch_page = fetch_page
        self.download = download
        self.empty_view = empty_view

    def load_page(self, state, page):
        """Split source pages into six-item UI pages, including source boundaries."""
        updated = deepcopy(state)
        pages = ceil(updated["total"] / RESULTS_PER_PAGE)
        if not pages:
            return updated
        page = min(max(1, page), pages)
        start = (page - 1) * RESULTS_PER_PAGE
        stop = min(start + RESULTS_PER_PAGE, updated["total"])
        for index in range(start, stop):
            source_page, offset = divmod(index, updated["page_size"])
            source_page += 1
            if source_page not in updated["cache"]:
                data = self.fetch_page(updated["query"], source_page, updated["mode"])
                updated["cache"][source_page] = data["items"]
            if offset >= len(updated["cache"][source_page]):
                raise ValueError("搜索结果已变化，请重新搜索后再试")
        updated["page"] = page
        return updated

    def view(self, state, status=None, busy=False):
        items = visible_results(state)
        pages = ceil(state["total"] / RESULTS_PER_PAGE)
        start = (state["page"] - 1) * RESULTS_PER_PAGE + 1
        if status is None:
            status = (f"共 {state['total']} 部作品 · 正在浏览 {start}–{start + len(items) - 1} 项"
                      if items else "没有找到相关作品，试试其他关键词")
        empty = (self.empty_view("没有找到相关作品", "试试其他关键词，开始新的一页")
                 if state["query"] else self.empty_view("等待发现好作品", "输入关键词，每页浏览 6 部作品"))
        count, download, clear = selection_feedback(state, busy)
        page_label = (
            f'<div class="jm-page-count" aria-live="polite"><strong>第 {state["page"]} 页'
            f'<span> / 共 {pages} 页</span></strong><small>每页 {RESULTS_PER_PAGE} 项</small></div>'
            if pages else '<div class="jm-page-count"><strong>等待搜索</strong><small>每页 6 项</small></div>'
        )
        return (
            state,
            gr.update(choices=[(f"{title}\nJM {aid}", aid) for aid, title in items],
                      value=[aid for aid, _ in items if aid in state["selected"]],
                      visible=bool(items), interactive=not busy,
                      elem_classes=[f"jm-page-{state['page'] % 2}"]),
            status, gr.update(value=empty, visible=not items), page_label,
            gr.update(interactive=state["page"] > 1 and not busy),
            gr.update(interactive=state["page"] < pages and not busy),
            count, download, clear, gr.update(interactive=not busy),
            gr.update(interactive=not busy),
            gr.update(value=str(state["page"]) if pages else "",
                      placeholder=f"1–{pages}" if pages else "页码",
                      interactive=pages > 0 and not busy),
            gr.update(interactive=pages > 0 and not busy),
        )

    def browse(self, query, state, selected, direction=0):
        previous = remember_selection(state, selected)
        query = (query or "").strip()
        if direction == 0 and not query:
            yield self.view(previous, "请输入 Tag 或关键词后搜索")
            return
        yield self.view(previous, "正在翻页…" if direction else "正在搜索…", busy=True)
        try:
            if direction:
                updated = self.load_page(previous, previous["page"] + direction)
            else:
                data = self.fetch_page(query)
                updated = new_search_state()
                updated.update(query=query, total=data["total"], page_size=data["page_size"],
                               mode=data["mode"], cache={1: data["items"]})
                updated = self.load_page(updated, 1)
            yield self.view(updated)
        except Exception as error:
            action = "翻页" if direction else "搜索"
            yield self.view(previous, f"{action}失败：{error}。可重试，原有结果与勾选已保留。")

    def search(self, query, state, selected):
        yield from self.browse(query, state, selected)

    def previous(self, query, state, selected):
        yield from self.browse(query, state, selected, -1)

    def next(self, query, state, selected):
        yield from self.browse(query, state, selected, 1)

    def jump(self, page, state, selected):
        previous = remember_selection(state, selected)
        pages = ceil(previous["total"] / RESULTS_PER_PAGE)
        if not pages:
            yield self.view(previous, "请先搜索作品，再输入页码跳转")
            return
        text = str(page or "").strip()
        try:
            target = int(text) if text.isdecimal() else 0
        except ValueError:
            target = 0
        if not 1 <= target <= pages:
            yield self.view(previous, f"请输入 1–{pages} 之间的整数页码，当前页面与勾选已保留")
            return
        if target == previous["page"]:
            yield self.view(previous)
            return
        yield self.view(previous, f"正在跳转到第 {target} 页…", busy=True)
        try:
            yield self.view(self.load_page(previous, target))
        except Exception as error:
            yield self.view(previous, f"跳转失败：{error}。可重试，原有结果与勾选已保留。")

    def select(self, selected, state):
        updated = remember_selection(state, selected)
        return updated, *selection_feedback(updated)

    def clear(self, state):
        updated = deepcopy(state)
        updated["selected"] = {}
        return updated, [], *selection_feedback(updated)

    def download_selected(self, selected, state, progress=gr.Progress()):
        updated = remember_selection(state, selected)
        return self.download(list(updated["selected"]), progress)
