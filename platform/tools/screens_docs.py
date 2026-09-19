"""Скриншоты сгенерированных документов (PDF в браузере, XLSX как HTML-превью)
и сравнение исходного сайта заказчика с перенесённым."""
from __future__ import annotations

import html
import sys
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://localhost:8090"
GEN = Path("../docs/generated").resolve()
OUT = Path("../docs/screens").resolve()
OUT.mkdir(parents=True, exist_ok=True)


def xlsx_preview_html(path: Path, max_rows=18, max_cols=10) -> str:
    wb = load_workbook(path)
    parts = [f"<h1>{html.escape(path.name)}</h1>"]
    for ws in wb.worksheets:
        parts.append(f"<h2>Лист «{html.escape(ws.title)}» — строк {ws.max_row}, колонок {ws.max_column}</h2><table>")
        for r, row in enumerate(ws.iter_rows(max_row=min(ws.max_row, max_rows), max_col=min(ws.max_column, max_cols)), 1):
            cells = []
            for c in row:
                v = c.value
                v = "" if v is None else (v.strftime("%d.%m.%Y %H:%M") if hasattr(v, "strftime") else str(v))
                tag = "th" if r == 1 else "td"
                cells.append(f"<{tag}>{html.escape(v)[:60]}</{tag}>")
            parts.append("<tr>" + "".join(cells) + "</tr>")
        parts.append("</table>")
        if ws.max_row > max_rows:
            parts.append(f"<p class=more>…ещё {ws.max_row - max_rows} строк</p>")
    style = """<style>body{font-family:Manrope,Segoe UI,sans-serif;margin:24px;color:#14181B}
    h1{font-size:19px;margin:0 0 4px}h2{font-size:13px;color:#5A646B;margin:18px 0 6px;font-weight:700}
    table{border-collapse:collapse;width:100%;font-size:11px;margin-bottom:6px}
    th,td{border:1px solid #DDE1E4;padding:4px 7px;text-align:left;vertical-align:top}
    th{background:#1F3A52;color:#fff;font-weight:700}tr:nth-child(even) td{background:#F5F6F7}
    .more{font-size:11px;color:#8A949B;margin:0}</style>"""
    return f"<!DOCTYPE html><html lang=ru><meta charset=utf-8>{style}{''.join(parts)}"


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1240, "height": 1000}, locale="ru-RU")
    page = ctx.new_page()

    print("PDF (рендер страниц через PDFium):")
    import pypdfium2 as pdfium

    pdfs = [("confirmation_Подтверждение заказа.pdf", "52_pdf_confirmation", "PDF: подтверждение заказа"),
            (next((f.name for f in GEN.glob("*quote.pdf")), ""), "53_pdf_quote", "PDF: коммерческое предложение"),
            (next((f.name for f in GEN.glob("*invoice.pdf")), ""), "54_pdf_invoice", "PDF: счёт на оплату с суммой прописью"),
            (next((f.name for f in GEN.glob("*act.pdf")), ""), "55_pdf_act", "PDF: акт выполненных работ со сменами"),
            (next((f.name for f in GEN.glob("*апорт*.pdf")), ""), "56_pdf_shift", "PDF: сменный рапорт")]
    for fname, out, caption in pdfs:
        if not fname or not (GEN / fname).exists():
            print("   пропуск:", fname)
            continue
        doc = pdfium.PdfDocument(str(GEN / fname))
        doc[0].render(scale=2).to_pil().save(OUT / f"{out}.png")
        print(f"   + {out}.png — {caption}")

    print("XLSX:")
    for i, (fname, out, caption) in enumerate([
            ("Заявки.xlsx", "57_xlsx_orders", "Excel: реестр заявок"),
            ("Прайс-лист.xlsx", "58_xlsx_pricelist", "Excel: прайс-лист, 4 листа"),
            ("Парк.xlsx", "59_xlsx_fleet", "Excel: парк и грузовые таблицы"),
            ("Смены.xlsx", "60_xlsx_shifts", "Excel: табель смен")]):
        src = GEN / fname
        if not src.exists():
            continue
        tmp = GEN / f"_preview_{i}.html"
        tmp.write_text(xlsx_preview_html(src), encoding="utf-8")
        page.goto(tmp.as_uri(), wait_until="load")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / f"{out}.png"), full_page=True)
        tmp.unlink()
        print(f"   + {out}.png — {caption}")

    print("Сравнение с исходным сайтом:")
    src_page = ctx.new_page()
    src_page.goto("http://dimecon.md/index.php?pag=news&tip=auto&l=ru", wait_until="domcontentloaded", timeout=45000)
    src_page.wait_for_timeout(1500)
    src_page.screenshot(path=str(OUT / "61_source_site.png"), full_page=False)
    print("   + 61_source_site.png — исходный сайт dimecon.md (каталог автокранов)")
    page.goto(f"{BASE}/s/dimecon/equipment", wait_until="networkidle")
    page.screenshot(path=str(OUT / "62_ported_catalog.png"), full_page=True)
    print("   + 62_ported_catalog.png — тот же парк после переноса на платформу")
    page.goto(f"{BASE}/s/dimecon/services", wait_until="networkidle")
    page.screenshot(path=str(OUT / "63_ported_services.png"), full_page=True)
    print("   + 63_ported_services.png — 14 услуг заказчика после переноса")
    browser.close()
print("готово")
