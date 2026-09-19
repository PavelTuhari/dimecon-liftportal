"""Демо-данные: платформа, суперадмин, три компании с парком, услугами, заказами."""
from __future__ import annotations

from datetime import datetime, timedelta

from .auth import hash_password, verify_password
from .db import SessionLocal as db
from .models import (Activity, Booking, CaseStudy, Contact, Equipment, EquipmentCategory, LoadChart, Membership, Order,
                     Page, Partner, Product, Project, Review, Service, Shift, Tenant, User, i18n)


def _cat(tid, code, ru, ro, en, kind, sort):
    c = EquipmentCategory(tenant_id=tid, code=code, name=i18n(ru, ro, en), kind=kind, sort=sort)
    db.add(c); db.flush()
    return c


def _chart(eq, rows):
    for r, q, h in rows:
        db.add(LoadChart(equipment_id=eq.id, radius_m=r, capacity_t=q, height_m=h))


def seed_tenant_defaults(tenant: Tenant, demo: bool = True):
    """Базовые категории, услуги и страницы — чтобы новая компания не получила пустой сайт."""
    tid = tenant.id
    cats = {
        "mobile": _cat(tid, "mobile_crane", "Автокраны", "Automacarale", "Mobile cranes", "crane", 1),
        "tower": _cat(tid, "tower_crane", "Башенные краны", "Macarale turn", "Tower cranes", "crane", 2),
        "crawler": _cat(tid, "crawler_crane", "Гусеничные краны", "Macarale pe șenile", "Crawler cranes", "crane", 3),
        "trailer": _cat(tid, "semitrailer", "Полуприцепы и тралы", "Semiremorci și trailere", "Semitrailers", "transport", 4),
    }
    services = [
        ("crane_services", "🏗", "Услуги автокранами и башенными кранами", "Servicii cu automacarale și macarale turn", "Mobile & tower crane services", 1200, 1),
        ("oversize", "🛣", "Перевозка негабаритных и тяжёлых грузов", "Transport agabaritic", "Oversize & heavy transport", 45, 2),
        ("tower_assembly", "🔧", "Монтаж и демонтаж башенных кранов", "Montarea și demontarea macaralelor turn", "Tower crane assembly", 15000, 3),
        ("rental", "📅", "Аренда кранов на объект", "Închirierea macaralelor", "Long-term crane rental", 95000, 4),
        ("inspection", "🔍", "Диагностика и техническое освидетельствование ГПМ", "Diagnosticarea și testarea tehnică", "Inspection & load testing", 4000, 5),
        ("maintenance", "🛠", "ТО и ремонт грузоподъёмных механизмов", "Deservirea și reparația", "Maintenance & repair", 800, 6),
        ("rigging", "⛓", "Изготовление грузозахватных приспособлений", "Dispozitive de prindere la comandă", "Custom rigging gear", 500, 7),
    ]
    for code, icon, ru, ro, en, price, sort in services:
        db.add(Service(tenant_id=tid, slug=code.replace("_", "-"), code=code, icon=icon, title=i18n(ru, ro, en),
                       short=i18n(f"{ru}: подача, оператор и документы включены.", f"{ro}: deplasare, operator și documente incluse.", f"{en}: dispatch, operator and documents included."),
                       body=i18n(f"<p>{ru}. Что входит: оператор, топливо, подача и возврат, страхование ГО. Не входит: простой по вине заказчика, разрешения.</p>"),
                       price_from=price, sort=sort))
    db.add(Page(tenant_id=tid, slug="terms", title=i18n("Условия аренды", "Condiții de închiriere", "Rental terms"),
                body=i18n("<p>Минимальная смена — 4 часа. Отмена более чем за 24 часа — бесплатно; за 6–24 часа — 30 % минимальной смены; менее 6 часов — полная минимальная смена и подача.</p>"), in_menu=True))
    tenant.hero = tenant.hero or {}
    tenant.hero.setdefault("title", i18n("Аренда кранов и спецтехники", "Închiriere macarale și utilaje", "Crane & heavy equipment rental"))
    tenant.hero.setdefault("subtitle", i18n("Рассчитайте стоимость онлайн и получите подтверждение за 15 минут.",
                                            "Calculați costul online și primiți confirmare în 15 minute.",
                                            "Get an instant online quote and confirmation within 15 minutes."))
    tenant.faq = tenant.faq or [
        {"q": i18n("Нужен ли стропальщик?", "Este nevoie de legător?", "Do I need a rigger?"),
         "a": i18n("Для большинства подъёмов — да. Его можно заказать вместе с краном, либо предоставить своего аттестованного.", "În majoritatea cazurilor — da.", "For most lifts — yes.")},
        {"q": i18n("Что входит в цену?", "Ce include prețul?", "What's included?"),
         "a": i18n("Оператор, топливо, подача и возврат техники, страхование. Отдельно — простой по вине заказчика и разрешения.", "Operator, combustibil, deplasare, asigurare.", "Operator, fuel, dispatch, insurance.")},
        {"q": i18n("Как быстро можете приехать?", "Cât de repede puteți veni?", "How fast can you arrive?"),
         "a": i18n("В городе — обычно на следующий день, срочно — в течение 4–6 часов с коэффициентом срочности.", "În oraș — de obicei a doua zi.", "In the city — usually next day.")},
    ]
    if demo:
        _demo_fleet(tenant, cats)
    db.flush()


