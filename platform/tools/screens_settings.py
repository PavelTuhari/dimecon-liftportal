"""Снимки экранов раздела «Запуск компании» для акта и презентации.

    ../.venv/Scripts/python tools/screens_settings.py [http://localhost:8090]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
OUT = Path("../docs/screens")
OUT.mkdir(parents=True, exist_ok=True)
shots: list[tuple[str, str]] = []

PAGES = [
    ("110_setup_index", "/s/dimecon/admin/setup", "Запуск компании: пять настроек и готовность"),
    ("111_setup_charts", "/s/dimecon/admin/setup/load-charts", "Грузовые таблицы: загрузка паспорта и состояние парка"),
    ("112_setup_pricing", "/s/dimecon/admin/setup/pricing", "Прайс: ставки, смены, зоны подачи, коэффициенты"),
    ("113_setup_company", "/s/dimecon/admin/setup/company", "Реквизиты банка и почтовый сервер компании"),
    ("114_setup_domain", "/s/dimecon/admin/setup/domain", "Свой домен: записи DNS и проверка привязки"),
]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = ctx.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.fill("input[type=email]", "owner@dimecon.md")
        page.fill("input[type=password]", "demo1234")
        page.click("form button.primary")
        page.wait_for_load_state("networkidle")

        for name, url, caption in PAGES:
            page.goto(BASE + url, wait_until="networkidle")
            page.add_style_tag(content=".wz-nav,.sticky-cta{position:static !important}")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            shots.append((name, caption))
            print(f"  + {name}.png — {caption}")

        browser.close()

    idx = OUT / "index.txt"
    have = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                k, v = line.split("\t", 1)
                have[k] = v
    for n, c in shots:
        have[n] = c
    idx.write_text("\n".join(f"{k}\t{v}" for k, v in sorted(have.items())), encoding="utf-8")
    print(f"\nГотово: {len(shots)} снимков раздела настроек")


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"время: {time.time() - t0:.1f} c")
