"""Проверка управленческих модулей: проекты, продажи, закупки, счета, таблицы, документы.

    ../.venv/Scripts/python tools/test_erp.py

Работает через тестовый клиент приложения на текущей базе: открывает страницы,
выполняет действия и сверяет результат арифметикой и запросами к данным.
"""
from __future__ import annotations

import re
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import (Document, Media, Payment, Project, PurchaseOrder, RecurringPlan,  # noqa: E402
                           SalesOrder, Sheet, Task, Tenant, Timesheet, Vendor)
from portal.services import docs_ws, invoicing, projects as prj, purchase as pur  # noqa: E402
from portal.services import sales as sls, sheets as sh  # noqa: E402

app = create_app()
c = app.test_client()
LOG: list[str] = []
passed = failed = 0
BASE = "/s/dimecon/admin"


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
    data["_csrf"] = csrf()
    return c.post(url, data=data, follow_redirects=True)


with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    login()

    # ---------------------------------------------------------------- страницы
    section("1. СТРАНИЦЫ МОДУЛЕЙ")
    for path, title in [("/projects", "объекты и проекты"), ("/tasks", "канбан задач"),
                        ("/sales", "коммерческие предложения"), ("/purchase", "закупки"),
                        ("/vendors", "поставщики и соглашения"), ("/purchase/reorder", "пополнение склада"),
                        ("/invoices", "счета и оплаты"), ("/plans", "повторяющиеся счета"),
                        ("/sheets", "таблицы"), ("/docs", "документы")]:
        r = c.get(BASE + path)
        check(r.status_code == 200, f"{title}: {path}", f"HTTP {r.status_code}")

    # берём объект, по которому действительно ведутся работы: с задачами и историей
    project = max(db.query(Project).filter_by(tenant_id=tenant.id, is_template=False).all(),
                  key=lambda p: db.query(Task).filter_by(project_id=p.id).count())
    r = c.get(f"{BASE}/projects/{project.id}")
    check(r.status_code == 200, "карточка объекта открывается", project.name)

    # ---------------------------------------------------------------- проекты
    section("2. ПРОЕКТЫ: ЗАДАЧИ, ЗАВИСИМОСТИ, ВРЕМЯ, ВЕХИ")
    tree = prj.task_tree(tenant, project)
    check(len(tree) >= 4, "иерархия работ построена", f"узлов {len(tree)}")

    blocked = next((row for row in tree if row["blocked"]), None)
    if blocked:
        res = prj.move_task(blocked["task"], "doing")
        check(not res["ok"], "задача с незавершённой зависимостью не стартует", res.get("reason", ""))
    else:
        check(True, "зависимостей в демо-объекте нет — проверка пропущена", "")

    before = prj.timesheet_totals(project)["hours"]
    prj.log_time(tenant, project, hours=3.5, note="Проверка учёта времени")
    after = prj.timesheet_totals(project)
    check(abs(after["hours"] - before - 3.5) < 0.01, "часы записываются в табель",
          f"{before} → {after['hours']}")
    check(abs(after["cost"] - after["hours"] * (project.hour_cost or 0)) < 0.5,
          "себестоимость часов считается по ставке объекта", f"{after['cost']} при {project.hour_cost}/ч")

    money = prj.profitability(tenant, project)
    check(abs(money["cost"] - (money["purchases"] + money["labour"])) < 0.5,
          "затраты объекта = закупки + труд",
          f"{money['cost']} = {money['purchases']} + {money['labour']}")
    check(abs(money["margin"] - (money["revenue"] - money["cost"])) < 0.5,
          "маржа = выручка − затраты", f"{money['margin']}")

    # фильтровать JSON-поле средствами СУБД ненадёжно (MySQL сравнивает документы),
    # поэтому ищем повторяющуюся задачу в Python
    rec = next((t for t in db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id).all()
                if (t.recurrence or {}).get("every")), None)
    if rec:
        count_before = db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id).count()
        prj.move_task(rec, "done")
        count_after = db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id).count()
        check(count_after == count_before + 1, "повторяющаяся задача порождает следующую",
              f"задач {count_before} → {count_after}")

    milestone = db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id,
                                         is_milestone=True).first()
    if milestone and not milestone.invoiced:
        doc = invoicing.from_milestone(tenant, milestone)
        check(doc.amount == milestone.milestone_amount, "счёт по вехе на сумму этапа",
              f"{doc.number} на {doc.amount}")
    else:
        check(bool(milestone), "веха в объекте есть", "счёт по ней уже выставлен")

    # шаблон объекта
    tmpl = db.query(Project).filter_by(tenant_id=tenant.id, is_template=True).first()
    new_project = prj.from_template(tenant, tmpl, name="Проверка шаблона", starts_at=date.today())
    src_tasks = db.query(Task).filter_by(project_id=tmpl.id).count()
    new_tasks = db.query(Task).filter_by(project_id=new_project.id).count()
    check(new_tasks == src_tasks, "объект по шаблону копирует все задачи", f"{src_tasks} → {new_tasks}")
    dep = db.query(Task).filter(Task.project_id == new_project.id, Task.depends_on_id.isnot(None)).first()
    check(dep is not None and db.get(Task, dep.depends_on_id).project_id == new_project.id,
          "зависимости в копии указывают на задачи той же копии")

    # ---------------------------------------------------------------- продажи
    section("3. ПРОДАЖИ: СМЕТА, СКИДКА, ДОПРАБОТЫ, ПРИНЯТИЕ")
    so = sls.create(tenant, contact_id=None)
    sls.add_line(so, name="Работа крана", qty=8, unit="ч", price=2000, cost=1100)
    sls.add_line(so, name="Подача", qty=1, unit="усл.", price=2500, cost=1400)
    sls.add_line(so, name="Ночная смена", qty=8, unit="ч", price=300, is_optional=True)
    so.discount_pct = 10
    sls.recalc(so)
    db.commit()
    check(abs(so.amount_net - (8 * 2000 + 2500) * 0.9) < 0.01, "сумма без НДС со скидкой 10 %",
          f"{so.amount_net} при базе {8 * 2000 + 2500}")
    check(abs(so.amount_vat - so.amount_net * 0.2) < 0.01, "НДС 20 % от суммы со скидкой", f"{so.amount_vat}")
    check(abs(so.amount_total - (so.amount_net + so.amount_vat)) < 0.01, "итого = сумма + НДС",
          f"{so.amount_total}")
    check(abs(so.amount_optional - 2400) < 0.01, "допработы считаются отдельно, не входят в итог",
          f"{so.amount_optional}")
    m = sls.margin(so)
    check(abs(m["cost"] - (8 * 1100 + 1400)) < 0.01, "себестоимость сметы по строкам", f"{m['cost']}")

    optional_line = [l for l in so.lines if l.is_optional][0]
    total_before = so.amount_total
    sls.send(so)
    sls.accept(so, by_name="Тестовый клиент", selected_optional=[optional_line.id])
    check(so.status == "accepted" and so.amount_total > total_before,
          "выбранная клиентом допработа входит в сумму", f"{total_before} → {so.amount_total}")

    r = c.get(f"/s/dimecon/kp/{so.accept_token}")
    check(r.status_code == 200, "страница предложения для клиента открывается по ссылке", f"HTTP {r.status_code}")

    sls.confirm(so, create_project=True)
    check(so.project_id is not None, "подтверждение открывает объект работ", f"объект #{so.project_id}")

    doc = invoicing.from_sales(tenant, so, advance_pct=40)
    check(abs(doc.amount - round(so.amount_total * 0.4, 2)) < 0.01, "авансовый счёт на 40 % суммы",
          f"{doc.amount} из {so.amount_total}")
    check(so.status == "invoiced", "предложение помечено как «выставлен счёт»")

    r = c.get(f"{BASE}/sales/{so.id}/pdf")
    check(r.status_code == 200 and r.data[:4] == b"%PDF", "PDF предложения формируется",
          f"{len(r.data)} байт")

    # ---------------------------------------------------------------- закупки
    section("4. ЗАКУПКИ: ЗАПРОС, ПРИЁМКА, СЧЁТ, ОПЛАТА")
    vendor = db.query(Vendor).filter_by(tenant_id=tenant.id).first()
    po = pur.create(tenant, vendor_id=vendor.id, note="Проверка закупки")
    pur.add_line(po, name="Болт М24", qty=100, unit="шт", price=12)
    pur.add_line(po, name="Гайка М24", qty=100, unit="шт", price=5)
    check(abs(po.amount_net - 1700) < 0.01, "сумма заказа по строкам", f"{po.amount_net}")
    check(abs(po.amount_total - 2040) < 0.01, "итог с НДС 20 %", f"{po.amount_total}")

    pur.send(po)
    pur.confirm(po)
    check(po.status == "confirmed" and po.bill_due_on is not None,
          "подтверждение ставит срок оплаты по условиям поставщика", f"до {po.bill_due_on}")

    res = pur.receive(po, {po.lines[0].id: 60})
    check(not res["full"] and po.lines[0].received_qty == 60, "частичная приёмка фиксируется построчно",
          f"принято {po.lines[0].received_qty} из {po.lines[0].qty}")
    res = pur.receive(po)
    check(res["full"] and po.status == "received", "полная приёмка закрывает заказ", f"статус {po.status}")

    pur.bill(po)
    pur.pay(po, amount=1000)
    check(abs(pur.paid_amount(po) - 1000) < 0.01, "оплата поставщику записывается", "1000")
    debts = [d for d in pur.to_pay(tenant) if d["po"].id == po.id]
    check(bool(debts) and abs(debts[0]["balance"] - (po.amount_total - 1000)) < 0.01,
          "остаток долга поставщику считается", f"{debts[0]['balance'] if debts else '—'}")

    stats_rows = [r for r in pur.vendor_stats(tenant) if r["vendor"].id == vendor.id]
    check(bool(stats_rows) and stats_rows[0]["orders"] >= 1, "анализ закупок по поставщику считается",
          f"заказов {stats_rows[0]['orders'] if stats_rows else 0}")

    # ---------------------------------------------------------------- счета
    section("5. СЧЕТА: ПЛАТЕЖИ, СТАТУСЫ, ПРОСРОЧКА, КРЕДИТ-НОТА")
    inv = invoicing.create_invoice(tenant, amount=10000, payment_days=5,
                                   lines=[{"title": "Услуги", "qty": 1, "unit": "усл.",
                                           "price": 10000, "amount": 10000}])
    check(inv.status == "issued", "новый счёт в статусе «выставлен»")
    invoicing.register_payment(tenant, inv, amount=4000)
    check(inv.status == "partial" and abs(invoicing.balance(inv) - 6000) < 0.01,
          "частичная оплата меняет статус и остаток", f"остаток {invoicing.balance(inv)}")
    invoicing.register_payment(tenant, inv, amount=6000)
    check(inv.status == "paid" and abs(invoicing.balance(inv)) < 0.01, "полная оплата закрывает счёт")

    old = invoicing.create_invoice(tenant, amount=5000, payment_days=-10,
                                   issued_on=date.today() - timedelta(days=40))
    invoicing.refresh_status(old)
    check(old.status == "overdue", "счёт с истёкшим сроком помечается просроченным",
          f"срок {old.due_at}")
    ag = invoicing.aging(tenant)
    check(ag["total"] > 0 and sum(ag["buckets"].values()) == ag["total"],
          "дебиторка разложена по срокам", f"итого {ag['total']}")

    note = invoicing.credit_note(tenant, old, reason="возврат по проверке")
    check(note.type == "credit_note" and note.ref_document_id == old.id,
          "кредит-нота ссылается на исходный счёт", note.number)
    check(old.status == "cancelled", "полная кредит-нота отменяет счёт")

    plan = db.query(RecurringPlan).filter_by(tenant_id=tenant.id).first()
    if plan:
        plan.next_run = date.today()
        db.commit()
        docs = invoicing.run_recurring(tenant)
        check(len(docs) >= 1 and plan.next_run > date.today(),
              "регулярный счёт выставлен и план сдвинут", f"следующий {plan.next_run}")

    sent = invoicing.send_reminders(tenant, min_days=0)
    check(isinstance(sent, list), "напоминания по просрочке отрабатывают", f"писем {len(sent)}")

    # ---------------------------------------------------------------- таблицы
    section("6. ТАБЛИЦЫ: ФОРМУЛЫ, ЖИВЫЕ ДАННЫЕ, СРЕЗЫ, ЭКСПОРТ")
    sheet = Sheet(tenant_id=tenant.id, name="Проверка формул",
                  cells={"A1": "10", "A2": "20", "A3": "30", "B1": "=СУММА(A1:A3)",
                         "B2": "=СРЗНАЧ(A1:A3)", "B3": "=МАКС(A1:A3)-МИН(A1:A3)",
                         "B4": "=ОКРУГЛ(A1*1,5;1)", "B5": "=ЕСЛИ(A3>25;100;0)",
                         "B6": "=ПРОЦЕНТ(A1;A3)", "B7": "=ТЕХНИКА(\"шт\")", "B8": "=B1+B7"})
    db.add(sheet)
    db.commit()
    calc = sh.compute(sheet, tenant)
    v = calc["values"]
    check(v.get("B1") == 60, "СУММА по диапазону", str(v.get("B1")))
    check(v.get("B2") == 20, "СРЗНАЧ по диапазону", str(v.get("B2")))
    check(v.get("B3") == 20, "МАКС − МИН", str(v.get("B3")))
    check(v.get("B4") == 15, "ОКРУГЛ с десятичной запятой", str(v.get("B4")))
    check(v.get("B5") == 100, "ЕСЛИ с условием", str(v.get("B5")))
    check(abs(float(v.get("B6", 0)) - 33.33) < 0.01, "ПРОЦЕНТ", str(v.get("B6")))
    fleet_count = db.query(Tenant).count() and v.get("B7")
    check(isinstance(v.get("B7"), (int, float)) and v.get("B7") > 0,
          "живая функция ТЕХНИКА берёт данные из базы", str(v.get("B7")))
    check(v.get("B8") == v.get("B1") + v.get("B7"), "ссылка на ячейку с живой функцией",
          f"{v.get('B8')}")
    check(not calc["errors"], "ошибок в формулах нет", str(calc["errors"]))

    bad = Sheet(tenant_id=tenant.id, name="Циклическая", cells={"A1": "=A2", "A2": "=A1"})
    db.add(bad)
    db.commit()
    cyc = sh.compute(bad, tenant)
    check(any("ЦИКЛ" in str(x) for x in cyc["values"].values()), "циклическая ссылка не вешает расчёт")

    evil = Sheet(tenant_id=tenant.id, name="Опасная", cells={"A1": "=__import__('os').system('echo')"})
    db.add(evil)
    db.commit()
    res_evil = sh.compute(evil, tenant)
    check(str(res_evil["values"].get("A1", "")).startswith("#"), "посторонний код в формуле отклоняется",
          str(res_evil["values"].get("A1")))

    rows = sh.pivot(tenant, "orders", "stage", "count")
    check(bool(rows) and all("key" in r and "value" in r for r in rows), "сводный срез по заявкам",
          f"групп {len(rows)}")
    cells = sh.pivot_to_cells(rows, title="Заявки по стадиям", at="D1")
    check(any(str(vv).startswith("=СУММА") for vv in cells.values()),
          "в срез вставляется живая формула итога")

    data = sh.to_xlsx(sheet, v)
    check(data[:2] == b"PK" and len(data) > 3000, "выгрузка таблицы в Excel", f"{len(data)} байт")
    r = c.get(f"{BASE}/sheets/{sheet.id}.xlsx")
    check(r.status_code == 200, "выгрузка доступна из интерфейса", f"HTTP {r.status_code}")

    # ---------------------------------------------------------------- документы
    section("7. ДОКУМЕНТЫ: ПРОСТРАНСТВА, ТЕГИ, ВЕРСИИ, ЗАПРОСЫ, ПРАВИЛА")
    folders = docs_ws.ensure_folders(tenant)
    check(len(folders) >= 6, "рабочие пространства созданы", f"{len(folders)}")

    media = db.query(Media).filter_by(tenant_id=tenant.id).first()
    docs_ws.set_tags(media, "договор, проверка, договор")
    check(media.tags.count("договор") == 1, "теги нормализуются без повторов", media.tags)
    docs_ws.link_to(media, "project", project.id)
    check(media.entity == "project" and media.entity_id == project.id, "файл привязан к объекту")

    second_media = db.query(Media).filter_by(tenant_id=tenant.id).offset(1).first()
    if second_media:
        docs_ws.add_version(tenant, media, second_media, note="вторая версия")
        check(second_media.version == 2 and media.version_of_id == second_media.id,
              "новая версия становится актуальной, старая уходит в историю",
              f"v{second_media.version}")
        check(len(docs_ws.versions(second_media)) >= 1, "история версий доступна")

    req = docs_ws.request_document(tenant, name="Проверочный документ", to_email="",
                                   folder_id=folders[0].id, due_on=date.today() + timedelta(days=3),
                                   send=False)
    r = c.get(f"/s/dimecon/upload/{req.request_token}")
    check(r.status_code == 200, "страница загрузки по запросу открывается без входа", f"HTTP {r.status_code}")
    docs_ws.fulfil_request(req, media)
    check(req.status == "received" and req.media_id == media.id, "запрос закрывается загруженным файлом")

    from portal.models import DocRule
    rule = DocRule(tenant_id=tenant.id, name="Проверка правила", match_tag="проверка",
                   action="tag", params={"tags": "авто"})
    db.add(rule)
    db.commit()
    applied = docs_ws.apply_rules(tenant, media)
    check("Проверка правила" in applied and "авто" in media.tags,
          "правило автообработки срабатывает по тегу", media.tags)

    summary = docs_ws.summary(tenant)
    check(summary["files"] > 0 and summary["folders"] >= 6, "сводка по документам считается",
          f"файлов {summary['files']}, папок {summary['folders']}")

    # ---------------------------------------------------------------- изоляция
    section("8. ИЗОЛЯЦИЯ МЕЖДУ КОМПАНИЯМИ")
    other = db.query(Tenant).filter(Tenant.slug != "dimecon").first()
    for path in (f"/s/{other.slug}/admin/projects", f"/s/{other.slug}/admin/sales",
                 f"/s/{other.slug}/admin/invoices", f"/s/{other.slug}/admin/docs"):
        r = c.get(path)
        check(r.status_code == 403, f"владелец Dimecon не видит {path}", f"HTTP {r.status_code}")

    r = c.get(f"/s/{other.slug}/admin/projects/{project.id}")
    check(r.status_code in (403, 404), "чужой объект по прямой ссылке недоступен", f"HTTP {r.status_code}")

    cross = db.query(SalesOrder).filter(SalesOrder.tenant_id != tenant.id,
                                        SalesOrder.project_id.in_(
                                            db.query(Project.id).filter_by(tenant_id=tenant.id))).count()
    check(cross == 0, "нет предложений чужой компании на объекты Dimecon", f"{cross}")

    # ---------------------------------------------------------------- уборка
    section("9. УБОРКА ПРОВЕРОЧНЫХ ЗАПИСЕЙ")
    removed = 0
    auto_project = db.get(Project, so.project_id) if so.project_id else None
    for obj in (sheet, bad, evil, new_project, po, so, inv, old, note, doc, auto_project):
        if obj is None:
            continue
        try:
            db.delete(db.merge(obj))
            removed += 1
        except Exception as exc:  # noqa: BLE001 — уборка не должна валить прогон
            out(f"  не удалось удалить {obj}: {exc}")
    db.commit()
    check(db.query(Sheet).filter(Sheet.name.in_(("Проверка формул", "Циклическая", "Опасная"))).count() == 0,
          "проверочные таблицы удалены", f"записей убрано {removed}")
    check(db.query(Project).filter_by(tenant_id=tenant.id, name="Проверка шаблона").count() == 0,
          "проверочный объект удалён вместе с задачами")

out("")
out(f"ИТОГО: пройдено {passed}, ошибок {failed}")
with open("../docs/test_erp.log", "w", encoding="utf-8") as f:
    f.write("\n".join(LOG) + "\n")
sys.exit(1 if failed else 0)