def _demo_fleet(tenant: Tenant, cats):
    tid = tenant.id
    e1 = Equipment(tenant_id=tid, category_id=cats["mobile"].id, slug="ks-3577", brand="КС", model="3577", inventory_no="A-01", year=2008,
                   title=i18n("Автокран КС-3577, 14 т", "Automacara KS-3577, 14 t", "Mobile crane KS-3577, 14 t"),
                   description=i18n("Компактный автокран для городских условий: разгрузка, монтаж, подъём до 14 т."),
                   capacity_t=14, radius_m=13, height_m=14.5, outrigger_half_m=2.8, hourly_rate=900, min_hours=4, mobilization_fee=1200, sort=3,
                   photo_url="https://images.unsplash.com/photo-1581094288338-2314dddb7ece?w=900&q=70")
    e2 = Equipment(tenant_id=tid, category_id=cats["mobile"].id, slug="ks-4562", brand="КС", model="4562", inventory_no="A-02", year=2010,
                   title=i18n("Автокран КС-4562, 17 т", "Automacara KS-4562, 17 t", "Mobile crane KS-4562, 17 t"),
                   capacity_t=17, radius_m=11, height_m=12.2, outrigger_half_m=3.0, hourly_rate=1000, min_hours=4, mobilization_fee=1200, sort=4,
                   photo_url="https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=900&q=70")
    e3 = Equipment(tenant_id=tid, category_id=cats["mobile"].id, slug="grove-gmk-3055", brand="GROVE", model="GMK 3055", inventory_no="A-03", year=2015,
                   title=i18n("Автокран GROVE GMK 3055, 55 т", "Automacara GROVE GMK 3055, 55 t", "All-terrain crane GROVE GMK 3055, 55 t"),
                   description=i18n("Вседорожный кран 55 т, стрела 43 м. Универсальная машина для монтажа и строительства."),
                   capacity_t=55, radius_m=40, height_m=43, outrigger_half_m=3.6, hourly_rate=2200, min_hours=4, mobilization_fee=2500, sort=2,
                   photo_url="https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=900&q=70")
    e4 = Equipment(tenant_id=tid, category_id=cats["mobile"].id, slug="grove-gmk-5100", brand="GROVE", model="GMK 5100", inventory_no="A-04", year=2017,
                   title=i18n("Автокран GROVE GMK 5100, 100 т", "Automacara GROVE GMK 5100, 100 t", "All-terrain crane GROVE GMK 5100, 100 t"),
                   description=i18n("Самая мощная машина парка: 100 т, вылет 46 м, высота 68 м с гуськом."),
                   capacity_t=100, radius_m=46, height_m=68, outrigger_half_m=4.05, hourly_rate=4500, min_hours=8, mobilization_fee=4000, sort=1,
                   photo_url="https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=900&q=70")
    e5 = Equipment(tenant_id=tid, category_id=cats["tower"].id, slug="potain-mc-85b", brand="POTAIN", model="MC-85B", inventory_no="T-01", year=2012,
                   title=i18n("Башенный кран POTAIN MC-85B", "Macara turn POTAIN MC-85B", "Tower crane POTAIN MC-85B"),
                   description=i18n("Башенный кран 5 т, вылет 50 м, высота под крюк до 60 м. Аренда помесячно с монтажом."),
                   capacity_t=5, radius_m=50, height_m=60, hourly_rate=0, min_hours=0, mobilization_fee=45000, spec={"monthly_rate": 95000}, sort=5,
                   photo_url="https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=900&q=70")
    e6 = Equipment(tenant_id=tid, category_id=cats["trailer"].id, slug="faymonville-snt-4u", brand="FAYMONVILLE", model="SNT-4U", inventory_no="TR-01", year=2014,
                   title=i18n("Трал FAYMONVILLE SNT-4U, 63 т", "Trailer FAYMONVILLE SNT-4U, 63 t", "Lowbed FAYMONVILLE SNT-4U, 63 t"),
                   payload_kg=63000, platform_l_mm=7950, platform_w_mm=2740, hourly_rate=0, per_km_rate=45, mobilization_fee=3000, sort=6,
                   photo_url="https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=900&q=70")
    for e in (e1, e2, e3, e4, e5, e6):
        db.add(e)
    db.flush()
    _chart(e1, [(3, 14, 14.5), (5, 8.5, 14), (7, 5.2, 13), (9, 3.6, 12), (11, 2.6, 10), (13, 1.9, 8)])
    _chart(e2, [(3.5, 17, 12), (5, 10.5, 12), (7, 6.4, 11), (9, 4.3, 10), (11, 3.1, 8)])
    _chart(e3, [(3, 55, 43), (6, 30, 42), (10, 17.5, 41), (14, 11.2, 39), (18, 7.8, 36), (24, 4.9, 32), (30, 3.1, 26), (36, 1.9, 18), (40, 1.2, 12)])
    _chart(e4, [(3, 100, 50), (6, 62, 50), (10, 38, 49), (14, 26, 48), (18, 18.5, 46), (24, 12.4, 43), (30, 8.6, 39), (36, 6.1, 34), (42, 4.2, 27), (46, 3.1, 20)])
    _chart(e5, [(15, 5, 60), (25, 3.4, 60), (35, 2.2, 60), (45, 1.5, 60), (50, 1.2, 60)])

    for sku, cat, ru, ro, en, unit, price in [
        ("ROPE-12", "Стальные канаты", "Канат стальной Ø12 мм ГОСТ 2688", "Cablu de oțel Ø12 mm", "Steel wire rope Ø12 mm", "м", 38),
        ("ROPE-20", "Стальные канаты", "Канат стальной Ø20 мм ГОСТ 2688", "Cablu de oțel Ø20 mm", "Steel wire rope Ø20 mm", "м", 95),
        ("SLING-4SK-5", "Грузозахват", "Строп 4СК 5 т / 4 м", "Chingă 4SK 5 t / 4 m", "4-leg chain sling 5 t / 4 m", "шт", 2400),
        ("HOOK-3", "Аксессуары", "Крюк такелажный 3,2 т", "Cârlig 3,2 t", "Rigging hook 3.2 t", "шт", 320),
        ("TRAV-6", "Грузозахват", "Траверса линейная 6 м / 8 т", "Traversă 6 m / 8 t", "Spreader beam 6 m / 8 t", "шт", 18500),
    ]:
        db.add(Product(tenant_id=tid, sku=sku, slug=sku.lower(), category=cat, title=i18n(ru, ro, en), unit=unit, price=price, stock=25,
                       attributes={"standard": "ГОСТ/EN", "in_stock": True}))
    db.add(CaseStudy(tenant_id=tid, slug="chiller-roof", title=i18n("Чиллер 4,2 т на крышу бизнес-центра", "Chiller de 4,2 t pe acoperiș", "4.2 t chiller onto an office roof"),
                     body=i18n("<p>Подъём чиллера на 38 м через внутренний двор при вылете 32 м. Задействован GROVE GMK 5100 с гуськом, 6 часов работы, без перекрытия улицы.</p>"),
                     client_name="Business Center Skytower", location=tenant.city, year=2025, metrics={"weight_t": 4.2, "height_m": 38, "hours": 6},
                     image_url="https://images.unsplash.com/photo-1541976590-713941681591?w=900&q=70"))
    db.add(CaseStudy(tenant_id=tid, slug="tower-assembly", title=i18n("Монтаж башенного крана на жилом комплексе", "Montarea macaralei turn", "Tower crane assembly at a residential site"),
                     body=i18n("<p>Монтаж POTAIN MC-85B на 60 м за две смены, включая перевозку секций тралом и приёмку инспекцией.</p>"),
                     client_name="Rezidential Grup", location=tenant.city, year=2026, metrics={"weight_t": 5, "height_m": 60, "hours": 16},
                     image_url="https://images.unsplash.com/photo-1590074072786-a66914d668f1?w=900&q=70"))
    db.flush()
    return {"e1": e1, "e2": e2, "e3": e3, "e4": e4, "e5": e5}


