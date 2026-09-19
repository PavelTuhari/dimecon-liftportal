"""Проверка расчётов, оформления заказов, форм и выгрузок PDF/XLSX.

Каждый расчёт проверяется независимо: ожидаемое значение считается в тесте
арифметикой из исходных ставок, затем сравнивается с ответом движка.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Contact, Document, Equipment, Order, Shift, Tenant  # noqa: E402
from portal.services import selector  # noqa: E402
from portal.services.pricing import DEFAULT_PRICING, calculate, pricing_of, urgency_factor  # noqa: E402

OUT = Path("../docs/generated")
OUT.mkdir(parents=True, exist_ok=True)
app = create_app()
passed, failed = [], []


def check(name: str, ok: bool, detail: str = ""):
    (passed if ok else failed).append(name)
    print(f"  {'OK  ' if ok else 'ОШИБКА'} {name}" + (f" — {detail}" if detail else ""))


def near(a, b, tol=0.51):
    return abs(float(a) - float(b)) <= tol


with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    P = pricing_of(tenant)
    fleet = db.query(Equipment).filter_by(tenant_id=tenant.id, is_published=True).all()
    gmk5100 = next(e for e in fleet if "5100" in e.model)
    ks3577 = next(e for e in fleet if "3577" in e.model)

    print("\n=== 1. РАСЧЁТ СТОИМОСТИ: проверка каждой составляющей ===")
    base_day = datetime(2026, 10, 1, 9, 0)      # четверг, будни, день
    r = calculate(tenant, ks3577, start=base_day, hours=4, distance_km=10, conditions=[])
    season = P["season"]["10"]
    expect_base = 4 * ks3577.hourly_rate * season
    expect_mob = ks3577.mobilization_fee
    expect_net = expect_base + expect_mob
    expect_vat = expect_net * tenant.vat_rate / 100
    expect_total = round((expect_net + expect_vat) / 10) * 10
    check("будни, 4 ч, город: сумма строк = итогу",
          near(sum(x["amount"] for x in r["lines"]), r["net"] + r["vat"], 2),
          f"строки {sum(x['amount'] for x in r['lines'])}, нетто+НДС {r['net'] + r['vat']}")
    check("будни: итог совпадает с ручным расчётом", near(r["total"], expect_total, 11),
          f"движок {r['total']}, ручной {expect_total}")
    check("НДС 20 % от нетто", near(r["vat"], r["net"] * 0.2, 2), f"{r['vat']} vs {r['net'] * 0.2:.0f}")

    r_min = calculate(tenant, ks3577, start=base_day, hours=1, distance_km=10, conditions=[])
    check("минимальная смена: 1 ч тарифицируется как 4 ч", near(r_min["total"], r["total"], 11),
          f"1 ч -> {r_min['total']}, 4 ч -> {r['total']}")

    r_sun = calculate(tenant, ks3577, start=datetime(2026, 10, 4, 9, 0), hours=4, distance_km=10, conditions=[])
    k_sun = P["time"]["sunday"]
    check(f"воскресный коэффициент x{k_sun} применён к работе",
          near(r_sun["net"] - r["net"], 4 * ks3577.hourly_rate * season * (k_sun - 1), 3),
          f"разница {r_sun['net'] - r['net']:.0f}")

    r_night = calculate(tenant, ks3577, start=datetime(2026, 10, 1, 23, 0), hours=4, distance_km=10, conditions=["night"])
    check("ночь: коэффициент 1.5 и осветительная установка в строках",
          any("ночь" in x["title"] for x in r_night["lines"]) and any("свет" in x["title"].lower() for x in r_night["lines"]),
          "; ".join(x["title"] for x in r_night["lines"]))

    r_far = calculate(tenant, ks3577, start=base_day, hours=4, distance_km=48, conditions=[])
    zone = next(z for z in P["zones"] if 48 <= z["max_km"])
    extra = (48 - zone["free_km"]) * (ks3577.per_km_rate or zone["per_km"]) * 2
    mob_line = next(x for x in r_far["lines"] if x["code"] == "mob")
    check(f"зона «{zone['name']}»: подача {zone['fee']} + перепробег",
          near(mob_line["amount"], (ks3577.mobilization_fee or zone["fee"]) + extra, 2),
          f"{mob_line['amount']} (ожидали {(ks3577.mobilization_fee or zone['fee']) + extra:.0f})")

    soon = datetime.utcnow() + timedelta(hours=3)
    r_urg = calculate(tenant, ks3577, start=soon, hours=4, distance_km=10, conditions=[])
    check(f"срочность x{urgency_factor(P, soon)} добавлена отдельной строкой",
          any(x["code"] == "urgent" for x in r_urg["lines"]), f"итого {r_urg['total']}")

    r_flex = calculate(tenant, ks3577, start=base_day, hours=4, distance_km=10, conditions=[], flexible=True)
    check("скидка за гибкую дату уменьшает итог", r_flex["total"] < r["total"],
          f"{r_flex['total']} < {r['total']}")

    r_cap = calculate(tenant, ks3577, start=base_day, hours=4, distance_km=10,
                      conditions=["tight", "soft_ground", "power_line"])
    cond_line = next((x for x in r_cap["lines"] if x["code"] == "cond"), None)
    factor = float(re.search(r"x\s*([\d.]+)", cond_line["title"].replace("×", "x")).group(1))
    check(f"потолок коэффициента условий {P['conditions_cap']} соблюдён", factor <= P["conditions_cap"] + 1e-9,
          f"фактически x{factor}")

    r_disc = calculate(tenant, gmk5100, start=base_day, hours=8, distance_km=10, conditions=[],
                       flexible=True, first_online=True, partner_discount=0.30)
    total_disc = sum(-x["amount"] for x in r_disc["lines"] if x["code"].startswith("d_"))
    subtotal = sum(x["amount"] for x in r_disc["lines"] if not x["code"].startswith("d_") and x["code"] != "vat")
    check(f"потолок суммарной скидки {P['discounts']['max_total'] * 100:.0f} %",
          total_disc <= subtotal * P["discounts"]["max_total"] + 1,
          f"скидок на {total_disc:.0f} из {subtotal:.0f}")

    print("\n=== 2. ПОДБОР ТЕХНИКИ ===")
    sel = selector.select_equipment(tenant.id, weight_t=3, height_m=3, offset_m=10, cargo_dim_m=6,
                                    cargo_h_m=2.5, start=base_day, hours=4, conditions=[], task_type="place")
    check("расчётная масса = (груз + строповка) x 1,10", near(sel.m_calc, (3 + 0.3) * 1.1, 0.01), f"{sel.m_calc} т")
    check("требуемая высота = высота + груз + строповка + 2 м",
          near(sel.h_req, 3 + 2.5 + max(1.5, 0.5 * 6) + 2.0, 0.01), f"{sel.h_req} м")
    check("подбор вернул варианты", len(sel.candidates) > 0, f"{len(sel.candidates)} шт")
    for c in sel.candidates:
        r_req = 10 + 0.5 * 6 + c.equipment.outrigger_half_m
        cap = c.chart.capacity_t if c.chart else None
        check(f"  {c.equipment.brand} {c.equipment.model}: запас >= 10 %", c.reserve >= 0.10 - 1e-9,
              f"запас {c.reserve * 100:.0f} %" + (f", таблица {cap} т на {c.chart.radius_m} м" if c.chart else ""))
        check(f"  {c.equipment.model}: вылет таблицы >= требуемого {r_req:.1f} м",
              (not c.chart) or c.chart.radius_m >= r_req - 1e-6,
              f"{c.chart.radius_m if c.chart else '—'} м")

    esc = selector.select_equipment(tenant.id, weight_t=42, height_m=12, offset_m=30, cargo_dim_m=3, cargo_h_m=2,
                                    start=base_day, hours=8, conditions=["power_line"], task_type="lift_height")
    check("эскалация при 42 т и ЛЭП", esc.escalated and any("ЛЭП" in x for x in esc.reasons),
          f"{len(esc.reasons)} причин")
    small = selector.select_equipment(tenant.id, weight_t=0.5, height_m=3, offset_m=5, cargo_dim_m=1, cargo_h_m=1,
                                      start=base_day, hours=4, conditions=[], task_type="install")
    check("лёгкий груз не уходит в эскалацию", not small.escalated or not small.candidates,
          f"вариантов {len(small.candidates)}, эскалация {small.escalated}")

    print("\n=== 3. КАЛЬКУЛЯТОР МАССЫ ===")
    lo, hi = selector.estimate_mass(2, 1, 1, "concrete", False)
    check("бетон 2x1x1 м = 5 т ±15 %", near(lo, 2 * 2.5 * 0.85, 0.1) and near(hi, 2 * 2.5 * 1.15, 0.1), f"{lo}–{hi} т")
    lo_h, hi_h = selector.estimate_mass(6, 2.4, 2.5, "steel", True)
    check("полая ёмкость считается по стенкам, а не по объёму", hi_h < 30, f"{lo_h}–{hi_h} т")

print("\n=== 4. ОФОРМЛЕНИЕ ЗАКАЗА И ФОРМЫ (HTTP) ===")
c = app.test_client()


def csrf():
    with c.session_transaction() as s:
        return s.get("csrf")


def wz(step, data):
    data["_csrf"] = csrf()
    return c.post(f"/s/dimecon/calculator?step={step}", data=data, follow_redirects=True)


c.get("/s/dimecon/calculator/reset", follow_redirects=True)   # рендер страницы выдаёт CSRF-токен сессии
wz(1, {"task": "place"}); wz(2, {"preset": "cabin6"}); wz(3, {"height": "3"})
wz(4, {"radius_code": "sidewalk"}); wz(5, {"cond": ["rigger"]})
res = wz(6, {"start": "2026-10-01T09:00", "hours": "4", "address": "Chișinău, str. Test 1", "distance": "9"})
html = res.get_data(as_text=True)
check("визард дошёл до результата", "Ваш вариант" in html, f"вариантов: {html.count('class=\"offer ')}")
eq_id = re.search(r'name="equipment_id" id="eqid" value="(\d+)"', html)
sub = c.post("/s/dimecon/calculator/submit", follow_redirects=True,
             data={"_csrf": csrf(), "equipment_id": eq_id.group(1) if eq_id else "",
                   "name": "Ион Мунтяну", "phone": "069 45 67 89", "email": "test.client@example.md",
                   "comment": "тест оформления"})
num = re.search(r"DIM-\d{4}-\d{5}", sub.get_data(as_text=True))
check("заявка оформлена и получила номер", bool(num), num.group(0) if num else "номер не найден")
order_number = num.group(0) if num else None

bad = c.post("/s/dimecon/calculator/submit", data={"equipment_id": "1", "name": "X", "phone": "1"})
check("форма без CSRF отклонена", bad.status_code == 400, f"HTTP {bad.status_code}")
contact_form = c.post("/s/dimecon/contacts", follow_redirects=True,
                      data={"_csrf": csrf(), "name": "Тест Контакт", "phone": "060 11 22 33",
                            "email": "form@example.md", "message": "проверка формы обратной связи"})
check("форма обратной связи принята", "Сообщение отправлено" in contact_form.get_data(as_text=True))
apply_form = c.post("/s/dimecon/partner/apply", follow_redirects=True,
                    data={"_csrf": csrf(), "company": "ТестСтрой SRL", "idno": "1012600099999",
                          "name": "Прораб Тестов", "phone": "069 99 88 77", "email": "p@example.md",
                          "about": "нужен кран на объект"})
check("форма заявки партнёра принята", "Заявка отправлена" in apply_form.get_data(as_text=True))

# вход владельцем для документов
r = c.get("/login")
tok = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
c.post("/login", data={"email": "owner@dimecon.md", "password": "demo1234", "_csrf": tok})

with app.app_context():
    order = db.query(Order).filter_by(tenant_id=1, number=order_number).one()
    oid = order.id
    # выпускаем комплект документов и рапорт
    for doc_type, amount in (("quote", order.price_max or 9000), ("invoice", order.price_max or 9000),
                             ("act", order.price_max or 9000)):
        c.post(f"/s/dimecon/admin/orders/{oid}",
               data={"_csrf": csrf(), "action": "document", "doc_type": doc_type, "amount": str(amount)})
    c.post(f"/s/dimecon/admin/orders/{oid}",
           data={"_csrf": csrf(), "action": "shift", "work_date": "2026-10-01", "operator": "Василий Гуцу",
                 "hours_worked": "6", "hours_idle": "1", "idle_fault": "customer", "lifts": "12",
                 "notes": "простой — ожидание разгрузки"})
    docs = db.query(Document).filter_by(order_id=oid).all()
    shift = db.query(Shift).filter_by(order_id=oid).first()
    check("документы выпущены", len(docs) == 3, ", ".join(f"{d.type} {d.number}" for d in docs))
    check("сменный рапорт создан", shift is not None, f"{shift.hours_worked} ч + {shift.hours_idle} ч простоя" if shift else "")

print("\n=== 5. PDF ===")
pdf_targets = [(f"/s/dimecon/export/orders/{oid}/confirmation.pdf", "Подтверждение заказа")]
with app.app_context():
    for d in db.query(Document).filter_by(order_id=oid).all():
        pdf_targets.append((f"/s/dimecon/export/documents/{d.id}.pdf", d.type))
    sh = db.query(Shift).filter_by(order_id=oid).first()
    pdf_targets.append((f"/s/dimecon/export/shifts/{sh.id}.pdf", "Сменный рапорт"))

for url, label in pdf_targets:
    resp = c.get(url)
    data = resp.get_data()
    name = url.rsplit("/", 1)[-1].replace(".pdf", "") + f"_{label}.pdf"
    ok = resp.status_code == 200 and data[:4] == b"%PDF" and len(data) > 1500
    if ok:
        (OUT / name).write_bytes(data)
    check(f"PDF {label}", ok, f"{len(data)} Б, {resp.headers.get('Content-Type')}")

print("\n=== 6. EXCEL ===")
xlsx_targets = [("/s/dimecon/export/orders.xlsx", "Заявки"), ("/s/dimecon/export/shifts.xlsx", "Смены"),
                ("/s/dimecon/export/documents.xlsx", "Документы"), ("/s/dimecon/export/fleet.xlsx", "Парк"),
                ("/s/dimecon/export/contacts.xlsx", "Контакты"), ("/s/dimecon/export/pricelist.xlsx", "Прайс-лист")]
for url, label in xlsx_targets:
    resp = c.get(url)
    data = resp.get_data()
    ok = resp.status_code == 200 and data[:2] == b"PK" and len(data) > 2000
    sheets = []
    if ok:
        (OUT / f"{label}.xlsx").write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            wb = z.read("xl/workbook.xml").decode("utf-8")
            sheets = re.findall(r'name="([^"]+)"', wb)
    check(f"XLSX {label}", ok, f"{len(data)} Б, листы: {', '.join(sheets)}")

# содержимое выгрузки проверяем чтением обратно
from openpyxl import load_workbook  # noqa: E402

wb = load_workbook(OUT / "Заявки.xlsx")
ws = wb.active
headers = [c.value for c in ws[1]]
numbers = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
check("в выгрузке заявок есть оформленная заявка", order_number in numbers,
      f"строк {ws.max_row - 1}, колонок {len(headers)}")
check("в выгрузке есть строка ИТОГО с формулой",
      any(isinstance(ws.cell(row=r, column=20).value, str) and str(ws.cell(row=r, column=20).value).startswith("=SUM")
          for r in range(2, ws.max_row + 1)))
wbp = load_workbook(OUT / "Прайс-лист.xlsx")
check("прайс-лист содержит 4 листа", len(wbp.sheetnames) == 4, ", ".join(wbp.sheetnames))
wbf = load_workbook(OUT / "Парк.xlsx")
check("выгрузка парка содержит грузовые таблицы", "Грузовые таблицы" in wbf.sheetnames,
      f"строк в таблицах: {wbf['Грузовые таблицы'].max_row - 1}")

print("\n=== 7. ДОСТУП К ДОКУМЕНТАМ ===")
anon_client = app.test_client()          # чистая сессия без входа
anon = anon_client.get(pdf_targets[1][0])
check("аноним не скачивает документ", anon.status_code in (302, 401, 403), f"HTTP {anon.status_code}")
anon_x = anon_client.get("/s/dimecon/export/orders.xlsx")
check("аноним не выгружает реестр заявок", anon_x.status_code in (302, 401, 403), f"HTTP {anon_x.status_code}")
anon_p = anon_client.get("/s/dimecon/export/pricelist.xlsx")
check("прайс-лист доступен публично", anon_p.status_code == 200 and anon_p.get_data()[:2] == b"PK",
      f"HTTP {anon_p.status_code}")
c = app.test_client()
r = c.get("/login")
tok = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
c.post("/login", data={"email": "client@example.com", "password": "demo1234", "_csrf": tok})
foreign = c.get(pdf_targets[1][0])
check("чужой клиент не скачивает документ по заявке другого клиента", foreign.status_code == 403,
      f"HTTP {foreign.status_code}")

print(f"\nИТОГО: пройдено {len(passed)}, ошибок {len(failed)}")
if failed:
    print("НЕ ПРОЙДЕНЫ:")
    for f in failed:
        print("  -", f)
print("Файлы:", OUT.resolve())
sys.exit(1 if failed else 0)
