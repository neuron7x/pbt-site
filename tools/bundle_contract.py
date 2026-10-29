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
