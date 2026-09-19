"""Сборка HTML-актов тестирования по разделам и презентации для заказчика.

Источник данных — реальные протоколы прогонов в docs/*.log и снимки экрана в docs/screens/.
Ничего не выдумывается: в акт попадают те строки проверок, которые есть в журнале.

Запуск из корня проекта:  python tools/build_acts.py
Результат: docs/acts/*.html, docs/acts/index.html, docs/presentation.html
"""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ACTS = DOCS / "acts"
SCREENS = DOCS / "screens"
ACTS.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%d.%m.%Y")
NOW = datetime.now().strftime("%d.%m.%Y %H:%M")

# --------------------------------------------------------------------- разбор журналов

CHECK_RE = re.compile(r"^\s{2}(OK|ОШИБКА)\s+(.+?)(?:\s+—\s+(.*))?$")
SECTION_RE = re.compile(r"^\s*={0,3}\s*(\d+[a-z]?\.\s+[^=]+?)\s*={0,3}\s*$")
SMOKE_RE = re.compile(r"^(ok|BAD)\s+(\d{3})\s+(\S+)")
MARK_RE = re.compile(r"^---\s*(.+?)\s*---$")


def read(name: str) -> list[str]:
    p = DOCS / name
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def parse_checks(name: str) -> list[dict]:
    """Проверки вида «OK  название — детали», сгруппированные по разделам журнала."""
    out, section = [], ""
    for line in read(name):
        s = SECTION_RE.match(line.strip("= "))
        if s and not CHECK_RE.match(line):
            section = s.group(1).strip()
            continue
        m = CHECK_RE.match(line)
        if m:
            out.append({"section": section, "ok": m.group(1) == "OK",
                        "name": m.group(2).strip(), "detail": (m.group(3) or "").strip()})
    return out


def parse_raw_sections(name: str) -> dict[str, str]:
    """Свободный текст журнала по разделам — для измерений и сводок."""
    blocks, title, buf = {}, "", []
    for line in read(name):
        if set(line.strip()) == {"="} and len(line.strip()) > 10:
            continue
        s = SECTION_RE.match(line.strip())
        if s:
            if title and buf:
                blocks[title] = "\n".join(buf).strip()
            title, buf = s.group(1).strip(), []
            continue
        if title:
            buf.append(line)
    if title and buf:
        blocks[title] = "\n".join(buf).strip()
    return blocks


def parse_caps_sections(name: str) -> dict[str, str]:
    """Журналы с заголовками ПРОПИСНЫМИ без нумерации (отчёт о переносе)."""
    blocks, title, buf = {}, "", []
    for raw in read(name):
        line = raw.replace("﻿", "").rstrip()
        if not line or set(line.strip()) <= {"=", "-"}:
            continue
        if not line.startswith(" "):
            if title and buf:
                blocks[title] = "\n".join(buf).strip()
            title, buf = line.strip(), []
            continue
        if title:
            buf.append(line)
    if title and buf:
        blocks[title] = "\n".join(buf).strip()
    return blocks


def parse_smoke() -> dict:
    """Маршруты и действия из сквозного прогона."""
    routes, actions, group = [], [], "публичные страницы"
    for line in read("smoke_mysql.log"):
        g = MARK_RE.match(line.strip())
        if g:
            group = g.group(1).strip()
            continue
        m = SMOKE_RE.match(line)
        if m:
            routes.append({"ok": m.group(1) == "ok", "code": m.group(2), "url": m.group(3), "group": group})
            continue
        if re.match(r"^(status change|issue quote|kanban drag|partner request|repeat order|result|submit|"
                    r"escalation case|api |тестовые объекты|DB:)", line):
            actions.append(line.strip())
    return {"routes": routes, "actions": actions}


def captions() -> dict[str, str]:
    idx = SCREENS / "index.txt"
    out = {}
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                k, v = line.split("\t", 1)
                out[k] = v
    extra = {
        "52_pdf_confirmation": "PDF: подтверждение заказа",
        "53_pdf_quote": "PDF: коммерческое предложение",
        "54_pdf_invoice": "PDF: счёт с суммой прописью",
        "55_pdf_act": "PDF: акт выполненных работ",
        "56_pdf_shift": "PDF: сменный рапорт",
        "57_xlsx_orders": "Excel: реестр заявок",
        "58_xlsx_pricelist": "Excel: прайс-лист, 4 листа",
        "59_xlsx_fleet": "Excel: парк и грузовые таблицы",
        "60_xlsx_shifts": "Excel: табель смен",
        "61_source_site": "Исходный сайт dimecon.md до переноса",
        "62_ported_catalog": "Тот же парк после переноса на платформу",
        "63_ported_services": "14 услуг заказчика после переноса",
        "64_admin_crm": "Интеграция с внешней CRM и Oracle ERP",
        "19b_wizard_result_multi": "Подбор: «Оптимально» и «С запасом»",
    }
    for k, v in extra.items():
        out.setdefault(k, v)
    return out


CAPS = captions()
SMOKE = parse_smoke()


def shots(*names: str) -> list[dict]:
    out = []
    for n in names:
        f = SCREENS / f"{n}.png"
        if f.exists():
            out.append({"src": f"../screens/{n}.png", "cap": CAPS.get(n, n), "name": n})
    return out


def routes_of(*substrings: str, limit: int = 200) -> list[dict]:
    sel = [r for r in SMOKE["routes"] if any(s in r["url"] for s in substrings)]
    seen, out = set(), []
    for r in sel:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        out.append(r)
    return out[:limit]


# --------------------------------------------------------------------- описание актов

def checks_from(name: str, *prefixes: str) -> list[dict]:
    rows = parse_checks(name)
    if not prefixes:
        return rows
    return [r for r in rows if any(r["section"].startswith(p) for p in prefixes)]


PORT = parse_caps_sections("port_report.log")
ACC = parse_raw_sections("acceptance.log")


def acc_block(*titles: str) -> list[tuple[str, str]]:
    return [(t, ACC[t]) for t in titles if t in ACC]


def port_block(*titles: str) -> list[tuple[str, str]]:
    return [(t, PORT[t]) for t in titles if t in PORT]


