"""Проверка раздела «Запуск компании»: настройки и их применение.

    ../.venv/Scripts/python tools/test_settings.py

Проверяем не только сохранение значений, но и то, что они действительно меняют работу:
подбор переключается на паспортную таблицу, расчёт берёт новые зоны подачи, счёт
печатается с реквизитами, сроки и префиксы документов подчиняются настройкам.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from datetime import date

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Document, Domain, Equipment, LoadChart, Order, Tenant  # noqa: E402
from portal.services import domains as dom, invoicing, loadcharts as lc, selector, setup_state  # noqa: E402
from portal.services.pricing import DEFAULT_PRICING, calculate, pricing_of  # noqa: E402

app = create_app()
c = app.test_client()
LOG: list[str] = []
passed = failed = 0
BASE = "/s/dimecon/admin"
PY = sys.executable


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
    return ok


def csrf():
    with c.session_transaction() as s:
        return s.get("csrf")


def login(email="owner@dimecon.md"):
    r = c.get("/login")
    tok = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
    c.post("/login", data={"email": email, "password": "demo1234", "_csrf": tok})


def post(url, **data):
    data.setdefault("_csrf", csrf())
    return c.post(url, data=data, follow_redirects=True)


def script(name: str, *args) -> tuple[int, str]:
    r = subprocess.run([PY, f"tools/{name}", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    original_pricing = dict(tenant.pricing or {})
    login()

    # ---------------------------------------------------------------- страницы
    section("1. СТРАНИЦЫ РАЗДЕЛА НАСТРОЕК")
    for path, title in [("/setup", "сводка «Запуск компании»"),
                        ("/setup/load-charts", "грузовые таблицы"),
                        ("/setup/pricing", "прайс и ставки"),
                        ("/setup/company", "реквизиты и почта"),
                        ("/setup/domain", "свой домен")]:
        r = c.get(BASE + path)
        check(r.status_code == 200, f"{title}: {path}", f"HTTP {r.status_code}")
    r = c.get(BASE + "/setup/load-charts/template.csv")
    check(r.status_code == 200 and "вылет" in r.get_data(as_text=True),
          "образец файла грузовой таблицы скачивается", f"{len(r.data)} байт")

    # ---------------------------------------------------------------- грузовые таблицы
    section("2. ГРУЗОВЫЕ ТАБЛИЦЫ: РАЗБОР, ПРОВЕРКА, ПРИМЕНЕНИЕ")
    eq = (db.query(Equipment).filter(Equipment.tenant_id == tenant.id, Equipment.model.like("%403А%"))
          .first() or db.query(Equipment).filter_by(tenant_id=tenant.id).first())
    before_state = [r for r in lc.coverage(tenant) if r["eq"].id == eq.id][0]

    csv_text = ("машина;вылет, м;грузоподъёмность, т;высота, м;конфигурация\n"
                f"{eq.model};10;8;30;main\n"
                f"{eq.model};16;5;30;main\n"
                f"{eq.model};25;2,5;30;main\n"
                f"{eq.model};30;1,8;30;main\n")
    headers, rows = lc.read_table(csv_text.encode("utf-8"), "chart.csv")
    mapping = lc.detect_mapping(headers)
    check(set(mapping.values()) >= {"equipment", "radius", "capacity"},
          "колонки файла распознаны по заголовкам", str(sorted(set(mapping.values()))))

    parsed, report = lc.parse(tenant, headers, rows, mapping)
    check(len(parsed) == 4 and not report.unknown, "строки привязаны к машине парка",
          f"{report.line()}")
    check(not lc.validate(parsed), "таблица прошла проверку на здравый смысл")

    broken = list(parsed)
    broken.append({**parsed[0], "radius_m": 40, "capacity_t": 12})
    check(bool(lc.validate(broken)), "растущая нагрузка на большом вылете помечается ошибкой",
          lc.validate(broken)[0][:70])

    applied = lc.apply(tenant, parsed, replace=True)
    after = [r for r in lc.coverage(tenant) if r["eq"].id == eq.id][0]
    check(after["state"] == "passport" and after["passport"] == 4,
          "паспортная таблица загружена и заменила ориентировочную",
          f"было {before_state['state']} ({before_state['rows']} строк), стало паспорт ({after['passport']})")

    db.refresh(eq)
    chart = selector.best_chart(eq, 12, 4, 20)
    check(chart is not None and (chart.source or "") == "passport",
          "подбор считает по паспортной строке", f"вылет {chart.radius_m if chart else '—'} м")
    check(selector.chart_is_approx(eq) is False, "предупреждение об оценке снято для этой машины")

    other = next((r for r in lc.coverage(tenant) if r["state"] == "approx"), None)
    if other:
        check(selector.chart_is_approx(other["eq"]) is True,
              "по остальным машинам предупреждение осталось", other["eq"].model)

    s = lc.summary(tenant)
    check(s["with_passport"] >= 1, "сводка по парку считает паспортные таблицы",
          f"паспорт у {s['with_passport']} из {s['machines']}")

    # загрузка через интерфейс
    data = {"_csrf": csrf(), "action": "import", "replace": "1",
            "file": (io.BytesIO(csv_text.encode("utf-8")), "chart.csv")}
    r = c.post(BASE + "/setup/load-charts", data=data, follow_redirects=True,
               content_type="multipart/form-data")
    check(r.status_code == 200, "загрузка файла через кабинет выполняется", f"HTTP {r.status_code}")

    # ---------------------------------------------------------------- прайс
    section("3. ПРАЙС: СТАВКИ, ЗОНЫ, КОЭФФИЦИЕНТЫ")
    eq_rate = db.query(Equipment).filter_by(tenant_id=tenant.id).filter(Equipment.hourly_rate > 0).first()
    old_rate = eq_rate.hourly_rate
    post(BASE + "/setup/pricing", action="rates", **{f"rate_{eq_rate.id}": old_rate + 100,
                                                     f"min_{eq_rate.id}": 5,
                                                     f"mob_{eq_rate.id}": eq_rate.mobilization_fee or 0})
    db.refresh(eq_rate)
    check(eq_rate.hourly_rate == old_rate + 100 and eq_rate.min_hours == 5,
          "ставка и минимальная смена сохраняются", f"{old_rate} → {eq_rate.hourly_rate}, мин. 5 ч")

    from datetime import datetime, timedelta
    when = datetime.utcnow().replace(hour=10, minute=0) + timedelta(days=7)
    base_quote = calculate(tenant, eq_rate, start=when, hours=4, distance_km=10, conditions=[])
    form = {"action": "form", "zone_name_0": "Город", "zone_code_0": "city", "zone_fee_0": 2000,
            "zone_free_0": 15, "zone_perkm_0": 25, "zone_max_0": 15,
            "zone_name_1": "Пригород до 30 км", "zone_code_1": "suburb", "zone_fee_1": 2500,
            "zone_free_1": 15, "zone_perkm_1": 25, "zone_max_1": 30,
            "zone_name_2": "Регионы", "zone_code_2": "region", "zone_fee_2": 3500,
            "zone_free_2": 0, "zone_perkm_2": 30, "zone_max_2": 400,
            "time_night": 1.8, "cond_power_line": 1.4, "addon_rigger": 750,
            "discount_max": 0.25, "conditions_cap": 1.6}
    post(BASE + "/setup/pricing", **form)
    db.refresh(tenant)
    p = pricing_of(tenant)
    check(len(p["zones"]) == 3 and p["zones"][0]["fee"] == 2000, "зоны подачи сохранены формой",
          f"зон {len(p['zones'])}, первая плата {p['zones'][0]['fee']}")
    check(p["time"]["night"] == 1.8 and p["conditions"]["power_line"] == 1.4,
          "коэффициенты времени и условий сохранены")
    check(p["addons"]["rigger"] == 750, "цена допуслуги сохранена")

    from portal.services.pricing import zone_for
    check(zone_for(tenant, 10)["fee"] == 2000, "зона для расстояния 10 км берётся из настроек",
          f"плата {zone_for(tenant, 10)['fee']}")
    # у машины может быть своя плата за подачу, она перекрывает зону — обнуляем на время проверки
    own_fee, eq_rate.mobilization_fee = eq_rate.mobilization_fee, 0
    db.commit()
    zone_quote = calculate(tenant, eq_rate, start=when, hours=4, distance_km=10, conditions=[])
    delivery = next((l["amount"] for l in zone_quote["lines"] if "одач" in l["title"]), 0)
    check(delivery == 2000, "в расчёте подача считается по плате зоны из настроек", str(delivery))
    eq_rate.mobilization_fee = own_fee
    db.commit()
    check(base_quote["total"] != zone_quote["total"], "итог заказа меняется вслед за прайсом",
          f"{base_quote['total']} → {zone_quote['total']}")

    r = c.get(BASE + "/setup")
    state = setup_state.progress(tenant)
    pricing_row = [x for x in state["rows"] if x["key"] == "pricing"][0]
    check(pricing_row["state"] in ("ok", "partial") and pricing_row["metrics"]["custom"],
          "в сводке прайс отмечен как свой", pricing_row["note"])

    # ---------------------------------------------------------------- реквизиты
    section("4. РЕКВИЗИТЫ И ПОЧТА")
    post(BASE + "/setup/company", action="save", legal_name="SA «Dimecon 11»", idno="1003600012345",
         vat_code="0301234", bank_name="BC «Moldindconbank» SA", bank_iban="MD24AG000225100013104168",
         bank_swift="MOLDMD2X", legal_address="mun. Chișinău, str. Uzinelor 21",
         director_name="Ион Попеску", accountant_name="Мария Русу",
         invoice_due_days=7, vat_rate=20, prefix_invoice="СЧ", prefix_act="АКТ", prefix_quote="КП")
    db.refresh(tenant)
    check(tenant.bank_iban.startswith("MD24") and tenant.director_name == "Ион Попеску",
          "реквизиты сохранены", tenant.bank_name)
    check(tenant.invoice_due_days == 7, "срок оплаты по умолчанию сохранён", "7 дней")

    doc = invoicing.create_invoice(tenant, amount=1000,
                                   lines=[{"title": "Проверка реквизитов", "qty": 1, "unit": "усл.",
                                           "price": 1000, "amount": 1000}])
    check((doc.due_at - doc.issued_at).days == 7, "новый счёт получает срок оплаты из настроек",
          f"{doc.issued_at} → {doc.due_at}")
    check(doc.number.startswith("СЧ-"), "номер счёта использует префикс из настроек", doc.number)

    order = db.query(Order).filter_by(tenant_id=tenant.id).order_by(Order.id.desc()).first()
    from portal.services.documents import invoice_pdf
    pdf = invoice_pdf(tenant, order, doc)
    text = ""
    try:
        from pypdf import PdfReader
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    except Exception as exc:  # noqa: BLE001 — без pypdf ограничимся размером
        out(f"  (текст PDF не читается: {exc})")
    if text:
        check("MD24AG000225100013104168" in text.replace(" ", ""), "IBAN печатается в счёте")
        check("Ион Попеску" in text, "подпись руководителя печатается в счёте")
        check("0301234" in text, "код плательщика НДС печатается в счёте")
    else:
        check(len(pdf) > 10000, "счёт с реквизитами формируется", f"{len(pdf)} байт")

    r = post(BASE + "/setup/company", action="smtp_test")
    check(r.status_code == 200, "проверка почтового сервера отрабатывает без сбоя")
    r = post(BASE + "/setup/company", action="mail_test", to="office@example.com")
    check(r.status_code == 200 and ("queued" in r.get_data(as_text=True) or "sent" in r.get_data(as_text=True)),
          "проверочное письмо ставится в очередь или отправляется")

    # ---------------------------------------------------------------- домен
    section("5. СВОЙ ДОМЕН")
    check(dom.normalize(" HTTPS://Crane.Dimecon.MD/path ") == "crane.dimecon.md",
          "адрес приводится к чистому имени", dom.normalize(" HTTPS://Crane.Dimecon.MD/path "))
    check(dom.validate("не домен") != "" and dom.validate("dimecon.md") == "",
          "опечатки в домене отклоняются")

    host = "proverka-domena.dimecon.md"
    db.query(Domain).filter_by(host=host).delete()
    db.commit()
    post(BASE + "/setup/domain", action="add", host=host)
    d = db.query(Domain).filter_by(tenant_id=tenant.id, host=host).first()
    check(d is not None, "домен добавлен", host)

    rows = dom.instructions(tenant, host, "eminescu.md")
    check(any(r["type"] == "CNAME" for r in rows), "для поддомена подсказывается запись CNAME",
          rows[0]["value"] if rows else "")
    apex_rows = dom.instructions(tenant, "dimecon.md", "eminescu.md")
    check(any(r["type"] == "A" for r in apex_rows), "для корневого домена подсказывается запись A")

    dom.check(tenant, d, "eminescu.md")
    check(d.verified is False and d.check_note, "непривязанный домен помечается неподтверждённым",
          d.check_note[:60])

    post(BASE + "/setup/domain", action="delete", id=d.id)
    check(db.query(Domain).filter_by(host=host).count() == 0, "домен удаляется из кабинета")

    # ---------------------------------------------------------------- скрипты
    section("6. СКРИПТЫ, ПРИМЕНЯЮЩИЕ НАСТРОЙКИ")
    code, text_out = script("settings_report.py", "dimecon")
    check("Грузовые таблицы" in text_out and "готовность" in text_out,
          "settings_report.py печатает готовность компании", text_out.splitlines()[1][:60] if text_out else "")

    code, text_out = script("pricing_tool.py", "show", "--tenant", "dimecon")
    check(code == 0 and "Зоны подачи" in text_out, "pricing_tool.py показывает прайс и ставки")

    code, text_out = script("pricing_tool.py", "rates-export", "../docs/generated/rates.csv", "--tenant", "dimecon")
    check(code == 0 and "выгружены" in text_out, "pricing_tool.py выгружает ставки в CSV")
    code, text_out = script("pricing_tool.py", "rates-import", "../docs/generated/rates.csv", "--tenant", "dimecon")
    check(code == 0 and "предварительный" in text_out,
          "pricing_tool.py без --apply только показывает изменения")

    code, text_out = script("company_tool.py", "show", "--tenant", "dimecon")
    check("IBAN" in text_out and "MD24" in text_out, "company_tool.py показывает реквизиты")

    import tempfile
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    tmp.write(csv_text)
    tmp.close()
    code, text_out = script("import_load_charts.py", tmp.name, "--tenant", "dimecon")
    check("предварительный разбор" in text_out, "import_load_charts.py без --apply ничего не пишет")

    code, text_out = script("domain_check.py", "--tenant", "dimecon", "--host", "eminescu.md")
    check("домен" in text_out.lower() or "DNS" in text_out, "domain_check.py отрабатывает")

    code, text_out = script("erp_sync.py", "check", "--tenant", "dimecon")
    check("OfficePlus" in text_out and "Oracle" in text_out,
          "erp_sync.py проверяет оба подключения", text_out.strip().splitlines()[0][:70] if text_out else "")

    # ---------------------------------------------------------------- доступ
    section("7. ПРАВА И ИЗОЛЯЦИЯ")
    other_tenant = db.query(Tenant).filter(Tenant.slug != "dimecon").first()
    for path in ("/setup", "/setup/pricing", "/setup/company", "/setup/domain"):
        r = c.get(f"/s/{other_tenant.slug}/admin{path}")
        check(r.status_code == 403, f"чужой кабинет закрыт: {path}", f"HTTP {r.status_code}")

    login("client@example.com")
    r = c.get(BASE + "/setup")
    check(r.status_code == 403, "клиент не попадает в настройки компании", f"HTTP {r.status_code}")
    login()

    # ---------------------------------------------------------------- возврат прайса
    section("8. ВОЗВРАТ ИСХОДНОГО СОСТОЯНИЯ")
    tenant.pricing = original_pricing
    eq_rate.hourly_rate = old_rate
    db.commit()
    check(pricing_of(tenant)["zones"][0]["fee"] == DEFAULT_PRICING["zones"][0]["fee"],
          "прайс возвращён к исходному, чтобы прочие проверки считали те же суммы")
    check(db.query(Equipment).get(eq_rate.id).hourly_rate == old_rate, "ставка машины возвращена")

out("")
out(f"ИТОГО: пройдено {passed}, ошибок {failed}")
with open("../docs/test_settings.log", "w", encoding="utf-8") as f:
    f.write("\n".join(LOG) + "\n")
sys.exit(1 if failed else 0)
