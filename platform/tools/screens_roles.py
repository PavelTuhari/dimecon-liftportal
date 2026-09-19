"""Снимки экранов по ролям для акта «Вход и роли».

Запуск (сервер поднят на BASE):
    ../.venv/Scripts/python tools/screens_roles.py [http://localhost:8090]

Снимаем то, что видит каждая роль после входа, и поведение формы при ошибках.
Файлы дописываются в docs/screens/, подписи — в docs/screens/index.txt.
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
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    shots.append((name, caption))
    print(f"  + {name}.png — {caption}")


def login(page, url: str, email: str, password: str = "demo1234"):
    page.goto(BASE + url, wait_until="networkidle")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", password)
    page.click("form button.primary")
    page.wait_for_load_state("networkidle")


def clear(ctx):
    ctx.clear_cookies()


ROLE_TOUR = [
    # (роль, страница входа, учётка, [(файл, маршрут, подпись)])
    ("Клиент", "/s/dimecon/account/login", "client@example.com", [
        ("70_role_client_home", "/s/dimecon/account/", "кабинет: заявки, статусы, документы"),
        ("71_role_client_order", "/s/dimecon/account/orders/1", "карточка заказа с документами и повтором"),
        ("72_role_client_profile", "/s/dimecon/account/profile", "профиль, телефон и язык интерфейса")]),
    ("Партнёр B2B", "/s/dimecon/account/login", "partner@example.com", [
        ("73_role_partner_home", "/s/dimecon/partner/", "рабочий стол: объекты, заявки, лимит"),
        ("74_role_partner_schedule", "/s/dimecon/partner/schedule", "график техники на 14 дней"),
        ("75_role_partner_docs", "/s/dimecon/partner/documents", "документы и счета партнёра")]),
    ("Владелец компании", "/s/dimecon/account/login", "owner@dimecon.md", [
        ("76_role_owner_home", "/s/dimecon/admin/", "сводка дня: заявки, подачи, эскалации"),
        ("77_role_owner_fleet", "/s/dimecon/admin/fleet", "парк компании и занятость"),
        ("78_role_owner_team", "/s/dimecon/admin/team", "команда компании и роли")]),
    ("Администратор платформы", "/login", "admin@platform.local", [
        ("79_role_admin_home", "/admin", "все компании платформы"),
        ("80_role_admin_mail", "/admin/mail", "журнал исходящих писем"),
        ("81_role_admin_tenant", "/s/sudlift/admin/", "вход в кабинет любой компании")]),
]

DENIED = [
    ("82_denied_client_partner", "client@example.com", "/s/dimecon/account/login",
     "/s/dimecon/partner/", "Клиенту закрыт портал партнёра"),
    ("83_denied_partner_admin", "partner@example.com", "/s/dimecon/account/login",
     "/s/dimecon/admin/", "Партнёру закрыт кабинет компании"),
    ("84_denied_owner_foreign", "owner@dimecon.md", "/s/dimecon/account/login",
     "/s/macara-nord/admin/", "Владельцу закрыт кабинет чужой компании"),
    ("85_denied_owner_platform", "owner@dimecon.md", "/s/dimecon/account/login",
     "/admin", "Владельцу закрыто администрирование платформы"),
]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = ctx.new_page()

        print("\n[1] Страницы входа")
        page.goto(f"{BASE}/s/dimecon/account/login", wait_until="networkidle")
        shot(page, "68_login_tenant", "Вход на сайте компании: кнопки демо-ролей", full=False)
        page.goto(f"{BASE}/login", wait_until="networkidle")
        shot(page, "69_login_platform", "Вход на платформу: демо-доступ в один клик", full=False)

        print("\n[2] Роли")
        for role, login_url, email, routes in ROLE_TOUR:
            clear(ctx)
            login(page, login_url, email)
            print(f"   {role} ({email}) → {page.url}")
            for name, route, caption in routes:
                page.goto(BASE + route, wait_until="networkidle")
                shot(page, name, f"{role}: {caption}")

        print("\n[3] Отказы в доступе")
        for name, email, login_url, route, caption in DENIED:
            clear(ctx)
            login(page, login_url, email)
            r = page.goto(BASE + route, wait_until="networkidle")
            shot(page, name, f"{caption} — HTTP {r.status}", full=False)

        print("\n[4] Ошибки ввода на форме входа")
        clear(ctx)
        page.goto(f"{BASE}/s/dimecon/account/login", wait_until="networkidle")
        page.fill("input[type=email]", "client@example.com")
        page.fill("input[type=password]", "неверный-пароль")
        page.click("form button.primary")
        page.wait_for_load_state("networkidle")
        shot(page, "86_login_wrong_password", "Неверный пароль: причина отказа названа прямо", full=False)

        page.goto(f"{BASE}/s/dimecon/account/login", wait_until="networkidle")
        page.fill("input[type=email]", "nobody@example.com")
        page.fill("input[type=password]", "demo1234")
        page.click("form button.primary")
        page.wait_for_load_state("networkidle")
        shot(page, "87_login_unknown_user", "Неизвестный адрес: предложено проверить адрес или зарегистрироваться",
             full=False)

        print("\n[5] Демо-вход одной кнопкой")
        clear(ctx)
        page.goto(f"{BASE}/s/dimecon/account/login", wait_until="networkidle")
        page.click("button.js-demo[data-email='partner@example.com']")
        page.wait_for_load_state("networkidle")
        shot(page, "88_demo_button_result", "Кнопка «Партнёр B2B» — вход выполнен без копирования пароля",
             full=False)

        browser.close()

    # подписи дописываем к уже снятым экранам, не затирая их
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
    print(f"\nГотово: {len(shots)} снимков по ролям, всего подписей {len(have)}")


if __name__ == "__main__":
    t0 = time.time()
    run()
    print(f"время: {time.time() - t0:.1f} c")
