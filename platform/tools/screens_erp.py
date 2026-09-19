"""Снимки экранов управленческих модулей для акта и презентации.

    ../.venv/Scripts/python tools/screens_erp.py [http://localhost:8090]
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


def shot(page, name: str, caption: str, full=True):
    page.add_style_tag(content=".wz-nav,.sticky-cta{position:static !important}")
    page.wait_for_timeout(350)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    shots.append((name, caption))
    print(f"  + {name}.png — {caption}")


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

        pages = [
            ("90_erp_projects", "/s/dimecon/admin/projects", "Объекты: план и факт, маржа по каждому"),
            ("92_erp_tasks", "/s/dimecon/admin/tasks", "Задачи по стадиям: канбан по всем объектам"),
            ("93_erp_sales", "/s/dimecon/admin/sales", "Коммерческие предложения: воронка и конверсия"),
            ("95_erp_purchase", "/s/dimecon/admin/purchase", "Закупки: запросы цен, приёмка, долги поставщикам"),
            ("96_erp_vendors", "/s/dimecon/admin/vendors", "Поставщики: анализ сроков и объёмов"),
            ("97_erp_reorder", "/s/dimecon/admin/purchase/reorder", "Пополнение склада по правилам"),
            ("98_erp_invoices", "/s/dimecon/admin/invoices", "Счета: оплаты, просрочка, дебиторка по срокам"),
            ("100_erp_plans", "/s/dimecon/admin/plans", "Повторяющиеся счета: абонементы и обслуживание"),
            ("101_erp_sheets", "/s/dimecon/admin/sheets", "Таблицы компании"),
            ("103_erp_docs", "/s/dimecon/admin/docs", "Документы: пространства, теги, запросы, правила"),
        ]
        for name, url, caption in pages:
            page.goto(BASE + url, wait_until="networkidle")
            shot(page, name, caption)

        # карточка объекта
        page.goto(f"{BASE}/s/dimecon/admin/projects", wait_until="networkidle")
        # берём объект с реальной историей работ, а не первый попавшийся
        rich = page.locator("table a[href*='/admin/projects/']", has_text="Рышкановка")
        link = rich.first if rich.count() else page.locator("table a[href*='/admin/projects/']").first
        if link.count():
            link.click()
            page.wait_for_load_state("networkidle")
            shot(page, "91_erp_project", "Карточка объекта: работы, вехи, часы, деньги")

        # карточка предложения
        page.goto(f"{BASE}/s/dimecon/admin/sales", wait_until="networkidle")
        link = page.locator("table a[href*='/admin/sales/']").first
        if link.count():
            link.click()
            page.wait_for_load_state("networkidle")
            shot(page, "94_erp_sale", "Предложение: строки сметы, маржа, допработы, счёт")

        # карточка счёта
        page.goto(f"{BASE}/s/dimecon/admin/invoices", wait_until="networkidle")
        link = page.locator("table a[href*='/admin/invoices/']").first
        if link.count():
            link.click()
            page.wait_for_load_state("networkidle")
            shot(page, "99_erp_invoice", "Счёт: платежи, остаток, кредит-нота")

        # таблица с формулами
        page.goto(f"{BASE}/s/dimecon/admin/sheets", wait_until="networkidle")
        link = page.locator("table a[href*='/admin/sheets/']").first
        if link.count():
            link.click()
            page.wait_for_load_state("networkidle")
            shot(page, "102_erp_sheet", "Таблица: формулы, живые данные компании, диаграмма")

        # предложение глазами клиента
        ctx2 = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ru-RU")
        guest = ctx2.new_page()
        token = None
        page.goto(f"{BASE}/s/dimecon/admin/sales", wait_until="networkidle")
        link = page.locator("table a[href*='/admin/sales/']").first
        if link.count():
            link.click()
            page.wait_for_load_state("networkidle")
            code = page.locator("code").first
            if code.count():
                token = code.inner_text().strip().rsplit("/", 1)[-1]
        if token:
            guest.goto(f"{BASE}/s/dimecon/kp/{token}", wait_until="networkidle")
            shot(guest, "104_erp_sales_accept", "Предложение глазами клиента: принять по ссылке")
        ctx2.close()

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
    print(f"\nГотово: {len(shots)} снимков модулей")


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"время: {time.time() - t0:.1f} c")