def _demo_business(tenant: Tenant, owner: User, fleet: dict):
    """Контакты, заказы в разных статусах, партнёр с проектом и сменами — чтобы CRM не была пустой."""
    tid = tenant.id
    now = datetime.utcnow()
    people = [("Ион Русу", "+37369111222", "ion.rusu@example.com"), ("Анна Ковальчук", "+37379333444", "anna.k@example.com"),
              ("Сергей Мунтян", "+37368555666", ""), ("Виктор Чеботарь", "+37360777888", "cebotari@example.com")]
    contacts = []
    for n, p, e in people:
        c = Contact(tenant_id=tid, name=n, phone=p, email=e, source="wizard"); db.add(c); contacts.append(c)
    db.flush()
    partner = Partner(tenant_id=tid, name="Rezidential Grup SRL", idno="1012600012345", contact_name="Дмитрий Попа", phone="+37369000111",
                      email="popa@rezidential.example", tier="silver", discount_pct=5, credit_limit=300000, payment_days=14, turnover=520000)
    db.add(partner); db.flush()
    pc = Contact(tenant_id=tid, name="Дмитрий Попа", company=partner.name, phone="+37369000111", email="popa@rezidential.example", kind="b2b",
                 partner_id=partner.id, source="portal"); db.add(pc); db.flush()
    project = Project(tenant_id=tid, partner_id=partner.id, name="ЖК «Рышкань Парк», корпус B", address=f"{tenant.city}, ул. Богдан Воевод 12",
                      starts_at=(now - timedelta(days=40)).date(), ends_at=(now + timedelta(days=200)).date()); db.add(project); db.flush()

    def mk(contact, num, **kw):
        o = Order(tenant_id=tid, contact_id=contact.id, number=f"{tenant.slug[:3].upper()}-{now.year}-{num:05d}", **kw)
        db.add(o); db.flush()
        db.add(Activity(tenant_id=tid, order_id=o.id, contact_id=contact.id, kind="status", body="Заявка создана (демо)"))
        return o

    o1 = mk(contacts[0], 1, kind="b2c", source="wizard", stage="new", status="submitted", task_type="place", cargo="Бытовка 6 м", weight_t=3, height_m=3,
            radius_m=16, address=f"{tenant.city}, с. Стэучень", starts_at=now + timedelta(days=2, hours=9), hours=4, equipment_id=fleet["e3"].id,
            price_min=8140, price_max=9900, conditions=["rigger"], breakdown=[{"title": "Работа техники (4 ч × 2 200)", "amount": 8800}, {"title": "Подача", "amount": 2500}])
    o2 = mk(contacts[1], 2, kind="b2c", source="wizard", stage="contacted", status="under_review", task_type="install", cargo="Кондиционер / чиллер", weight_t=0.6,
            height_m=28, radius_m=12, address=f"{tenant.city}, бул. Дачия 47", starts_at=now + timedelta(days=4, hours=8), hours=4, equipment_id=fleet["e3"].id,
            price_min=9380, price_max=11200, escalated=False, assignee_id=owner.id)
    o3 = mk(contacts[2], 3, kind="b2c", source="phone", stage="quoted", status="quoted", task_type="lift_height", cargo="Металлоферма", weight_t=1.8, height_m=9,
            radius_m=20, address=f"{tenant.city}, ул. Узинелор 5", starts_at=now + timedelta(days=6, hours=9), hours=8, equipment_id=fleet["e3"].id, price_final=17600)
    o4 = mk(contacts[3], 4, kind="b2c", source="wizard", stage="won", status="scheduled", task_type="unload", cargo="Плиты перекрытия", weight_t=2.5, height_m=2,
            radius_m=8, address=f"{tenant.city}, ул. Мунчешть 271", starts_at=now + timedelta(hours=26), hours=4, equipment_id=fleet["e2"].id, price_final=6800)
    db.add(Booking(tenant_id=tid, equipment_id=fleet["e2"].id, starts_at=o4.starts_at, ends_at=o4.starts_at + timedelta(hours=4), reason="order", order_id=o4.id))
    o5 = mk(contacts[0], 5, kind="b2c", source="wizard", stage="won", status="paid", task_type="place", cargo="Септик", weight_t=1.5, height_m=0,
            radius_m=10, address=f"{tenant.city}, с. Стэучень", starts_at=now - timedelta(days=20), hours=4, equipment_id=fleet["e1"].id, price_final=6200, payment_status="paid")
    o6 = mk(contacts[1], 6, kind="b2c", source="wizard", stage="new", status="submitted", task_type="lift_height", cargo="Трансформатор", weight_t=42, height_m=12,
            radius_m=30, address=f"{tenant.city}, промзона", starts_at=now + timedelta(days=9, hours=7), hours=8, escalated=True,
            escalation_reasons=["Масса груза превышает 60 % возможностей парка — требуется инженерный расчёт", "Работа вблизи ЛЭП"], conditions=["power_line"])
    # B2B: заявки партнёра на проекте
    for i, (d, st, stage) in enumerate([(-7, "completed", "won"), (0, "scheduled", "won"), (7, "under_review", "contacted")], start=7):
        st_at = (now + timedelta(days=d)).replace(hour=8, minute=0)
        o = mk(pc, i, kind="b2b", source="portal", stage=stage, status=st, task_type="construction", cargo="Бетонирование перекрытия", weight_t=2.5,
               address=project.address, starts_at=st_at, hours=8, equipment_id=fleet["e3"].id, partner_id=partner.id, project_id=project.id, price_final=16720)
        if st in ("scheduled", "completed"):
            db.add(Booking(tenant_id=tid, equipment_id=fleet["e3"].id, starts_at=st_at, ends_at=st_at + timedelta(hours=8), reason="order", order_id=o.id))
        if st == "completed":
            db.add(Shift(tenant_id=tid, order_id=o.id, project_id=project.id, equipment_id=fleet["e3"].id, work_date=st_at.date(), operator="Василий Гуцу",
                         hours_worked=8.5, hours_idle=1.0, idle_fault="customer", lifts=42, status="submitted", notes="Простой 1 ч — ожидание бетона"))
    db.add(Booking(tenant_id=tid, equipment_id=fleet["e4"].id, starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=5), reason="maintenance", note="ТО-2"))
    db.add(Review(tenant_id=tid, order_id=o5.id, author="Ион Русу", rating=5, body="Приехали вовремя, септик поставили за час. Цена совпала с расчётом на сайте.", is_published=True))
    db.add(Review(tenant_id=tid, author="Rezidential Grup", rating=5, body="Работаем по проекту третий месяц — рапорты подтверждаем в портале, споров по часам нет.", is_published=True))
    db.add(Membership(tenant_id=tid, user_id=_user("client@example.com", "Ион Русу", "+37369111222").id, role="customer"))
    contacts[0].user_id = db.query(User).filter_by(email="client@example.com").first().id
    pu = _user("partner@example.com", "Дмитрий Попа", "+37369000111")
    db.add(Membership(tenant_id=tid, user_id=pu.id, role="partner", partner_id=partner.id))
    pc.user_id = pu.id


