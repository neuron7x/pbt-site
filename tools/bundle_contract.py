"""Фейл-клоуз контракт інлайнування CSS у переносних збірках ПБТ."""

import re


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
        f"<title>{title}</title>\n"
        + prepaint + "\n"
        + "\n".join(head_items) + "\n"
        + body
    )
