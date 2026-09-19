"""Безопасный вывод форматированного текста из базы.

Описания техники, услуг, товаров и страниц хранятся как HTML: часть пришла с сайта
заказчика при переносе, часть редактируется владельцем компании в кабинете.
Выводить такой текст через |safe нельзя — это чужой ввод, а страницы публичные.

Фильтр экранирует всё, а затем возвращает к разметке только простые теги из белого
списка. Атрибуты не восстанавливаются ни у одного тега, кроме class="specs-table"
у таблицы характеристик, — поэтому ни onerror, ни href="javascript:" не выживают.
"""
from __future__ import annotations

import re

from markupsafe import Markup, escape

ALLOWED = ("p", "br", "b", "strong", "i", "em", "u", "small", "sub", "sup",
           "ul", "ol", "li", "h3", "h4", "h5", "table", "thead", "tbody", "tr", "td", "th")

# Атрибуты внутри тега могут содержать экранированные кавычки (&#34;), поэтому идём
# до первого закрывающего &gt;, а не «до первого &». Сами атрибуты отбрасываем.
_ATTRS = r"(?:\s(?:(?!&gt;|&lt;).)*)?"
_OPEN = re.compile(r"&lt;(" + "|".join(ALLOWED) + r")" + _ATTRS + r"\s*/?&gt;", re.I)
_CLOSE = re.compile(r"&lt;/(" + "|".join(ALLOWED) + r")\s*&gt;", re.I)
_SPECS = re.compile(r"<table>(?=\s*<tbody>\s*<tr>\s*<td>)", re.I)


def richtext(value) -> Markup:
    """HTML из базы → безопасная разметка с белым списком тегов."""
    if value is None:
        return Markup("")
    if isinstance(value, dict):  # на случай, если в шаблон пришло поле i18n целиком
        value = value.get("ru") or next(iter(value.values()), "")
    out = str(escape(value))
    out = _OPEN.sub(lambda m: f"<{m.group(1).lower()}>", out)
    out = _CLOSE.sub(lambda m: f"</{m.group(1).lower()}>", out)
    out = _SPECS.sub('<table class="specs-table">', out)
    return Markup(out)


def plain(value, limit: int = 0) -> str:
    """Тот же текст без разметки — для карточек, списков и метатегов."""
    if isinstance(value, dict):
        value = value.get("ru") or next(iter(value.values()), "")
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text.replace("&nbsp;", " ")).strip()
    return text[:limit].rstrip(" ,.;") + "…" if limit and len(text) > limit else text
