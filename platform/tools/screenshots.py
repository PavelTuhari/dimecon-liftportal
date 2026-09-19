"""Скриншоты всех ключевых экранов для акта тестирования.

Запуск (сервер должен быть поднят на BASE):
    ../.venv/Scripts/python tools/screenshots.py [http://localhost:8090]

Селекторы намеренно не зависят от языка интерфейса: клики идут по value радиокнопок
и служебным классам, а не по подписям.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8090"
OUT = Path("../docs/screens")
OUT.mkdir(parents=True, exist_ok=True)
shots: list[tuple[str, str]] = []


def shot(page, name: str, caption: str, full=True):
    if full:
        # sticky-элементы при съёмке страницы целиком «залипают» посреди макета и перекрывают поля
        page.add_style_tag(content=".wz-nav,.sticky-cta{position:static !important}")
    page.wait_for_timeout(350)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    shots.append((name, caption))
    print(f"  + {name}.png - {caption}")


def nxt(page):
    """Кнопка «Далее» в визарде."""
    page.click(".wz-nav button.primary")
    page.wait_for_load_state("networkidle")


def pick(page, value: str, name: str | None = None):
    sel = f"input[name={name}][value='{value}']" if name else f"input[value='{value}']"
    page.locator(sel).first.check(force=True)


def login(page, email: str, password: str = "demo1234"):
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", password)
    page.click("form button.primary")
    page.wait_for_load_state("networkidle")


def logout(page):
    page.goto(f"{BASE}/", wait_until="networkidle")
    try:
        page.click("header button", timeout=2500)
        page.wait_for_load_state("networkidle")
    except Exception:
        page.context.clear_cookies()


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU", device_scale_factor=1)
        page = ctx.new_page()

        print("\n[1] Платформа: маркетплейс и онбординг")
        page.goto(BASE, wait_until="networkidle")
        shot(page, "01_platform_marketplace", "Маркетплейс: каталог компаний на платформе")
        page.goto(f"{BASE}/register", wait_until="networkidle")
        shot(page, "02_platform_register", "Онбординг: регистрация новой компании")
        page.goto(f"{BASE}/pricing", wait_until="networkidle")
        shot(page, "03_platform_pricing", "Пакеты платформы BASE / PRO / MAX")

        print("\n[2] Публичный сайт компании Dimecon 11")
        page.goto(f"{BASE}/s/dimecon/", wait_until="networkidle")
        shot(page, "04_site_home", "Сайт компании: главная страница целиком (тема Dimecon)")
        page.goto(f"{BASE}/s/dimecon/?lang=ro", wait_until="networkidle")
        shot(page, "05_site_home_ro", "Тот же сайт на румынском языке", full=False)
        page.goto(f"{BASE}/s/dimecon/equipment?lang=ru", wait_until="networkidle")
        shot(page, "06_site_equipment", "Каталог техники с фасетными фильтрами")
        page.goto(f"{BASE}/s/dimecon/equipment", wait_until="networkidle"); page.click(".eq-card"); page.wait_for_load_state("networkidle")
        shot(page, "07_site_equipment_item", "Карточка техники: ТТХ, график грузоподъёмности, занятость")
        page.goto(f"{BASE}/s/dimecon/services", wait_until="networkidle")
        shot(page, "08_site_services", "Услуги компании")
        page.goto(f"{BASE}/s/dimecon/products", wait_until="networkidle")
        shot(page, "09_site_products", "Раздел «В продаже»")
        page.goto(f"{BASE}/s/dimecon/partners", wait_until="networkidle")
        shot(page, "10_site_partners", "Лендинг для подрядчиков и уровни партнёрства")

        print("\n[3] Другие арендаторы: проверка white-label")
        page.goto(f"{BASE}/s/macara-nord/", wait_until="networkidle")
        shot(page, "11_site_tenant2", "Вторая компания: свой бренд, цвета, парк, контакты", full=False)
        page.goto(f"{BASE}/s/sudlift/?lang=en", wait_until="networkidle")
        shot(page, "12_site_tenant3_en", "Третья компания на английском языке", full=False)

        print("\n[4] B2C-визард: сквозной сценарий")
        page.goto(f"{BASE}/s/dimecon/?lang=ru", wait_until="networkidle")
        page.goto(f"{BASE}/s/dimecon/calculator/reset", wait_until="networkidle")
        shot(page, "13_wizard_s1", "Шаг 1: что нужно сделать")
        pick(page, "place"); nxt(page)
        shot(page, "14_wizard_s2", "Шаг 2: пресеты груза и калькулятор массы")
        pick(page, "cabin6"); nxt(page)
        shot(page, "15_wizard_s3", "Шаг 3: высота подъёма в этажах")
        pick(page, "3", "height"); nxt(page)
        shot(page, "16_wizard_s4", "Шаг 4: вылет — схемы ситуаций вместо термина")
        pick(page, "fence"); nxt(page)
        shot(page, "17_wizard_s5", "Шаг 5: условия площадки")
        nxt(page)
        page.fill("input[name=start]", "2026-10-01T09:00")
        page.select_option("select[name=hours]", "4")
        page.fill("input[name=address]", "Chișinău, str. Ion Creangă 45")
        page.fill("input[name=distance]", "12")
        page.locator("input[name=flex]").check(force=True)
        shot(page, "18_wizard_s6", "Шаг 6: дата, длительность, гибкая дата со скидкой, адрес")
        nxt(page)
        shot(page, "19_wizard_result", "Результат подбора: варианты, доступность, вилка цены")
        for d in page.locator(".offer.optimal details").all():
            d.click()
        page.wait_for_timeout(400)
        shot(page, "20_wizard_breakdown", "Раскрытые «почему эта машина» и построчная детализация цены")
        page.fill("input[name=name]", "Ион Мунтяну")
        page.fill("input[name=phone]", "069 45 67 89")
        page.fill("input[name=email]", "test.client@example.md")
        page.fill("textarea[name=comment]", "Подъём бытовки на участок за забором")
        page.locator("#contact input[type=checkbox]").check(force=True)
        page.click("#contact button.primary")
        page.wait_for_load_state("networkidle")
        shot(page, "21_wizard_done", "Заявка принята: номер, параметры, цена, что дальше")
        print("   номер заявки:", page.locator("h1").first.inner_text().strip())
        page.click("a[href*='/track/']")
        page.wait_for_load_state("networkidle")
        shot(page, "22_track", "Отслеживание заявки по ссылке без входа в кабинет")

        print("\n[5] Эскалация к инженеру: 42 т и работа вблизи ЛЭП")
        page.goto(f"{BASE}/s/dimecon/calculator/reset", wait_until="networkidle")
        pick(page, "lift_height"); nxt(page)
        pick(page, "custom"); page.fill("#w", "42"); nxt(page)
        pick(page, "9", "height"); nxt(page)
        pick(page, "far"); nxt(page)
        pick(page, "power_line"); nxt(page)
        page.fill("input[name=address]", "Chișinău, промзона")
        nxt(page)
        shot(page, "23_wizard_escalation", "Эскалация: система не выдаёт машину, а передаёт инженеру с причинами")

        print("\n[5a] Подбор с несколькими вариантами (машина ближе к грузу)")
        page.goto(f"{BASE}/s/dimecon/calculator/reset", wait_until="networkidle")
        pick(page, "place"); nxt(page)
        pick(page, "cabin6"); nxt(page)
        pick(page, "3", "height"); nxt(page)
        pick(page, "sidewalk"); nxt(page)
        nxt(page)
        page.fill("input[name=address]", "Chișinău, str. Alba Iulia 10")
        page.fill("input[name=distance]", "8")
        nxt(page)
        shot(page, "19b_wizard_result_multi", "Подбор выдал несколько вариантов: «Оптимально» и «С запасом»")

        print("\n[6] Кабинет компании: CRM")
        login(page, "owner@dimecon.md")
        shot(page, "24_admin_dashboard", "Дашборд: KPI, воронка, ближайшие подачи, последние заявки")
        page.goto(f"{BASE}/s/dimecon/admin/orders", wait_until="networkidle")
        shot(page, "25_admin_kanban", "Канбан заявок с drag-and-drop по этапам сделки")
        page.goto(f"{BASE}/s/dimecon/admin/orders?view=list", wait_until="networkidle")
        shot(page, "26_admin_orders_list", "Реестр заявок: B2C и B2B вместе")
        page.goto(f"{BASE}/s/dimecon/admin/orders?view=list", wait_until="networkidle") or page.click("tbody a[href*=/admin/orders/]"); page.wait_for_load_state("networkidle")
        shot(page, "27_admin_order", "Карточка заявки: обработка, техника, документы, рапорты")
        page.goto(f"{BASE}/s/dimecon/admin/contacts", wait_until="networkidle")
        shot(page, "28_admin_contacts", "Контакты CRM с дедупликацией по телефону")
        page.goto(f"{BASE}/s/dimecon/admin/fleet", wait_until="networkidle")
        shot(page, "29_admin_fleet", "Парк техники и график занятости на 14 дней")
        page.click("table a[href*=admin/fleet/]") if False else page.goto(f"{BASE}/s/dimecon/admin/fleet", wait_until="networkidle") or page.click("tbody a[href*=/admin/fleet/]"); page.wait_for_load_state("networkidle")
        shot(page, "30_admin_equipment", "Карточка техники: тарифы, грузовые таблицы, импорт CSV")
        page.goto(f"{BASE}/s/dimecon/admin/content/services", wait_until="networkidle")
        shot(page, "31_admin_content", "Контент: услуги с индикацией заполненных переводов")
        page.goto(f"{BASE}/s/dimecon/admin/content/services", wait_until="networkidle") or page.click("tbody a[href*=/content/services/]"); page.wait_for_load_state("networkidle")
        shot(page, "32_admin_content_edit", "Редактор контента с вкладками RU / RO / EN")
        page.goto(f"{BASE}/s/dimecon/admin/media", wait_until="networkidle")
        shot(page, "33_admin_media", "Медиатека: загрузка файла или регистрация по внешнему URL")
        page.goto(f"{BASE}/s/dimecon/admin/partners", wait_until="networkidle")
        shot(page, "34_admin_partners", "Партнёры B2B: уровни, скидки, лимиты, приглашения")

        print("\n[7] Настройки white-label")
        page.goto(f"{BASE}/s/dimecon/admin/settings/branding", wait_until="networkidle")
        shot(page, "35_admin_branding", "Бренд компании: цвета, логотип, герой, FAQ, языки")
        page.goto(f"{BASE}/s/dimecon/admin/settings/mail", wait_until="networkidle")
        shot(page, "36_admin_smtp", "Собственный SMTP компании и журнал писем")
        page.goto(f"{BASE}/s/dimecon/admin/settings/storage", wait_until="networkidle")
        shot(page, "37_admin_storage", "Хранилище файлов: диск платформы, внешние ссылки или S3")
        page.goto(f"{BASE}/s/dimecon/admin/settings/pricing", wait_until="networkidle")
        shot(page, "38_admin_pricing", "Тарифы: коэффициенты, зоны подачи, допуслуги, скидки")
        page.goto(f"{BASE}/s/dimecon/admin/settings/team", wait_until="networkidle")
        shot(page, "39_admin_team", "Команда, собственный домен, API-ключ")
        page.goto(f"{BASE}/s/dimecon/admin/integrations", wait_until="networkidle")
        shot(page, "64_admin_crm", "Интеграция с внешней CRM: импорт выгрузки, сопоставление колонок, обмен данными")

        print("\n[8] Портал партнёра B2B")
        logout(page)
        login(page, "partner@example.com")
        shot(page, "40_partner_index", "Портал партнёра: рапорты на подтверждение, объекты, уровень")
        page.goto(f"{BASE}/s/dimecon/partner/projects/1", wait_until="networkidle")
        shot(page, "41_partner_project", "Объект: заявки, рапорты, создание заявки из шаблона")
        page.goto(f"{BASE}/s/dimecon/partner/schedule", wait_until="networkidle")
        shot(page, "42_partner_schedule", "График техники: свои брони видны, чужие — без деталей")
        page.goto(f"{BASE}/s/dimecon/partner/documents", wait_until="networkidle")
        shot(page, "43_partner_documents", "Документы, счета и кредитный лимит партнёра")

        print("\n[9] Кабинет частного клиента")
        logout(page)
        login(page, "client@example.com")
        shot(page, "44_account_index", "Кабинет клиента: активные заказы, история, повтор в один клик")
        page.goto(f"{BASE}/s/dimecon/account/", wait_until="networkidle") or page.click("tbody a[href*=/account/orders/]"); page.wait_for_load_state("networkidle")
        shot(page, "45_account_order", "Заказ клиента: параметры, расчёт, документы, история")

        print("\n[10] Суперадмин платформы")
        logout(page)
        login(page, "admin@platform.local")
        page.goto(f"{BASE}/admin", wait_until="networkidle")
        shot(page, "46_superadmin", "Суперадмин: все компании, статусы, пакеты, листинг")
        page.goto(f"{BASE}/admin/mail", wait_until="networkidle")
        shot(page, "47_superadmin_mail", "Журнал почты по всем компаниям")
        r = page.goto(f"{BASE}/s/macara-nord/admin/", wait_until="networkidle")
        shot(page, "48_isolation_ok", f"Контроль: суперадмин открывает кабинет любой компании (HTTP {r.status})", full=False)

        print("\n[11] Изоляция данных между компаниями")
        logout(page)
        login(page, "owner@dimecon.md")
        r = page.goto(f"{BASE}/s/macara-nord/admin/", wait_until="networkidle")
        shot(page, "49_isolation_403", f"Владелец Dimecon в кабинете чужой компании: HTTP {r.status}", full=False)
        print("   изоляция:", r.status)

        print("\n[12] Мобильная версия")
        mob = ctx.new_page()
        mob.set_viewport_size({"width": 390, "height": 844})
        mob.goto(f"{BASE}/s/dimecon/", wait_until="networkidle")
        shot(mob, "50_mobile_home", "Мобильная версия сайта, 390 px, со sticky-CTA", full=False)
        mob.goto(f"{BASE}/s/dimecon/calculator/reset", wait_until="networkidle")
        shot(mob, "51_mobile_wizard", "Мобильный визард: один вопрос на экран", full=False)
        mob.close()

        browser.close()

    (OUT / "index.txt").write_text("\n".join(f"{n}\t{c}" for n, c in shots), encoding="utf-8")
    print(f"\nГотово: {len(shots)} скриншотов в {OUT.resolve()}")


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"время: {time.time() - t0:.1f} c")
