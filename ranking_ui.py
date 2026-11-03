"""
排行榜浏览器（周榜/月榜/总榜 + 封面预览）
"""

import jmcomic
from jmcomic import JmMagicConstants

def get_cover_url(client, album_id: str) -> str:
    """获取封面 URL（失败返回空）"""
    try:
        album = client.get_album_detail(album_id)
        # 尝试拿封面
        if hasattr(album, "cover") and album.cover:
            return album.cover
        # 备用方式
        return f"https://cdn-msp.jmapiproxy1.cc/media/albums/{album_id}.jpg"
    except Exception:
        return ""

def fetch_ranking(mode: str, page: int = 1):
    """
    mode: 'week' | 'month' | 'all'
    返回 list of (id, title, views_or_info)
    """
    client = jmcomic.JmOption.default().new_jm_client()
    
    if mode == "week":
        page_result = client.week_ranking(page)
    elif mode == "month":
        page_result = client.month_ranking(page)
    else:  # all time by views
        page_result = client.categories_filter(
            page=page,
            time=JmMagicConstants.TIME_ALL,
            category=JmMagicConstants.CATEGORY_ALL,
            order_by=JmMagicConstants.ORDER_BY_VIEW,
        )
    
    items = []
    for aid, title in page_result.iter_id_title():
        items.append((str(aid), str(title)))
    return items

def get_preview_html(album_id: str, title: str, cover_url: str = "") -> str:
    """生成封面预览 HTML"""
    if not cover_url:
        cover_url = f"https://cdn-msp.jmapiproxy1.cc/media/albums/{album_id}.jpg"
    
    return f'''
    <div style="text-align:center; padding:12px;">
      <img src="{cover_url}" style="max-width:180px; max-height:240px; border-radius:8px; box-shadow:0 2px 8px #0002;" 
           onerror="this.style.display='none'" />
      <div style="margin-top:10px; font-size:13px; color:#333; font-weight:500;">{title}</div>
      <div style="font-size:11px; color:#888;">JM{album_id}</div>
    </div>
    '''