def _user(email, name, phone="", admin=False) -> User:
    u = db.query(User).filter_by(email=email).first()
    if not u:
        u = User(email=email, full_name=name, phone=phone, password_hash=hash_password(DEMO_PASSWORD), is_platform_admin=admin)
        db.add(u); db.flush()
    return u


DEMO_PASSWORD = "demo1234"
# Кого показывать на странице входа как демо-доступ. Кнопка подставляет данные в форму,
# чтобы адрес и пароль не приходилось копировать руками — при копировании подсказки
# в поле попадали разделители и невидимые символы, и вход отклонялся.
DEMO_ROLES = [
    ("client@example.com", "Клиент", "заявки, документы, повтор заказа"),
    ("partner@example.com", "Партнёр B2B", "объекты, график техники, счета"),
    ("owner@dimecon.md", "Компания", "CRM, парк, контент, команда"),
    ("admin@platform.local", "Платформа", "все компании, почта, схема БД"),
]


def demo_accounts(only: tuple[str, ...] = ()) -> list[dict]:
    """Демо-доступы, реально существующие в базе и с неизменённым демо-паролем."""
    out = []
    for email, role, hint in DEMO_ROLES:
        if only and email not in only:
            continue
        u = db.query(User).filter_by(email=email).first()
        if u and u.is_active and verify_password(u, DEMO_PASSWORD):
            out.append({"email": email, "password": DEMO_PASSWORD, "role": role, "hint": hint})
    return out


