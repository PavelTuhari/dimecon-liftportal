"""Проверка фильтра безопасного вывода текста из базы.

Запуск:  ../.venv/Scripts/python tools/test_richtext.py

Текст описаний приходит с сайта заказчика и редактируется владельцем компании,
а страницы публичные — значит разметку нужно и показать, и обезвредить.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal.richtext import plain, richtext  # noqa: E402

LOG: list[str] = []
passed = failed = 0


def out(line: str = ""):
    print(line)
    LOG.append(line)


def section(title: str):
    out("")
    out(f"=== {title} ===")


def check(ok: bool, name: str, detail: str = ""):
    global passed, failed
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
    out(f"  {'OK' if ok else 'ОШИБКА'}   {name}" + (f" — {detail}" if detail else ""))


section("1. РАЗМЕТКА ИЗ ИСТОЧНИКА СОХРАНЯЕТСЯ")
src = ('<p><strong>Стальные канаты</strong></p>\n'
       '<table class="specs-table"><tbody>\n<tr><td>Диаметр, мм</td><td>Масса, кг/м</td></tr>\n'
       '<tr><td>5.6</td><td>0,120</td></tr>\n</tbody></table>')
html = str(richtext(src))
check("<p>" in html and "<strong>" in html, "абзацы и выделение выводятся разметкой", "<p>, <strong>")
check(html.count("<table") == 1, "таблица характеристик открывается", "тег <table> восстановлен")
check(html.count("<tr>") == 2 and html.count("<td>") == 4, "строки и ячейки таблицы на месте", "2 строки, 4 ячейки")
check('class="specs-table"' in html, "таблице возвращён служебный класс оформления")
check("&lt;table" not in html, "экранированных тегов в выводе не осталось")

section("2. ОПАСНАЯ РАЗМЕТКА ОБЕЗВРЕЖИВАЕТСЯ")
CASES = [
    ("<script>alert(1)</script>", "<script", "скрипт не выводится тегом"),
    ('<img src=x onerror="alert(1)">', "<img", "картинка с обработчиком не выводится"),
    ('<a href="javascript:alert(1)">клик</a>', "<a", "ссылка с javascript: не выводится"),
    ('<p onclick="alert(1)">текст</p>', "onclick", "обработчик события у разрешённого тега отброшен"),
    ('<iframe src="http://evil"></iframe>', "<iframe", "встроенный фрейм не выводится"),
    ('<table class="x" onmouseover="alert(1)"><tr><td>1</td></tr></table>', "onmouseover",
     "обработчик у таблицы отброшен"),
]
for evil, banned, name in CASES:
    html = str(richtext(evil))
    check(banned not in html, name, f"в выводе нет «{banned}»")
check("<p>текст</p>" in str(richtext('<p onclick="alert(1)">текст</p>')),
      "разрешённый тег с опасным атрибутом остаётся тегом", "атрибут убран, абзац сохранён")

section("3. ТЕКСТ БЕЗ РАЗМЕТКИ")
check(plain(src).startswith("Стальные канаты"), "plain убирает теги", plain(src)[:40])
check(plain(src, 20).endswith("…"), "plain обрезает по длине с многоточием", plain(src, 20))
check(plain({"ru": "<p>Привет</p>", "en": "<p>Hi</p>"}) == "Привет", "поле i18n берётся по основному языку")
check(str(richtext(None)) == "", "пустое значение не ломает вывод")

out("")
out(f"ИТОГО: пройдено {passed}, ошибок {failed}")
with open("../docs/test_richtext.log", "w", encoding="utf-8") as f:
    f.write("\n".join(LOG) + "\n")
sys.exit(1 if failed else 0)
