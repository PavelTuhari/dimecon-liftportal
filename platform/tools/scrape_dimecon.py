"""Выгрузка содержимого dimecon.md.

Особенности исходного сайта, учтённые здесь:
  * пагинация разделов — параметр &start=N (шаг 10);
  * у каждого языка СВОИ идентификаторы записей, поэтому языки сопоставляются по порядку в списке;
  * в правой колонке (div.right_content) висит сквозной блок «КРАНЫ» — его нужно отрезать,
    иначе ссылки сайдбара попадают в каждый раздел.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://dimecon.md/"
OUT = Path("../docs/dimecon_source")
OUT.mkdir(parents=True, exist_ok=True)
HDRS = {"User-Agent": "Mozilla/5.0 (compatible; content-migration/1.0)"}
LANGS = ("ro", "ru", "en")
TIPS = ("auto", "turn", "senile", "transport", "servicii", "vinzari", "noutati")
cache: dict[str, str] = {}


def get(url: str) -> str:
    if url in cache:
        return cache[url]
    full = urllib.parse.urljoin(BASE, url)
    html = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers=HDRS), timeout=30) as r:
                html = r.read().decode("utf-8", "replace")
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                print("  !! не удалось:", full, exc)
            time.sleep(1.5)
    cache[url] = html
    time.sleep(0.2)
    return html


def main_part(html: str) -> str:
    """Только основная колонка: обрезаем сквозной сайдбар и подвал."""
    i = html.find('<div class="right_content"')
    return html[:i] if i > 0 else html


def content_block(html: str) -> str:
    """Тело карточки исходного сайта лежит в div#continut."""
    m = re.search(r'(?is)<div id="continut">(.*?)(?:<div class="right_content"|<div class="clear")', html)
    if m:
        return m.group(1)
    m = re.search(r'(?is)<div class="left_content"[^>]*>(.*)', main_part(html))
    return m.group(1) if m else main_part(html)


ROW_RE = re.compile(r"(?is)<tr[^>]*>(.*?)</tr>")
CELL_RE = re.compile(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>")


def parse_specs(html: str) -> list[list[str]]:
    """Таблицы ТТХ исходного сайта -> строки вида [подпись, значение]."""
    rows = []
    for tr in ROW_RE.findall(html):
        cells = [strip_tags(c).replace("\xa0", " ").strip() for c in CELL_RE.findall(tr)]
        cells = [c for c in cells if c]
        if 2 <= len(cells) <= 4:
            rows.append(cells)
    return rows


def strip_tags(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|tr|li|h[1-6])>", "\n", html)
    txt = unescape(re.sub(r"(?s)<[^>]+>", " ", html)).replace("﻿", "").replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n", txt).strip()


def clean_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?is)<div class=\"readmore2\".*?</div>", "", html)
    html = re.sub(r"(?i)</?(font|span|o:p|div|table|tbody|tr|td|th|center|a)[^>]*>", " ", html)
    html = re.sub(r'(?i)\s(class|style|lang|align|valign|width|height|border|cellpadding|cellspacing)="[^"]*"', "", html)
    html = unescape(html).replace("﻿", "").replace("\xa0", " ")
    html = re.sub(r"[ \t]{2,}", " ", html)
    html = re.sub(r"(?:\s*<br\s*/?>\s*){2,}", "\n", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


ITEM_RE = re.compile(
    r'(?is)<h3><a href="([^"]*opa=view[^"]*)"[^>]*>(.*?)</a>\s*</h3>(.*?)(?:<div class="clear">|<h3>|<div class="pages">)')
IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
SKIP_IMG = re.compile(r"(spacer|pixel|bullet|arrow|line|bg_|menu|logo|banner)", re.I)


def listing(tip: str, lang: str) -> list[dict]:
    """Все карточки раздела по порядку, со всех страниц пагинации."""
    items, start, seen = [], 0, set()
    while start < 200:
        html = main_part(get(f"index.php?pag=news&tip={tip}&l={lang}&start={start}"))
        found = ITEM_RE.findall(html)
        new = 0
        for href, title, desc in found:
            m = re.search(r"id=(\d+)", href)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            summary = re.sub(r"\s+", " ", strip_tags(desc)).replace("Читать далее...", "")
            summary = re.sub(r"(?i)(citeşte mai mult|read more|mai mult)\.*", "", summary).strip()
            items.append({"id": m.group(1), "title": strip_tags(title), "summary": summary})
            new += 1
        if not new or f"start={start + 10}" not in html:
            break
        start += 10
    return items


def item_page(tip: str, iid: str, lang: str) -> dict:
    raw = get(f"index.php?pag=news&opa=view&id={iid}&tip={tip}&l={lang}")
    body = content_block(raw)
    specs = parse_specs(body)
    text = strip_tags(body)
    mt = re.search(r"(?is)<h3[^>]*>(.*?)</h3>", main_part(raw))
    title = strip_tags(mt.group(1)) if mt else ""
    images = [urllib.parse.urljoin(BASE, s) for s in IMG_RE.findall(body) if not SKIP_IMG.search(s)]
    return {"id": iid, "title": title, "text": text, "html": clean_html(body)[:20000],
            "images": images[:10], "specs": specs}


def static_page(url: str, lang: str) -> dict:
    body = main_part(get(url))
    return {"url": url, "text": strip_tags(body), "html": clean_html(body)[:30000]}


if __name__ == "__main__":
    data: dict = {"tips": {}, "pages": {}, "forms": {}}

    for tip in TIPS:
        data["tips"][tip] = {}
        print(f"\n[{tip}]")
        for lang in LANGS:
            lst = listing(tip, lang)
            rows = []
            for it in lst:
                page = item_page(tip, it["id"], lang)
                page["list_title"] = it["title"]
                page["summary"] = it["summary"]
                rows.append(page)
            data["tips"][tip][lang] = rows
            print(f"   {lang}: {len(rows)} — " + "; ".join(r["list_title"][:46] for r in rows[:3]))

    for pid, name in (("83", "about"), ("87", "contacts")):
        data["pages"][name] = {lang: static_page(f"index.php?pag=page&id={pid}&l={lang}", lang) for lang in LANGS}
        print(f"[page {name}] ok")
    for form in ("aplica_macara", "aplica_transport"):
        data["forms"][form] = {lang: static_page(f"index.php?pag={form}&l={lang}", lang) for lang in LANGS}
        print(f"[form {form}] ok")

    (OUT / "content.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(v["ro"]) for v in data["tips"].values())
    print(f"\nИтого карточек (RO): {total}")
    for tip in TIPS:
        n = {lang: len(data["tips"][tip][lang]) for lang in LANGS}
        print(f"  {tip:<10} {n}")
    print("Сохранено:", (OUT / "content.json").resolve())