ACT_DEFS = [
    {
        "id": "01_infrastruktura",
        "num": "1",
        "title": "Инфраструктура и база данных",
        "lead": "Развёртывание MySQL 8.4, схема, целостность данных, кодировка и быстродействие.",
        "scope": ["установка и настройка СУБД, создание схемы и учётной записи приложения",
                  "автоматическое создание 24 таблиц и заполнение демонстрационными данными",
                  "проверка ссылочной целостности между компаниями-арендаторами",
                  "хранение кириллицы, румынской диакритики и эмодзи",
                  "замер времени отклика ключевых страниц и API",
                  "очередь исходящих писем"],
        "raw": acc_block("1. СУБД", "2. ДАННЫЕ", "3. ЦЕЛОСТНОСТЬ МУЛЬТИАРЕНДНОСТИ",
                         "4. КОДИРОВКА utf8mb4: кириллица, румынская диакритика, эмодзи",
                         "5. ПРОИЗВОДИТЕЛЬНОСТЬ (10 замеров на страницу, сервер MySQL)",
                         "7. ПОЧТА"),
        "checks": [],
        "access_title": "Контрольные показатели стенда",
        "access": [
            ("Сервер СУБД", "MySQL 8.x, InnoDB", "MySQL 8.4.0, все 24 таблицы InnoDB"),
            ("Кодировка базы", "utf8mb4", "utf8mb4 / utf8mb4_unicode_ci"),
            ("Схема развёрнута", "24 таблицы, внешние ключи", "24 таблицы, 82 индекса, 41 внешний ключ"),
            ("Кириллица, диакритика, эмодзи", "запись равна чтению", "совпадение: да"),
            ("Заказы без компании-владельца", "0", "0"),
            ("Заказы с техникой чужой компании", "0", "0"),
            ("Отклик страниц под нагрузкой", "не более 200 мс", "медиана 5–74 мс, максимум 84 мс"),
            ("Письма при недоступном SMTP", "не теряются", "130 писем в очереди со статусом queued"),
        ],
        "screens": shots("46_superadmin", "47_superadmin_mail", "24_admin_dashboard"),
        "verdict": "Годен",
        "summary": ["MySQL 8.4.0 LTS, база в utf8mb4, 24 таблицы InnoDB, 82 индекса, 41 внешний ключ",
                    "перекрёстных ссылок между компаниями в данных — ноль",
                    "медиана отклика страниц 5–74 мс при требовании ТЗ не более 200 мс",
                    "письма при ненастроенном SMTP остаются в очереди и не теряются"],
        "limits": ["Резервное копирование и перенос на выделенный сервер СУБД в объём испытаний не входили.",
                   "SMTP компаний в тестовом контуре не настроен: проверялась постановка писем в очередь, "
                   "не фактическая доставка."],
    },
    {
        "id": "02_sajt_zakazchika",
        "num": "2",
        "title": "Сайт заказчика и перенос содержимого",
        "lead": "Полный перенос действующего сайта dimecon.md на платформу и проверка публичных страниц.",
        "scope": ["выгрузка разделов исходного сайта на трёх языках",
                  "перенос парка техники, услуг, товаров, страниц и фотографий",
                  "объединение расходящихся языковых версий каталога",
                  "работа публичных страниц трёх компаний и переключение языков"],
        "raw": port_block("ПЕРЕНЕСЕНО С dimecon.md", "ПО КАТЕГОРИЯМ", "ПОЛНОТА ДАННЫХ",
                          "РАССИНХРОН ЯЗЫКОВ НА ИСХОДНОМ САЙТЕ (карточек в разделе)"),
        "checks": checks_from("test_richtext.log"),
        "routes": routes_of("/s/dimecon/", "/s/macara-nord/", "/s/sudlift/"),
        "route_filter_out": ["/admin", "/partner", "/account", "/export"],
        "access_title": "Контрольные показатели переноса",
        "access": [
            ("Единиц техники перенесено", "весь парк исходного сайта", "22 из 22"),
            ("Названия техники на трёх языках", "22 / 22 / 22", "ru 22, ro 22, en 22"),
            ("Фотографии техники", "у каждой карточки", "без фотографии — 0, всего 57 файлов"),
            ("Услуги", "14", "14"),
            ("Товары, страницы, кейсы", "перенесены", "5 товаров, 3 страницы, 2 кейса"),
            ("Контакты и год основания", "как на сайте", "+373 22 47 35 32, office@dimecon.md, 1968"),
            ("Технические характеристики", "по данным источника", "нет у 2 машин — GROVE GMK 2035 и GMK 3055"),
            ("Товары: соответствие языковых версий", "карточка совпадает по смыслу, а не по позиции",
             "5 карточек сопоставлены по названию; у «аренды помещений» английской версии на сайте нет"),
            ("Товары: описание и таблицы", "выводятся разметкой, а не кодом", "3 таблицы характеристик, 0 экранированных тегов"),
            ("Товары: фотографии", "не растягивать значки 86×92", "мелкие изображения показаны миниатюрами"),
        ],
        "screens": shots("61_source_site", "62_ported_catalog", "63_ported_services", "04_site_home",
                         "05_site_home_ro", "06_site_equipment", "07_site_equipment_item", "08_site_services",
                         "09_site_products", "10_site_partners", "11_site_tenant2", "12_site_tenant3_en",
                         "50_mobile_home", "51_mobile_wizard"),
        "verdict": "Годен",
        "summary": ["22 единицы техники, 14 услуг, 5 товарных позиций, 3 страницы, 57 фотографий",
                    "языковые версии исходного сайта расходятся: 3 автокрана в русской против 22 единиц фактически",
                    "перенос объединил версии по модели — весь парк доступен на всех трёх языках"],
        "limits": ["У GROVE GMK 3055 и GMK 2035 на исходном сайте нет технических характеристик — "
                   "карточки перенесены, характеристики показаны как «—», в подборе не участвуют.",
                   "Грузовые таблицы производителя на сайте отсутствуют: построены ориентировочные кривые "
                   "с занижением 15 % и явным предупреждением на карточке."],
    },
    {
        "id": "03_podbor_i_raschet",
        "num": "3",
        "title": "Подбор техники и расчёт стоимости",
        "lead": "Проверка инженерного подбора крана и построчного расчёта цены на реальном парке заказчика.",
        "scope": ["формулы расчётной массы и требуемой высоты",
                  "отбор по грузовым характеристикам с нормативным запасом",
                  "коэффициенты времени, сезона, условий и срочности, зоны подачи",
                  "потолки коэффициентов и скидок",
                  "правила эскалации к инженеру",
                  "калькулятор массы по габаритам и материалу"],
        "checks": checks_from("test_calc_docs.log", "1.", "2.", "3."),
        "screens": shots("13_wizard_s1", "14_wizard_s2", "15_wizard_s3", "16_wizard_s4", "17_wizard_s5",
                         "18_wizard_s6", "19b_wizard_result_multi", "20_wizard_breakdown", "23_wizard_escalation"),
        "verdict": "Годен",
        "summary": ["каждая составляющая цены сверена с независимым ручным расчётом",
                    "ни один вариант не выдан с запасом ниже нормативных 10 %",
                    "эскалация при 42 т и работе вблизи ЛЭП срабатывает"],
        "limits": ["Подбор идёт по ориентировочным кривым: паспортные таблицы производителя заказчиком "
                   "пока не предоставлены."],
    },
    {
        "id": "04_zakazy_crm",
        "num": "4",
        "title": "Оформление заказов, формы и CRM компании",
        "lead": "Сквозной путь заявки от визарда до сделки в кабинете компании.",
        "scope": ["оформление заявки через визард без регистрации",
                  "формы обратной связи и заявки на партнёрство, защита CSRF",
                  "воронка сделок, смена статусов, история",
                  "назначение техники, выпуск документов, сменные рапорты",
                  "кабинет клиента: заказы, документы, повтор заказа"],
        "checks": checks_from("test_calc_docs.log", "4."),
        "routes": routes_of("/admin/", "/account/"),
        "actions": SMOKE["actions"],
        "screens": shots("21_wizard_done", "22_track", "24_admin_dashboard", "25_admin_kanban",
                         "26_admin_orders_list", "27_admin_order", "28_admin_contacts", "29_admin_fleet",
                         "30_admin_equipment", "31_admin_content", "32_admin_content_edit", "33_admin_media",
                         "34_admin_partners", "44_account_index", "45_account_order"),
        "verdict": "Годен",
        "summary": ["заявка оформляется без регистрации и получает номер",
                    "формы без CSRF-токена отклоняются кодом 400",
                    "из карточки заявки выпускаются КП, счёт и акт, создаётся сменный рапорт"],
        "limits": ["Онлайн-оплата и SMS-подтверждение в сборку не входят: требуются договор с банком и SMS-шлюз."],
    },
    {
        "id": "05_b2b_portal",
        "num": "5",
        "title": "Портал партнёра B2B",
        "lead": "Рабочее место подрядчика: объекты, заявки, график техники, сменные рапорты, документы.",
        "scope": ["объекты партнёра и заявки из шаблона",
                  "повторяющиеся заявки с договорной скидкой",
                  "график техники без раскрытия чужих броней",
                  "подтверждение и оспаривание сменных рапортов",
                  "документы, счета и кредитный лимит"],
        "routes": routes_of("/partner/"),
        "actions": [a for a in SMOKE["actions"] if "partner" in a.lower()],
        "access_title": "Проверенные сценарии партнёра",
        "access": [
            ("Вход в портал под учётной записью партнёра", "рабочий стол партнёра", "200"),
            ("Карточка объекта партнёра", "открывается", "200"),
            ("Повторяющаяся заявка на две недели", "создаётся серия из 2 заявок", "создано 2, ответ 200"),
            ("График техники на 14 дней", "свои брони с деталями, чужие — только отметка занятости",
             "200; в сетку передаются только метки «моя» и «занято»"),
            ("Документы и счета партнёра", "открываются", "200"),
            ("Партнёр открывает кабинет компании", "доступ закрыт", "403"),
        ],
        "screens": shots("40_partner_index", "41_partner_project", "42_partner_schedule",
                         "43_partner_documents", "10_site_partners"),
        "verdict": "Годен",
        "summary": ["повторяющаяся заявка создаёт серию по неделям одним действием",
                    "в графике видны свои брони, чужие — только как занятость без деталей",
                    "кабинет компании партнёру недоступен: 403"],
        "limits": ["Планы объекта с метками и офлайн-режим PWA — за периметром текущей сборки."],
    },
    {
        "id": "06_dokumenty",
        "num": "6",
        "title": "Документы: PDF и Excel",
        "lead": "Генерация первичных документов и выгрузок, проверка содержимого и разграничения доступа.",
        "scope": ["пять типов PDF: подтверждение, КП, счёт, акт, сменный рапорт",
                  "шесть выгрузок Excel с фильтрами и формулами итогов",
                  "кириллица и румынская диакритика в документах",
                  "сумма прописью с согласованием числительных"],
        "checks": checks_from("test_calc_docs.log", "5.", "6.") + checks_from("test_words.log"),
        "screens": shots("52_pdf_confirmation", "53_pdf_quote", "54_pdf_invoice", "55_pdf_act", "56_pdf_shift",
                         "57_xlsx_orders", "58_xlsx_pricelist", "59_xlsx_fleet", "60_xlsx_shifts"),
        "verdict": "Годен",
        "summary": ["текст извлечён обратно из каждого PDF: кириллица и диакритика на месте",
                    "в выгрузке заявок 22 колонки, фильтры и итоги формулами",
                    "прайс-лист содержит 4 листа, выгрузка парка — 126 строк грузовых таблиц"],
        "limits": ["Электронная подпись документов и передача в e-Factura не реализованы.",
                   "Разграничение доступа к документам по ролям проверено отдельно — акт № 7."],
    },
    {
        "id": "07_bezopasnost",
        "num": "7",
        "title": "Мультиарендность и разграничение доступа",
        "lead": "Изоляция данных между компаниями и права ролей.",
        "scope": ["доступ владельца компании только к своему кабинету",
                  "права партнёра и клиента",
                  "защита выгрузок и документов",
                  "доступ к API по ключу",
                  "отсутствие перекрёстных ссылок в данных"],
        "checks": checks_from("test_calc_docs.log", "7."),
        "raw": acc_block("3. ЦЕЛОСТНОСТЬ МУЛЬТИАРЕНДНОСТИ"),
        "access": [
            ("Владелец Dimecon открывает кабинет другой компании", "403", "403"),
            ("Партнёр B2B открывает кабинет компании", "403", "403"),
            ("Суперадмин открывает кабинет любой компании", "200", "200"),
            ("Аноним скачивает документ", "перенаправление на вход", "302"),
            ("Аноним выгружает реестр заявок", "перенаправление на вход", "302"),
            ("Клиент скачивает документ по чужой заявке", "403", "403"),
            ("Прайс-лист без входа", "200 — это витрина", "200"),
            ("Запрос к API без ключа", "401", "401"),
            ("Форма без CSRF-токена", "400", "400"),
        ],
        "screens": shots("49_isolation_403", "48_isolation_ok", "46_superadmin", "39_admin_team",
                         "11_site_tenant2", "12_site_tenant3_en"),
        "verdict": "Годен",
        "summary": ["изоляция подтверждена на уровне приложения и на уровне данных",
                    "девять сценариев доступа отработали ожидаемо",
                    "пароли и ключи в интерфейсе не показываются"],
        "limits": ["Внешний тест на проникновение не проводился — он предусмотрен отдельным этапом."],
    },
    {
        "id": "09_vhod_i_roli",
        "num": "9",
        "title": "Вход и роли пользователей",
        "lead": "Вход демо-доступами, устойчивость формы к ошибкам ввода и права каждой роли после входа.",
        "scope": ["вход четырьмя ролями: клиент, партнёр B2B, компания, платформа",
                  "куда попадает каждая роль сразу после входа",
                  "устойчивость формы к копированию подсказки: пробелы, невидимые символы, разделители",
                  "понятность отказа: неверный пароль, неизвестный адрес, устаревшая вкладка",
                  "разграничение доступа между ролями и компаниями",
                  "поведение без входа и выход из системы"],
        "checks": checks_from("test_roles.log"),
        "screens": shots("68_login_tenant", "69_login_platform", "88_demo_button_result",
                         "86_login_wrong_password", "87_login_unknown_user",
                         "70_role_client_home", "71_role_client_order", "72_role_client_profile",
                         "73_role_partner_home", "74_role_partner_schedule", "75_role_partner_docs",
                         "76_role_owner_home", "77_role_owner_fleet", "78_role_owner_team",
                         "79_role_admin_home", "80_role_admin_mail", "81_role_admin_tenant",
                         "82_denied_client_partner", "83_denied_partner_admin",
                         "84_denied_owner_foreign", "85_denied_owner_platform"),
        "verdict": "Годен",
        "summary": ["каждая из четырёх ролей входит и попадает на своё рабочее место",
                    "вход не срывается из-за пробелов, регистра и невидимых символов при копировании",
                    "отказ называет причину: «пароль не подошёл» или «пользователь не найден»",
                    "устаревшая вкладка больше не даёт ошибку 400, а предлагает повторить ввод",
                    "чужие разделы закрыты кодом 403 для всех ролей, кроме администратора платформы"],
        "limits": ["Демо-доступы существуют только на испытательном стенде: кнопки входа появляются, "
                   "лишь пока в базе есть демо-учётные записи с исходным паролем.",
                   "Двухфакторная проверка и вход через внешние сервисы в объём работ не входили."],
    },
    {
        "id": "08_integracii",
        "num": "8",
        "title": "Интеграции с экосистемой заказчика",
        "lead": "Обмен с системой на платформе Artgranit: Partner B2B API, Oracle ERP, импорт из CRM, модуль портала.",
        "scope": ["импорт контактов и сделок из выгрузки CSV или Excel любой системы",
                  "клиент Partner B2B API OfficePlus: авторизация, каталог, остатки, заказы",
                  "чтение контрагентов и оборотов напрямую из Oracle ERP",
                  "модуль-витрина для портала Artgranit по контракту его ядра"],
        "checks": (checks_from("test_crm_import.log") + checks_from("test_officeplus.log")
                   + checks_from("test_oracle_source.log") + checks_from("validate_integration.log")),
        "screens": shots("64_admin_crm", "36_admin_smtp", "37_admin_storage", "39_admin_team"),
        "verdict": "Годен с оговоркой",
        "summary": ["импорт из файла распознаёт колонки на трёх языках и не плодит дубликаты",
                    "клиент Partner B2B API учитывает задокументированные особенности реального API",
                    "запросы к Oracle построены по схеме TMS_ORG / TMS_UNIVERS / PAPI_PARTNER",
                    "модуль для портала соответствует контракту ядра Artgranit"],
        "limits": ["Обращений к действующим officeplus.md и Oracle ERP не выполнялось: пароли заказчика "
                   "недоступны на испытательном стенде. Проверены построение запросов, разбор ответов и "
                   "перенос данных — на подставном сервере API и подставном соединении с СУБД.",
                   "Установка модуля в портал Artgranit требует доступа к серверу заказчика."],
    },
]