def ensure_seed(app):
    if db.query(Tenant).first():
        return
    app.logger.info("Первый запуск: создаю демо-данные")
    admin = _user("admin@platform.local", "Администратор платформы", admin=True)

    companies = [
        dict(slug="dimecon", name="Dimecon 11", legal_name="SA «Dimecon 11»", city="Chișinău", phone="+373 22 47 35 32", phone2="+373 68 140 336",
             email="office@dimecon.md", website="dimecon.md", founded_year=1968, idno="1003600012345", address="mun. Chișinău, str. Uzinelor 21",
             tagline=i18n("Краны до 100 т и негабаритные перевозки с 1968 года", "Macarale până la 100 t și transport agabaritic din 1968", "Cranes up to 100 t and oversize transport since 1968"),
             theme={"accent": "#F5A623", "navy": "#1F3A52", "hero_image_url": "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1600&q=70"},
             owner=("owner@dimecon.md", "Владелец Dimecon")),
        dict(slug="macara-nord", name="Macara Nord", legal_name="SRL «Macara Nord»", city="Bălți", phone="+373 231 55 010", email="office@macaranord.md",
             founded_year=2009, idno="1009602004411", address="Bălți, str. Decebal 88",
             tagline=i18n("Автокраны и тралы на севере Молдовы", "Automacarale și trailere în nordul Moldovei", "Mobile cranes and lowbeds in northern Moldova"),
             theme={"accent": "#E0562B", "navy": "#1B3B2F", "hero_image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?w=1600&q=70"},
             owner=("owner@macaranord.md", "Владелец Macara Nord")),
        dict(slug="sudlift", name="SudLift", legal_name="SRL «SudLift»", city="Cahul", phone="+373 299 22 331", email="info@sudlift.md",
             founded_year=2016, idno="1016605001122", address="Cahul, str. Republicii 14",
             tagline=i18n("Подъём и монтаж на юге страны", "Ridicare și montaj în sudul țării", "Lifting and installation in the south"),
             theme={"accent": "#2D9CDB", "navy": "#0F2A44", "hero_image_url": "https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=1600&q=70"},
             owner=("owner@sudlift.md", "Владелец SudLift")),
    ]
    for c in companies:
        owner_email, owner_name = c.pop("owner")
        tnt = Tenant(**c, status="active", plan="max")
        db.add(tnt); db.flush()
        owner = _user(owner_email, owner_name)
        db.add(Membership(tenant_id=tnt.id, user_id=owner.id, role="owner"))
        db.add(Membership(tenant_id=tnt.id, user_id=admin.id, role="owner"))
        seed_tenant_defaults(tnt, demo=False)
        cats = {c.code.split("_")[0]: c for c in db.query(EquipmentCategory).filter_by(tenant_id=tnt.id).all()}
        cats = {"mobile": cats["mobile"], "tower": cats["tower"], "crawler": cats["crawler"], "trailer": cats["semitrailer"]}
        fleet = _demo_fleet(tnt, cats)
        if tnt.slug == "dimecon":
            _demo_business(tnt, owner, fleet)
        tnt.settings = {"api_key": f"demo-{tnt.slug}-key"}
    db.commit()
    app.logger.info("Демо-данные созданы. Вход: admin@platform.local / demo1234")
