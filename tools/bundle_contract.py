"""Фейл-клоуз контракт інлайнування CSS у переносних збірках ПБТ."""

from collections.abc import Callable
from html import escape
import re


def offline_source(html: str) -> str:
    """Вилучає розмітку чату, який потребує живого API."""
    return re.sub(r'[ \t]*<!-- live-support:start -->.*?<!-- live-support:end -->\n?',
                  '', html, flags=re.S)


def fit_video_budget(assemble: Callable[[list[str]], str], candidates: list[str],
                     limit: int) -> tuple[str, list[str]]:
    """Drop lowest-priority clips until the UTF-8 page fits, including its posters."""
    videos = list(candidates)
    while True:
        page = assemble(videos)
        if len(page.encode("utf-8")) <= limit:
            return page, videos
        if not videos:
            raise ValueError("Poster-only bundle exceeds the byte budget")
        videos.pop()


def inline_css(html: str, sources: tuple[tuple[str, str], ...]) -> str:
    """Інлайнує рівно один очікуваний stylesheet у вихідному порядку.

    Помилка в разі пропущеного, повтореного чи невідомого CSS-посилання:
    офлайн-збірка не може непомітно втрачати оформлення.
    """
    for href, css in sources:
        tag = f'<link rel="stylesheet" href="{href}">'
        n = html.count(tag)
        if n != 1:
            raise ValueError(f"Очікується один {href}; знайдено {n}")
        html = html.replace(tag, "<style>" + css + "</style>")

    if re.search(r"<link\b[^>]*\brel=[\"']stylesheet[\"']", html, re.I):
        raise ValueError("У збірці лишилося зовнішнє CSS-посилання")
    return html


def emit_fragment(title: str, head_items: list[str], prepaint: str, body: str) -> str:
    """Keep theme restoration ahead of CSS in both portable HTML fragments."""
    if not prepaint.lstrip().startswith("<script>") or "dataset.theme" not in prepaint:
        raise ValueError("Missing prepaint theme bootstrap")
    if any("<link" in item and "stylesheet" in item for item in head_items):
        raise ValueError("Portable fragment cannot depend on external stylesheets")
    return (
        f"<title>{escape(title, quote=False)}</title>\n"
        + prepaint + "\n"
        + "\n".join(head_items) + "\n"
        + body
    )