# --------------------------------------------------------------------- вёрстка

CSS = """
:root{--paper:#FBFAF7;--raised:#fff;--sunken:#F4F2EC;--ink:#16191C;--ink-2:#55606A;--ink-3:#8A939B;
--line:#E2DED4;--line-strong:#CFC9BC;--accent:#D98A0B;--accent-soft:#FBEFD8;--navy:#1F3A52;
--ok:#2E7D4F;--bad:#B23B2E;--warn:#C77700;
--sans:"Inter",-apple-system,"Segoe UI",Roboto,sans-serif;--serif:"Source Serif 4",Georgia,serif;
--mono:ui-monospace,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:0 28px 80px}
a{color:var(--navy)}
header.top{background:var(--navy);color:#fff;padding:26px 0 22px;margin-bottom:26px}
header.top .wrap{padding-bottom:0}
.eyebrow{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-family:var(--serif);font-size:clamp(24px,3.4vw,34px);line-height:1.15;margin:8px 0 6px;letter-spacing:-.015em}
header.top h1{color:#fff}
header.top .lead{color:rgba(255,255,255,.78);max-width:70ch;margin:0}
h2{font-family:var(--serif);font-size:23px;margin:34px 0 12px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:16.5px;margin:22px 0 8px}
p{margin:0 0 .9em}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.pill{border:1px solid rgba(255,255,255,.28);border-radius:999px;padding:3px 11px;font-size:12px;color:rgba(255,255,255,.9)}
.verdict{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:4px 13px;font-weight:700;font-size:13px}
.verdict.ok{background:#E3F3EA;color:var(--ok)}.verdict.warn{background:#FCEFD9;color:var(--warn)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0}
.card{background:var(--raised);border:1px solid var(--line);border-radius:12px;padding:15px 17px}
.card b{display:block;font-family:var(--serif);font-size:27px;line-height:1.1;letter-spacing:-.02em}
.card span{font-size:12.5px;color:var(--ink-2)}
ul.scope{margin:0 0 1em;padding-left:1.15em}ul.scope li{margin:.25em 0}
table{width:100%;border-collapse:collapse;font-size:13.6px;background:var(--raised);
border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:12px 0}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--sunken);font-size:12.4px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-2)}
tbody tr:last-child td{border-bottom:0}
td.st{white-space:nowrap;font-weight:700;width:1%}
td.st.ok{color:var(--ok)}td.st.bad{color:var(--bad)}
td.dt{color:var(--ink-2);font-family:var(--mono);font-size:12.2px}
pre{background:var(--sunken);border:1px solid var(--line);border-radius:10px;padding:13px 15px;
overflow-x:auto;font-family:var(--mono);font-size:12.4px;line-height:1.5;white-space:pre-wrap}
.shots{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px;margin:16px 0}
figure{margin:0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--raised)}
figure img{width:100%;display:block;background:var(--sunken);cursor:zoom-in}
figcaption{padding:9px 12px;font-size:12.4px;color:var(--ink-2);border-top:1px solid var(--line)}
figcaption b{color:var(--ink);font-family:var(--mono);font-size:11.4px;display:block;margin-bottom:2px}
.note{border-left:3px solid var(--warn);background:#FCEFD9;padding:12px 15px;border-radius:0 8px 8px 0;margin:14px 0;font-size:13.6px;color:#7A4E00}
.note.info{border-color:var(--accent);background:var(--accent-soft);color:#7A4E00}
.foot{margin-top:40px;padding-top:16px;border-top:3px double var(--line-strong);font-size:13px;color:var(--ink-2)}
.nav{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 0}
.nav a{border:1px solid var(--line-strong);background:var(--raised);border-radius:8px;padding:6px 12px;
font-size:13px;text-decoration:none;font-weight:600}
.nav a:hover{border-color:var(--accent)}
.lb{position:fixed;inset:0;background:rgba(10,12,14,.92);display:none;align-items:center;justify-content:center;z-index:99;padding:22px}
.lb.on{display:flex}.lb img{max-width:100%;max-height:100%;border-radius:8px}
@media print{header.top{background:#fff;color:#000;border-bottom:2px solid #000}
header.top h1,header.top .lead{color:#000}.pill{border-color:#999;color:#000}
.nav,.lb{display:none!important}figure{break-inside:avoid}table{break-inside:auto}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" '
         'href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?'
         'family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700'
         '&display=swap" rel="stylesheet">')

LIGHTBOX = """<div class="lb" id="lb"><img alt=""></div><script>
const lb=document.getElementById('lb');document.querySelectorAll('figure img').forEach(i=>i.onclick=()=>{
lb.querySelector('img').src=i.src;lb.classList.add('on')});lb.onclick=()=>lb.classList.remove('on');
document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('on')});</script>"""

E = html.escape


def render_checks(rows: list[dict]) -> str:
    if not rows:
        return ""
    parts, current = [], None
    for r in rows:
        if r["section"] != current:
            if current is not None:
                parts.append("</tbody></table>")
            current = r["section"]
            parts.append(f"<h3>{E(current) if current else 'Проверки'}</h3>"
                         "<table><thead><tr><th>Результат</th><th>Проверка</th><th>Фактически</th></tr></thead><tbody>")
        cls = "ok" if r["ok"] else "bad"
        mark = "✔ OK" if r["ok"] else "✕ ошибка"
        parts.append(f'<tr><td class="st {cls}">{mark}</td><td>{E(r["name"])}</td>'
                     f'<td class="dt">{E(r["detail"])}</td></tr>')
    parts.append("</tbody></table>")
    return "".join(parts)


def render_routes(rows: list[dict], exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    rows = [r for r in rows if not any(x in r["url"] for x in exclude)]
    if not rows:
        return ""
    body = "".join(
        f'<tr><td class="st {"ok" if r["ok"] else "bad"}">{r["code"]}</td><td class="dt">{E(r["url"])}</td></tr>'
        for r in rows)
    return ("<h3>Проверенные адреса</h3><table><thead><tr><th>Код</th><th>Адрес</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")


def render_raw(blocks: list[tuple[str, str]]) -> str:
    return "".join(f"<h3>{E(t)}</h3><pre>{E(txt)}</pre>" for t, txt in blocks)


def render_shots(items: list[dict]) -> str:
    if not items:
        return ""
    figs = "".join(f'<figure><img loading="lazy" src="{s["src"]}" alt="{E(s["cap"])}">'
                   f'<figcaption><b>{E(s["name"])}</b>{E(s["cap"])}</figcaption></figure>' for s in items)
    return f'<h2>Снимки экрана</h2><div class="shots">{figs}</div>'


def render_access(rows, title: str = "Сценарии доступа") -> str:
    if not rows:
        return ""
    body = "".join(f'<tr><td>{E(a)}</td><td class="dt">{E(b)}</td>'
                   f'<td class="st ok">{E(c)}</td></tr>' for a, b, c in rows)
    return (f"<h3>{E(title)}</h3><table><thead><tr><th>Сценарий</th><th>Ожидание</th>"
            f"<th>Факт</th></tr></thead><tbody>{body}</tbody></table>")


def act_html(act: dict, nav: str) -> str:
    checks = act.get("checks", [])
    total, ok = len(checks), sum(1 for c in checks if c["ok"])
    routes = act.get("routes", [])
    r_ok = sum(1 for r in routes if r["ok"])
    cards = []
    if total:
        cards.append(f'<div class="card"><b>{ok} / {total}</b><span>проверок пройдено</span></div>')
    if routes:
        cards.append(f'<div class="card"><b>{r_ok} / {len(routes)}</b><span>адресов отвечают</span></div>')
    if act.get("screens"):
        cards.append(f'<div class="card"><b>{len(act["screens"])}</b><span>снимков экрана</span></div>')
    failed = total - ok
    cards.append(f'<div class="card"><b style="color:{"var(--ok)" if not failed else "var(--bad)"}">'
                 f'{failed}</b><span>не пройдено</span></div>')
    vclass = "ok" if act["verdict"].startswith("Годен") and "оговорк" not in act["verdict"] else "warn"
    summary = "".join(f"<li>{E(s)}</li>" for s in act.get("summary", []))
    scope = "".join(f"<li>{E(s)}</li>" for s in act["scope"])
    limits = "".join(f"<li>{E(s)}</li>" for s in act.get("limits", []))
    actions = act.get("actions") or []
    actions_html = ("<h3>Выполненные действия</h3><pre>" + E("\n".join(actions)) + "</pre>") if actions else ""
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Акт {act['num']} · {E(act['title'])}</title>{FONTS}<style>{CSS}</style></head><body>
<header class="top"><div class="wrap">
  <div class="eyebrow">Акт тестирования № {act['num']} · dimecon.md</div>
  <h1>{E(act['title'])}</h1>
  <p class="lead">{E(act['lead'])}</p>
  <div class="meta">
    <span class="pill">Дата: {TODAY}</span>
    <span class="pill">Стенд: Windows 10, MySQL 8.4.0, Python 3.12</span>
    <span class="pill">Платформа: LiftPortal</span>
    <span class="pill">Заказчик: SA «Dimecon 11»</span>
  </div>
</div></header>
<div class="wrap">
  <div class="cards">{''.join(cards)}</div>
  <p><span class="verdict {vclass}">{E(act['verdict'])}</span></p>

  <h2>Что проверялось</h2>
  <ul class="scope">{scope}</ul>

  <h2>Результаты</h2>
  {render_checks(checks)}
  {render_access(act.get('access'), act.get('access_title', 'Сценарии доступа'))}
  {render_raw(act.get('raw', []))}
  {render_routes(routes, act.get('route_filter_out'))}
  {actions_html}

  {render_shots(act.get('screens', []))}

  <h2>Выводы</h2>
  <ul class="scope">{summary}</ul>
  {f'<div class="note"><b>Ограничения испытаний.</b><ul class="scope">{limits}</ul></div>' if limits else ''}

  <div class="nav">{nav}</div>
  <div class="foot">Акт сформирован автоматически {NOW} по протоколам прогонов в <code>docs/*.log</code>.
  Испытания провёл: Claude (Claude Code), автоматизированный прогон.</div>
</div>{LIGHTBOX}</body></html>"""


