"""Интерфейсные строки RU/RO/EN. Контент компаний хранится в JSON-полях {ru,ro,en}."""
from __future__ import annotations

from flask import g, request, session

LANGS = ["ru", "ro", "en"]
LANG_NAMES = {"ru": "Русский", "ro": "Română", "en": "English"}

T = {
    # навигация публичного сайта
    "nav.equipment": ("Техника", "Tehnică", "Equipment"),
    "nav.services": ("Услуги", "Servicii", "Services"),
    "nav.products": ("Товары", "Produse", "Products"),
    "nav.cases": ("Кейсы", "Cazuri", "Cases"),
    "nav.about": ("О компании", "Despre noi", "About"),
    "nav.contacts": ("Контакты", "Contacte", "Contacts"),
    "nav.cabinet": ("Кабинет", "Cont", "Account"),
    "nav.calculate": ("Рассчитать", "Calculează", "Get a quote"),
    "nav.partners": ("Партнёрам", "Parteneri", "Partners"),
    # герой
    "hero.hint": ("Без регистрации · Цена появится сразу · Перезвоним за 15 минут",
                  "Fără înregistrare · Prețul apare imediat · Vă sunăm în 15 minute",
                  "No registration · Price shown instantly · We call you in 15 min"),
    "hero.cta": ("Подобрать технику →", "Selectează utilajul →", "Find equipment →"),
    "stats.founded": ("год основания", "an de fondare", "year founded"),
    "stats.capacity": ("макс. грузоподъёмность", "cap. max. ridicare", "max lift capacity"),
    "stats.reach": ("макс. вылет", "deschidere max.", "max reach"),
    "stats.fleet": ("единиц техники", "utilaje", "units in fleet"),
    # секции
    "sec.tasks.label": ("ВОЗМОЖНОСТИ", "POSIBILITĂȚI", "CAPABILITIES"),
    "sec.tasks.title": ("Задачи, которые мы закрываем", "Lucrări pe care le executăm", "Tasks we handle"),
    "sec.fleet.label": ("ПАРК ТЕХНИКИ", "PARC TEHNIC", "FLEET"),
    "sec.fleet.title": ("Наш парк", "Parcul nostru", "Our fleet"),
    "sec.fleet.all": ("Смотреть весь каталог →", "Toate utilajele →", "View full catalog →"),
    "sec.steps.label": ("КАК ЭТО РАБОТАЕТ", "CUM FUNCȚIONEAZĂ", "HOW IT WORKS"),
    "sec.steps.title": ("Техника на объекте за 4 шага", "Utilajul pe șantier în 4 pași", "Equipment on site in 4 steps"),
    "sec.price.label": ("ПРОЗРАЧНЫЕ ЦЕНЫ", "PREȚURI TRANSPARENTE", "TRANSPARENT PRICING"),
    "sec.price.title": ("Никаких скрытых коэффициентов", "Niciun coeficient ascuns", "No hidden fees"),
    "sec.cases.label": ("ОБЪЕКТЫ", "OBIECTE", "PROJECTS"),
    "sec.cases.title": ("Кейсы", "Cazuri", "Case studies"),
    "sec.partners.label": ("ДЛЯ ПОДРЯДЧИКОВ", "PENTRU ANTREPRENORI", "FOR CONTRACTORS"),
    "sec.partners.title": ("Работайте с нами как партнёр", "Lucrați cu noi ca partener", "Work with us as a partner"),
    "sec.partners.text": ("Договорные цены, личный диспетчер, портал с графиком техники и сменными рапортами.",
                          "Prețuri contractuale, dispecer personal, portal cu grafic și rapoarte de schimb.",
                          "Contract rates, dedicated dispatcher, portal with schedule and shift reports."),
    "sec.partners.cta": ("Стать партнёром", "Deveniți partener", "Become a partner"),
    "sec.faq.title": ("Частые вопросы", "Întrebări frecvente", "Frequently asked questions"),
    "sec.contacts.title": ("Контакты", "Contacte", "Contacts"),
    "steps.1.t": ("Опишите задачу", "Descrieți sarcina", "Describe your task"),
    "steps.1.d": ("Что поднять, на какую высоту, на каком расстоянии — без технических терминов",
                  "Ce ridicați, la ce înălțime, la ce distanță — fără termeni tehnici",
                  "What to lift, how high, how far — no technical terms"),
    "steps.2.t": ("Получите расчёт", "Primiți calculul", "Get your quote"),
    "steps.2.d": ("Система подбирает технику и показывает цену построчно",
                  "Sistemul selectează utilajul și afișează prețul pe linii",
                  "The system picks equipment and shows an itemised price"),
    "steps.3.t": ("Подтвердите заявку", "Confirmați comanda", "Confirm your order"),
    "steps.3.d": ("Оставьте контакт — подтверждение за 15 минут",
                  "Lăsați un contact — confirmare în 15 minute",
                  "Leave a contact — confirmation within 15 minutes"),
    "steps.4.t": ("Техника приедет", "Utilajul vine", "Equipment arrives"),
    "steps.4.d": ("Оператор, документы, инструктаж — всё включено",
                  "Operator, documente, instructaj — totul inclus",
                  "Operator, documents, briefing — all included"),
    # техника
    "eq.available": ("Свободен", "Disponibil", "Available"),
    "eq.busy": ("Занят", "Ocupat", "Busy"),
    "eq.capacity": ("Г/П", "C/R", "Cap."),
    "eq.reach": ("Вылет", "Deschid.", "Reach"),
    "eq.height": ("Высота", "Înălțime", "Height"),
    "eq.payload": ("Грузоподъёмность", "Sarcină utilă", "Payload"),
    "eq.from": ("от", "de la", "from"),
    "eq.hour": ("час", "oră", "hour"),
    "eq.order": ("Заказать", "Comandă", "Order"),
    "eq.loadchart": ("Грузовая характеристика", "Diagrama de sarcină", "Load chart"),
    "eq.specs": ("Характеристики", "Caracteristici", "Specifications"),
    # визард
    "wz.title": ("Подбор техники и расчёт стоимости", "Selectarea utilajului și calculul", "Equipment selection & quote"),
    "wz.step": ("Шаг", "Pasul", "Step"),
    "wz.of": ("из", "din", "of"),
    "wz.back": ("← Назад", "← Înapoi", "← Back"),
    "wz.next": ("Далее →", "Mai departe →", "Next →"),
    "wz.dontknow": ("Не знаю", "Nu știu", "I don't know"),
    "wz.s1": ("Что нужно сделать?", "Ce trebuie făcut?", "What do you need?"),
    "wz.s2": ("Что поднимаем?", "Ce ridicăm?", "What are we lifting?"),
    "wz.s3": ("На какую высоту?", "La ce înălțime?", "How high?"),
    "wz.s4": ("Насколько близко подъедет машина?", "Cât de aproape ajunge utilajul?", "How close can the crane park?"),
    "wz.s5": ("Условия на площадке", "Condiții pe șantier", "Site conditions"),
    "wz.s6": ("Когда и где?", "Când și unde?", "When and where?"),
    "wz.result": ("Ваш вариант", "Varianta dvs.", "Your option"),
    "wz.contacts": ("Ваши контакты", "Contactele dvs.", "Your contacts"),
    "wz.weight": ("Вес, тонн", "Greutate, tone", "Weight, tons"),
    "wz.qty": ("Количество", "Cantitate", "Quantity"),
    "wz.height_m": ("Высота, м", "Înălțime, m", "Height, m"),
    "wz.radius_m": ("Расстояние, м", "Distanță, m", "Distance, m"),
    "wz.date": ("Дата и время", "Data și ora", "Date and time"),
    "wz.hours": ("Длительность, ч", "Durata, ore", "Duration, h"),
    "wz.flex": ("Дата гибкая (±3 дня) — скидка", "Data flexibilă (±3 zile) — reducere", "Flexible date (±3 days) — discount"),
    "wz.address": ("Адрес объекта", "Adresa obiectului", "Site address"),
    "wz.zone": ("Зона", "Zona", "Zone"),
    "wz.optimal": ("Оптимально", "Optim", "Best fit"),
    "wz.cheaper": ("Дешевле", "Mai ieftin", "Cheaper"),
    "wz.reserve": ("С запасом", "Cu rezervă", "Extra margin"),
    "wz.why": ("Почему эта машина", "De ce acest utilaj", "Why this machine"),
    "wz.breakdown": ("Из чего складывается цена", "Din ce se compune prețul", "Price breakdown"),
    "wz.disclaimer": ("Это предварительный подбор. Окончательное решение о схеме подъёма принимает инженер после уточнения условий на площадке.",
                      "Aceasta este o selecție preliminară. Decizia finală o ia inginerul după verificarea condițiilor.",
                      "This is a preliminary selection. The final lifting plan is confirmed by our engineer after site review."),
    "wz.escalated": ("Ваша задача требует инженерного расчёта — это наша специализация. Оставьте контакт, инженер свяжется с вами.",
                     "Sarcina dvs. necesită calcul ingineresc — specialitatea noastră. Lăsați contactul, inginerul vă va suna.",
                     "Your task needs an engineering assessment — our specialty. Leave a contact and our engineer will call."),
    "wz.submit": ("Оформить заявку", "Trimite comanda", "Submit order"),
    "wz.name": ("Имя", "Nume", "Name"),
    "wz.phone": ("Телефон", "Telefon", "Phone"),
    "wz.email": ("E-mail", "E-mail", "E-mail"),
    "wz.comment": ("Комментарий", "Comentariu", "Comment"),
    "wz.success": ("Заявка принята", "Comanda a fost primită", "Order received"),
    "wz.success.text": ("Мы подтвердим заявку в течение 30 минут в рабочее время.",
                        "Vom confirma comanda în 30 de minute în orele de lucru.",
                        "We will confirm within 30 minutes during business hours."),
    "wz.total": ("Итого", "Total", "Total"),
    "wz.vat": ("НДС", "TVA", "VAT"),
    # кабинет клиента
    "acc.login": ("Вход", "Autentificare", "Sign in"),
    "acc.register": ("Регистрация", "Înregistrare", "Sign up"),
    "acc.logout": ("Выйти", "Ieșire", "Sign out"),
    "acc.orders": ("Мои заказы", "Comenzile mele", "My orders"),
    "acc.repeat": ("Повторить заказ", "Repetă comanda", "Repeat order"),
    "acc.password": ("Пароль", "Parolă", "Password"),
    "common.all": ("Все", "Toate", "All"),
    "common.save": ("Сохранить", "Salvează", "Save"),
    "common.cancel": ("Отмена", "Anulare", "Cancel"),
    "common.delete": ("Удалить", "Șterge", "Delete"),
    "common.search": ("Поиск", "Căutare", "Search"),
    "common.price": ("Цена", "Preț", "Price"),
    "common.status": ("Статус", "Status", "Status"),
    "common.date": ("Дата", "Data", "Date"),
    "common.more": ("Подробнее", "Detalii", "Details"),
    "footer.rights": ("Все права защищены", "Toate drepturile rezervate", "All rights reserved"),
    "footer.powered": ("Работает на платформе", "Funcționează pe platforma", "Powered by"),
}


def current_lang() -> str:
    lang = getattr(g, "lang", None)
    if lang:
        return lang
    lang = request.args.get("lang") or session.get("lang")
    tenant = getattr(g, "tenant", None)
    allowed = (tenant.locales if tenant and tenant.locales else LANGS)
    if lang not in allowed:
        lang = tenant.default_locale if tenant else None
    if lang not in allowed:
        lang = allowed[0]
    g.lang = lang
    return lang


def t(key: str, lang: str | None = None) -> str:
    lang = lang or current_lang()
    row = T.get(key)
    if not row:
        return key
    return row[LANGS.index(lang)] if lang in LANGS else row[0]


def tr(value, lang: str | None = None) -> str:
    """Достать перевод из JSON-поля контента {ru,ro,en} с fallback."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    lang = lang or current_lang()
    return value.get(lang) or value.get("ru") or value.get("ro") or value.get("en") or ""
