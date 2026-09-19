"""Демо-данные управленческих модулей: объекты, продажи, закупки, счета, таблицы, документы.

Вызывается при первом запуске и отдельно скриптом tools/seed_erp.py.
Идемпотентно: если у компании уже есть объект с задачами, второй раз ничего не создаётся.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .db import SessionLocal as db
from .models import (Contact, DocRequest, DocRule, Equipment, Partner, Product, Project,
                     PurchaseAgreement, RecurringPlan, ReorderRule, SalesTemplate, Service,
                     Sheet, Task, Tenant, User, Vendor)
from .services import docs_ws, invoicing, projects as prj, purchase as pur, sales as sls, sheets as sh


def seed_erp(tenant: Tenant) -> dict:
    if db.query(Task).filter_by(tenant_id=tenant.id).count():
        return {"skipped": True}

    today = date.today()
    owner = (db.query(User).join(User.memberships)
             .filter_by(tenant_id=tenant.id).order_by(User.id).first())
    partner = db.query(Partner).filter_by(tenant_id=tenant.id).first()
    contact = db.query(Contact).filter_by(tenant_id=tenant.id).first()
    fleet = db.query(Equipment).filter_by(tenant_id=tenant.id).order_by(Equipment.capacity_t.desc()).all()
    services = db.query(Service).filter_by(tenant_id=tenant.id).order_by(Service.sort).all()
    products = db.query(Product).filter_by(tenant_id=tenant.id).all()
    stats = {}

    # ---------------------------------------------------------------- поставщики
    vendors = []
    for name, contact_name, phone, email, days, lead in [
        ("Металлопрокат МД", "Андрей Быков", "+37322112233", "sales@metal.md", 30, 5),
        ("Трос и Строп", "Виктория Лунгу", "+37322445566", "office@tros.md", 14, 3),
        ("Автозапчасти Плюс", "Сергей Гусев", "+37322778899", "info@autoparts.md", 7, 2),
    ]:
        v = Vendor(tenant_id=tenant.id, name=name, contact_name=contact_name, phone=phone,
                   email=email, payment_days=days, lead_days=lead, rating=4.5)
        db.add(v)
        vendors.append(v)
    db.flush()
    db.add(PurchaseAgreement(tenant_id=tenant.id, vendor_id=vendors[0].id,
                             name="Металлопрокат 2026, годовая цена", kind="blanket",
                             valid_from=today.replace(month=1, day=1), valid_to=today.replace(month=12, day=31),
                             terms={"discount_pct": 7, "payment_days": 30}))
    db.commit()
    stats["vendors"] = len(vendors)

    # ---------------------------------------------------------------- объекты
    tmpl = Project(tenant_id=tenant.id, name="Типовой монтаж башенного крана", is_template=True,
                   code="TPL-01", stage="planning", hour_cost=180, hour_rate=450,
                   budget_amount=210000, planned_cost=140000, starts_at=today,
                   notes="Шаблон: подготовка площадки, монтаж, пусконаладка, сдача инспекции.")
    db.add(tmpl)
    db.flush()
    seq = 0
    parent_map = {}
    for title, hours, offset, length, milestone, amount in [
        ("Подготовка площадки", 24, 0, 4, False, 0),
        ("Монтаж башни и стрелы", 64, 4, 6, False, 0),
        ("Пусконаладка и обкатка", 16, 10, 2, False, 0),
        ("Сдача инспекции, акт", 8, 12, 1, True, 70000),
    ]:
        seq += 10
        t = Task(tenant_id=tenant.id, project_id=tmpl.id, title=title, planned_hours=hours,
                 starts_on=today + timedelta(days=offset), due_on=today + timedelta(days=offset + length),
                 is_milestone=milestone, milestone_amount=amount, sequence=seq, stage="todo")
        db.add(t)
        db.flush()
        parent_map[title] = t
    parent_map["Монтаж башни и стрелы"].depends_on_id = parent_map["Подготовка площадки"].id
    parent_map["Пусконаладка и обкатка"].depends_on_id = parent_map["Монтаж башни и стрелы"].id
    db.commit()

    project = prj.from_template(tenant, tmpl, name="ЖК «Рышкановка», башенный кран КБ-403А",
                                partner_id=partner.id if partner else None,
                                contact_id=contact.id if contact else None,
                                starts_at=today - timedelta(days=9))
    project.address = "Кишинёв, ул. Киевская, 12"
    project.stage = "works"
    project.budget_amount, project.planned_cost = 240000, 150000
    db.commit()

    tasks = db.query(Task).filter_by(project_id=project.id).order_by(Task.sequence).all()
    if tasks:
        prj.move_task(tasks[0], "done")
        if len(tasks) > 1:
            prj.move_task(tasks[1], "doing")
        db.add(Task(tenant_id=tenant.id, project_id=project.id, parent_id=tasks[1].id if len(tasks) > 1 else None,
                    title="Проверить анкерные болты", planned_hours=4, stage="todo",
                    due_on=today + timedelta(days=2), priority=1, sequence=25))
        db.add(Task(tenant_id=tenant.id, project_id=project.id, title="Еженедельный отчёт заказчику",
                    planned_hours=1, stage="todo", due_on=today + timedelta(days=3),
                    recurrence={"every": 1, "unit": "week"}, sequence=100))
        db.commit()

    second = Project(tenant_id=tenant.id, name="Склад «Индустриальная 46», перенос оборудования",
                     code="OBJ-02", address="Кишинёв, ул. Индустриальная, 46", stage="planning",
                     status="active", budget_amount=86000, planned_cost=51000, hour_cost=160,
                     hour_rate=420, starts_at=today + timedelta(days=5),
                     ends_at=today + timedelta(days=25),
                     contact_id=contact.id if contact else None,
                     manager_id=owner.id if owner else None)
    db.add(second)
    db.commit()
    stats["projects"] = 3

    for day_offset, hours, note in [(-8, 8, "Подготовка площадки, планировка"),
                                    (-7, 8, "Разгрузка секций башни"),
                                    (-6, 6.5, "Монтаж секций 1–4"),
                                    (-2, 8, "Монтаж стрелы"),
                                    (-1, 4, "Запасовка троса")]:
        prj.log_time(tenant, project, hours=hours, user_id=owner.id if owner else None,
                     work_date=today + timedelta(days=day_offset), note=note)
    stats["timesheets"] = 5

    # ---------------------------------------------------------------- продажи
    tpl_lines = []
    if fleet:
        tpl_lines.append({"name": f"Работа крана {fleet[0].brand} {fleet[0].model}", "qty": 8, "unit": "ч",
                          "price": fleet[0].hourly_rate or 2200, "cost": (fleet[0].hourly_rate or 2200) * 0.55,
                          "kind": "equipment", "ref_id": fleet[0].id})
    tpl_lines += [
        {"name": "Подача и возврат техники", "qty": 1, "unit": "усл.", "price": 2500, "cost": 1400},
        {"name": "Стропальщик", "qty": 8, "unit": "ч", "price": 150, "cost": 90},
        {"name": "Ночная смена", "qty": 8, "unit": "ч", "price": 300, "cost": 180, "optional": True},
    ]
    template = SalesTemplate(tenant_id=tenant.id, name="Смена автокрана под ключ", lines=tpl_lines,
                             note="Оплата: 50 % аванс, остаток по акту. Минимальная смена — 4 часа.")
    db.add(template)
    db.commit()

    so1 = sls.create(tenant, contact_id=contact.id if contact else None, template=template,
                     assignee_id=owner.id if owner else None)
    sls.send(so1)
    sls.accept(so1, by_name=contact.name if contact else "Клиент")
    sls.confirm(so1)

    so2 = sls.create(tenant, partner_id=partner.id if partner else None, template=template,
                     assignee_id=owner.id if owner else None)
    so2.project_id = project.id
    if services:
        sls.add_from_catalog(so2, "service", services[0].id, 1)
    sls.recalc(so2)
    sls.send(so2)
    db.commit()

    so3 = sls.create(tenant, contact_id=contact.id if contact else None,
                     assignee_id=owner.id if owner else None)
    sls.add_line(so3, name="Демонтаж металлоконструкций", qty=1, unit="усл.", price=48000, cost=31000)
    sls.add_line(so3, name="Вывоз лома", qty=12, unit="т", price=900, cost=520, is_optional=True)
    sls.recalc(so3)
    db.commit()
    stats["sales"] = 3

    # ---------------------------------------------------------------- закупки
    po1 = pur.create(tenant, vendor_id=vendors[1].id, project_id=project.id,
                     note="Тросы и стропы для монтажа", created_by=owner.id if owner else None)
    pur.add_line(po1, name="Канат стальной ЛК-Р 16 мм", qty=120, unit="м", price=95)
    pur.add_line(po1, name="Строп 4СК-5,0", qty=2, unit="шт", price=2400)
    pur.send(po1)
    pur.confirm(po1)
    pur.receive(po1)
    pur.bill(po1, due_on=today + timedelta(days=7))
    pur.pay(po1, amount=round(po1.amount_total * 0.5, 2), user_id=owner.id if owner else None)

    po2 = pur.create(tenant, vendor_id=vendors[0].id, project_id=project.id,
                     note="Металл для закладных", created_by=owner.id if owner else None)
    pur.add_line(po2, name="Швеллер 16П", qty=1.8, unit="т", price=21500)
    pur.send(po2)
    db.commit()
    stats["purchases"] = 2

    if products:
        db.add(ReorderRule(tenant_id=tenant.id, product_id=products[0].id, vendor_id=vendors[1].id,
                           min_qty=5, max_qty=25))
        db.commit()

    # ---------------------------------------------------------------- счета
    inv1 = invoicing.from_sales(tenant, so1, advance_pct=50, payment_days=5)
    invoicing.register_payment(tenant, inv1, amount=inv1.amount, on=today - timedelta(days=2),
                               method="bank", reference="п/п 145", user_id=owner.id if owner else None)
    inv2 = invoicing.create_invoice(tenant, amount=64800,
                                    lines=[{"title": "Работа крана GROVE GMK 5100, 8 ч", "qty": 8,
                                            "unit": "ч", "price": 8100, "amount": 64800}],
                                    contact_id=contact.id if contact else None,
                                    partner_id=partner.id if partner else None,
                                    project_id=project.id, payment_days=-12,
                                    issued_on=today - timedelta(days=42))
    invoicing.refresh_status(inv2)
    milestone = db.query(Task).filter_by(project_id=project.id, is_milestone=True).first()
    if milestone:
        invoicing.from_milestone(tenant, milestone)
    db.add(RecurringPlan(
        tenant_id=tenant.id, name="Обслуживание ГПМ, ежемесячно",
        partner_id=partner.id if partner else None, amount=12000, period="month",
        day_of_month=5, next_run=today + timedelta(days=3), payment_days=10,
        lines=[{"title": "Техобслуживание ГПМ", "qty": 1, "unit": "мес.", "price": 12000, "amount": 12000}]))
    db.commit()
    stats["invoices"] = 3

    # ---------------------------------------------------------------- таблицы
    for name in ("Отчёт по продажам", "Загрузка парка"):
        tpl = sh.TEMPLATES[name]
        db.add(Sheet(tenant_id=tenant.id, name=name, cells=dict(tpl["cells"]),
                     charts=list(tpl.get("charts", [])), formats=dict(tpl.get("formats", {})),
                     updated_by=owner.id if owner else None))
    db.commit()
    stats["sheets"] = 2

    # ---------------------------------------------------------------- документы
    folders = docs_ws.ensure_folders(tenant)
    by_name = {f.name: f for f in folders}
    db.add(DocRule(tenant_id=tenant.id, name="Счета — в папку «Акты и счета»", match_tag="счёт",
                   action="move", params={"folder_id": by_name.get("Акты и счета").id
                                          if by_name.get("Акты и счета") else None}))
    db.add(DocRule(tenant_id=tenant.id, name="Чертежи — пометить тегом", match_mime="pdf",
                   action="tag", params={"tags": "чертёж"}))
    db.add(DocRequest(tenant_id=tenant.id, name="Доверенность на получение техники",
                      to_email=contact.email if contact and contact.email else "client@example.com",
                      to_name=contact.name if contact else "Клиент",
                      folder_id=by_name.get("Договоры").id if by_name.get("Договоры") else None,
                      due_on=today + timedelta(days=5), entity="project", entity_id=project.id))
    db.commit()
    stats["folders"] = len(folders)
    return stats