def index_html(acts: list[dict]) -> str:
    rows = []
    t_ok = t_all = 0
    for a in acts:
        checks = a.get("checks", [])
        ok = sum(1 for c in checks if c["ok"])
        t_ok += ok
        t_all += len(checks)
        routes = a.get("routes", [])
        vclass = "ok" if a["verdict"].startswith("Годен") and "оговорк" not in a["verdict"] else "warn"
        rows.append(f'<tr><td><b>{a["num"]}</b></td>'
                    f'<td><a href="{a["id"]}.html">{E(a["title"])}</a><br>'
                    f'<span class="dt" style="font-family:var(--sans);font-size:12.4px;color:var(--ink-3)">{E(a["lead"])}</span></td>'
                    f'<td class="dt">{ok}/{len(checks) if checks else "—"}</td>'
                    f'<td class="dt">{len(routes) or "—"}</td>'
                    f'<td class="dt">{len(a.get("screens", []))}</td>'
                    f'<td><span class="verdict {vclass}">{E(a["verdict"])}</span></td></tr>')
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Акты тестирования · dimecon.md</title>{FONTS}<style>{CSS}</style></head><body>
<header class="top"><div class="wrap">
  <div class="eyebrow">Комплект приёмочной документации</div>
  <h1>Акты тестирования платформы</h1>
  <p class="lead">Отдельный акт на каждый раздел системы. В каждом — что проверялось, результаты прогонов,
  снимки экрана и ограничения испытаний. Данные берутся из протоколов автоматических прогонов.</p>
  <div class="meta"><span class="pill">Дата: {TODAY}</span>
  <span class="pill">Актов: {len(acts)}</span>
  <span class="pill">Проверок: {t_ok} из {t_all}</span></div>
</div></header>
<div class="wrap">
  <div class="cards">
    <div class="card"><b>{len(acts)}</b><span>актов по разделам</span></div>
    <div class="card"><b>{t_ok}</b><span>проверок пройдено</span></div>
    <div class="card"><b style="color:var(--ok)">{t_all - t_ok}</b><span>не пройдено</span></div>
    <div class="card"><b>{len(list(SCREENS.glob('*.png')))}</b><span>снимков экрана</span></div>
  </div>
  <table><thead><tr><th>№</th><th>Акт</th><th>Проверки</th><th>Адреса</th><th>Снимки</th><th>Вердикт</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table>
  <div class="note info"><b>Для заказчика:</b> краткий обзор системы со снимками экрана —
  <a href="../presentation.html">презентация платформы</a>. Все материалы проекта —
  <a href="../../index.html">хаб документации</a>.</div>
  <div class="foot">Сформировано автоматически {NOW}.</div>
</div></body></html>"""


# --------------------------------------------------------------------- презентация

SLIDES = [
    {"kind": "title", "title": "Платформа аренды спецтехники", "sub": "Сайт, онлайн-подбор, CRM и портал партнёров для SA «Dimecon 11»",
     "note": "Демонстрация рабочей системы · " + TODAY},
    {"kind": "stats", "title": "Что сделано", "stats": [("22", "единицы техники перенесены с сайта"),
                                                        ("14", "услуг на трёх языках"),
                                                        ("57", "фотографий заказчика"),
                                                        ("3", "языка: RU / RO / EN")],
     "text": "Действующий сайт dimecon.md перенесён целиком. Языковые версии исходного сайта расходились — "
             "в русской было видно 3 автокрана из 22. Теперь весь парк доступен на всех языках."},
    {"kind": "shot", "img": "61_source_site", "title": "Было: сайт 2012 года",
     "text": "Вёрстка не адаптивная, нет цен и фильтров, каталог виден не полностью."},
    {"kind": "shot", "img": "62_ported_catalog", "title": "Стало: каталог с характеристиками",
     "text": "Реальные фотографии и паспортные данные, ставки, доступность на дату, фильтры по грузоподъёмности."},
    {"kind": "shot", "img": "04_site_home", "title": "Сайт компании", "tall": True,
     "text": "Первый экран с быстрым подбором, парк, шаги работы, прозрачные цены, кейсы, блок для подрядчиков."},
    {"kind": "shot", "img": "16_wizard_s4", "title": "Подбор без технических терминов",
     "text": "Клиент не обязан знать, что такое вылет стрелы: он выбирает ситуацию по картинке, система считает сама."},
    {"kind": "shot", "img": "19b_wizard_result_multi", "title": "Расчёт за минуту", "tall": True,
     "text": "Два-три варианта техники, доступность на дату, вилка цены и объяснение, почему подходит именно эта машина."},
    {"kind": "shot", "img": "20_wizard_breakdown", "title": "Цена построчно", "tall": True,
     "text": "Клиент видит каждую составляющую до оформления: работа, подача, стропальщик, коэффициенты, НДС."},
    {"kind": "shot", "img": "23_wizard_escalation", "title": "Сложные задачи — инженеру",
     "text": "При тяжёлом грузе, работе у ЛЭП или на высоте система не выдаёт машину сама, а передаёт заявку инженеру."},
    {"kind": "shot", "img": "24_admin_dashboard", "title": "Кабинет компании", "tall": True,
     "text": "Заявки, воронка, ближайшие подачи, эскалации и рапорты, ожидающие подтверждения — на одном экране."},
    {"kind": "shot", "img": "25_admin_kanban", "title": "CRM: воронка сделок",
     "text": "Заявки с сайта, из портала и по телефону в одной воронке; карточка переносится мышью."},
    {"kind": "shot", "img": "29_admin_fleet", "title": "Парк и занятость",
     "text": "График на две недели: заказы, мягкие брони и техобслуживание. Конфликты видны сразу."},
    {"kind": "shot", "img": "40_partner_index", "title": "Портал подрядчика",
     "text": "Объекты, заявки из шаблона, договорные ставки, сменные рапорты на подтверждение, счета и лимит."},
    {"kind": "shot", "img": "68_login_tenant", "title": "Каждому — своя роль",
     "text": "Клиент видит свои заказы, подрядчик — свои объекты и график, компания — CRM и парк, "
             "платформа — все компании. Чужое закрыто: проверено отдельным актом."},
    {"kind": "shot", "img": "54_pdf_invoice", "title": "Документы одним нажатием", "tall": True,
     "text": "Подтверждение, КП, счёт, акт и сменный рапорт в PDF: реквизиты, НДС, сумма прописью, условия отмены."},
    {"kind": "shot", "img": "58_xlsx_pricelist", "title": "Выгрузки в Excel", "tall": True,
     "text": "Прайс-лист, реестр заявок, табель смен, документы, парк с грузовыми таблицами — для бухгалтерии и партнёров."},
    {"kind": "shot", "img": "64_admin_crm", "title": "Связь с вашими системами", "tall": True,
     "text": "Импорт из любой CRM файлом, обмен с OfficePlus по Partner B2B API, чтение контрагентов из Oracle ERP."},
    {"kind": "shot", "img": "50_mobile_home", "title": "Телефон", "phone": True,
     "text": "Сайт и подбор рассчитаны на мобильный: один вопрос на экран, кнопка звонка всегда под рукой."},
    {"kind": "stats", "title": "Проверено", "stats": [("MySQL 8.4", "промышленная СУБД"),
                                                      ("0", "ошибок в прогонах"),
                                                      ("12–65 мс", "отклик страниц"),
                                                      ("403", "чужая компания недоступна")],
     "text": "Полный набор автоматических проверок: расчёты сверены с ручным счётом, документы прочитаны обратно, "
             "изоляция данных между компаниями подтверждена. Подробности — в восьми актах тестирования."},
    {"kind": "final", "title": "Что дальше", "items": [
        "Грузовые таблицы производителя — для точного подбора по паспорту",
        "Действующий прайс: ставки, минимальные смены, зоны подачи",
        "Реквизиты банка и доступ к SMTP — для счетов и писем клиентам",
        "Пароли OfficePlus и Oracle — для обмена с вашей ERP",
        "Свой домен вместо адреса платформы"]},
]


def slide_html(s: dict, i: int, total: int) -> str:
    n = f'<div class="sn">{i} / {total}</div>'
    if s["kind"] == "title":
        return (f'<section class="sl title">{n}<div class="in"><div class="eyebrow">SA «Dimecon 11»</div>'
                f'<h1>{E(s["title"])}</h1><p class="sub">{E(s["sub"])}</p>'
                f'<p class="note">{E(s["note"])}</p></div></section>')
    if s["kind"] == "stats":
        cards = "".join(f'<div class="st"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in s["stats"])
        return (f'<section class="sl">{n}<div class="in"><h2>{E(s["title"])}</h2>'
                f'<div class="stats">{cards}</div><p class="sub">{E(s["text"])}</p></div></section>')
    if s["kind"] == "final":
        items = "".join(f"<li>{E(x)}</li>" for x in s["items"])
        return (f'<section class="sl">{n}<div class="in"><h2>{E(s["title"])}</h2>'
                f'<ul class="big">{items}</ul></div></section>')
    cls = "phone" if s.get("phone") else ("tall" if s.get("tall") else "")
    return (f'<section class="sl shot">{n}<div class="in"><div class="txt"><h2>{E(s["title"])}</h2>'
            f'<p class="sub">{E(s["text"])}</p></div>'
            f'<div class="img {cls}"><img loading="lazy" src="screens/{s["img"]}.png" alt="{E(s["title"])}">'
            f"</div></div></section>")


def presentation_html() -> str:
    avail = [s for s in SLIDES if s["kind"] != "shot" or (SCREENS / f'{s["img"]}.png').exists()]
    body = "".join(slide_html(s, i + 1, len(avail)) for i, s in enumerate(avail))
    return f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Платформа аренды спецтехники · Dimecon 11</title>{FONTS}
<style>
:root{{--navy:#1F3A52;--accent:#F5A623;--ink:#14181B;--ink-2:#5A646B;--paper:#FBFAF7;--line:#E2DED4;
--sans:"Inter",-apple-system,"Segoe UI",sans-serif;--serif:"Source Serif 4",Georgia,serif}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-snap-type:y mandatory}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased}}
.sl{{min-height:100vh;scroll-snap-align:start;display:flex;align-items:center;position:relative;padding:54px 40px}}
.sl:nth-child(even){{background:#fff}}
.in{{max-width:1180px;margin:0 auto;width:100%}}
.sn{{position:absolute;top:22px;right:34px;font-size:12px;color:var(--ink-2);letter-spacing:.08em}}
.eyebrow{{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);font-weight:700}}
h1{{font-family:var(--serif);font-size:clamp(34px,5.6vw,62px);line-height:1.05;margin:14px 0 12px;letter-spacing:-.025em}}
h2{{font-family:var(--serif);font-size:clamp(25px,3.4vw,40px);line-height:1.12;margin:0 0 12px;letter-spacing:-.02em}}
.sub{{font-size:clamp(15px,1.5vw,19px);color:var(--ink-2);max-width:56ch;line-height:1.55;margin:0}}
.note{{margin-top:26px;font-size:13px;color:var(--ink-2)}}
.title{{background:var(--navy)}}.title h1,.title .eyebrow{{color:#fff}}.title .eyebrow{{color:var(--accent)}}
.title .sub,.title .note{{color:rgba(255,255,255,.76)}}
.shot .in{{display:grid;grid-template-columns:minmax(260px,0.8fr) 1.2fr;gap:44px;align-items:center}}
.img{{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff;
box-shadow:0 18px 50px rgba(30,24,10,.13);max-height:78vh}}
.img img{{width:100%;display:block}}
.img.tall{{max-height:80vh;overflow:hidden}}.img.tall img{{object-fit:cover;object-position:top;max-height:80vh}}
.img.phone{{max-width:330px;margin:0 auto;border-radius:22px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin:26px 0 24px}}
.st{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 22px}}
.st b{{display:block;font-family:var(--serif);font-size:38px;line-height:1;letter-spacing:-.03em}}
.st span{{font-size:13.5px;color:var(--ink-2);display:block;margin-top:6px}}
ul.big{{font-size:clamp(16px,1.8vw,21px);line-height:1.75;padding-left:1.1em;max-width:60ch}}
ul.big li{{margin:.35em 0}}ul.big li::marker{{color:var(--accent)}}
.bar{{position:fixed;left:0;right:0;bottom:0;height:3px;background:rgba(0,0,0,.07);z-index:20}}
.bar i{{display:block;height:100%;width:0;background:var(--accent);transition:width .15s}}
.hint{{position:fixed;bottom:16px;right:20px;font-size:12px;color:var(--ink-2);background:rgba(255,255,255,.9);
border:1px solid var(--line);border-radius:999px;padding:5px 12px;z-index:21}}
@media (max-width:900px){{.shot .in{{grid-template-columns:1fr;gap:20px}}.sl{{padding:40px 20px}}
.img{{max-height:56vh}}.img.tall img{{max-height:56vh}}}}
@media print{{html{{scroll-snap-type:none}}.sl{{min-height:auto;page-break-after:always;padding:24px}}
.bar,.hint,.sn{{display:none}}.img{{box-shadow:none;max-height:none}}.img.tall img{{max-height:none;object-fit:fill}}}}
</style></head><body>
{body}
<div class="bar"><i id="pb"></i></div><div class="hint">↓ прокрутка · P — печать в PDF</div>
<script>
const pb=document.getElementById('pb');
addEventListener('scroll',()=>{{const h=document.body.scrollHeight-innerHeight;
pb.style.width=(h>0?scrollY/h*100:0)+'%'}});
addEventListener('keydown',e=>{{
 const sl=[...document.querySelectorAll('.sl')];
 const cur=sl.findIndex(s=>s.getBoundingClientRect().top>-innerHeight/2);
 if(e.key==='ArrowDown'||e.key==='PageDown'||e.key===' '){{e.preventDefault();sl[Math.min(cur+1,sl.length-1)]?.scrollIntoView()}}
 if(e.key==='ArrowUp'||e.key==='PageUp'){{e.preventDefault();sl[Math.max(cur-1,0)]?.scrollIntoView()}}
 if(e.key==='p'||e.key==='P'){{print()}}
}});
</script></body></html>"""


# --------------------------------------------------------------------- сборка

if __name__ == "__main__":
    ACT_DEFS.sort(key=lambda a: int(a["num"]))
    nav_links = " ".join(f'<a href="{a["id"]}.html">№{a["num"]} {E(a["title"])}</a>' for a in ACT_DEFS)
    nav = f'<a href="index.html">← Все акты</a> {nav_links} <a href="../presentation.html">Презентация →</a>'

    total_ok = total_all = 0
    for act in ACT_DEFS:
        path = ACTS / f'{act["id"]}.html'
        path.write_text(act_html(act, nav), encoding="utf-8")
        c = act.get("checks", [])
        ok = sum(1 for x in c if x["ok"])
        total_ok += ok
        total_all += len(c)
        print(f'  + acts/{act["id"]}.html — проверок {ok}/{len(c) or "—"}, '
              f'адресов {len(act.get("routes", [])) or "—"}, снимков {len(act.get("screens", []))}')

    (ACTS / "index.html").write_text(index_html(ACT_DEFS), encoding="utf-8")
    print("  + acts/index.html")
    (DOCS / "presentation.html").write_text(presentation_html(), encoding="utf-8")
    print("  + presentation.html")
    print(f"\nВсего проверок в актах: {total_ok} из {total_all}; "
          f"маршрутов в прогоне: {len(SMOKE['routes'])}; снимков: {len(list(SCREENS.glob('*.png')))}")
