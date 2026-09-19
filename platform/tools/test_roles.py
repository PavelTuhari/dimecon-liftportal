"""Проверка входа и прав каждой роли.

Запуск (сервер поднят на BASE):
    ../.venv/Scripts/python tools/test_roles.py [http://127.0.0.1:8090]

Проверяем то, на чём заказчик споткнулся: вход демо-ролями, устойчивость формы к
копированию подсказки (пробелы, невидимые символы, разделители), понятность отказа
и разграничение доступа после входа.
"""
from __future__ import annotations

import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8090").rstrip("/")
# приложение может жить в подкаталоге домена: https://eminescu.md/TehnCons
PREFIX = urllib.parse.urlparse(BASE).path.rstrip("/")
LOG: list[str] = []
passed = failed = 0

ROLES = {
    "client@example.com": ("Клиент", "/s/dimecon/account/login", "/s/dimecon/account/"),
    "partner@example.com": ("Партнёр B2B", "/s/dimecon/account/login", "/s/dimecon/partner/"),
    "owner@dimecon.md": ("Владелец компании", "/s/dimecon/account/login", "/s/dimecon/admin/"),
    "admin@platform.local": ("Администратор платформы", "/login", "/admin"),
}


def out(line: str = ""):
    print(line)
    LOG.append(line)


def section(title: str):
    out("")
    out(f"=== {title} ===")


def check(ok: bool, name: str, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    out(f"  {'OK' if ok else 'ОШИБКА'}   {name}" + (f" — {detail}" if detail else ""))
    return ok


class Client:
    """Сессия браузера: cookies, CSRF со страницы, переходы по редиректам."""

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, path: str) -> tuple[int, str, str]:
        try:
            r = self.op.open(BASE + path)
            return r.status, r.read().decode("utf-8", "replace"), r.url
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), BASE + path

    def csrf(self, path: str) -> str:
        _, body, _ = self.get(path)
        m = re.search(r'name="_csrf"[^>]*value="([^"]+)"', body)
        return m.group(1) if m else ""

    def post(self, path: str, data: dict, token: str | None = None) -> tuple[int, str, str]:
        payload = dict(data)
        payload["_csrf"] = self.csrf(path) if token is None else token
        body = urllib.parse.urlencode(payload).encode()
        try:
            r = self.op.open(urllib.request.Request(BASE + path, data=body))
            return r.status, r.read().decode("utf-8", "replace"), r.url
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), BASE + path

    def login(self, path: str, email: str, password: str = "demo1234"):
        return self.post(path, {"email": email, "password": password})


def path_of(url: str) -> str:
    """Путь без префикса размещения — чтобы ожидания не зависели от слота на хостинге."""
    path = urllib.parse.urlparse(url).path
    if PREFIX and path.startswith(PREFIX):
        path = path[len(PREFIX):] or "/"
    return path


# ------------------------------------------------------------------ 1. вход ролями

section("1. ВХОД ДЕМО-ДОСТУПАМИ")
sessions: dict[str, Client] = {}
for email, (role, login_url, landing) in ROLES.items():
    c = Client()
    code, body, url = c.login(login_url, email)
    ok = code == 200 and path_of(url) == landing and "Неверный" not in body and "не подошёл" not in body
    check(ok, f"{role} ({email})", f"HTTP {code}, попал на {path_of(url)}")
    sessions[email] = c

section("2. КНОПКА ДЕМО-ВХОДА НА СТРАНИЦЕ")
for url, expect in [("/s/dimecon/account/login", ("client@example.com", "partner@example.com", "owner@dimecon.md")),
                    ("/login", ("admin@platform.local",))]:
    _, body, _ = Client().get(url)
    for email in expect:
        check(f'data-email="{email}"' in body, f"{url}: кнопка для {email}",
              "данные подставляются в форму, копировать не нужно")

# ------------------------------------------------------------------ 3. устойчивость формы

section("3. УСТОЙЧИВОСТЬ ФОРМЫ ВХОДА К ОШИБКАМ ВВОДА")
CASES = [
    ("пробелы вокруг адреса", "  client@example.com  ", "demo1234"),
    ("адрес заглавными буквами", "Client@Example.COM", "demo1234"),
    ("разделитель «·» из подсказки", "client@example.com ·", "demo1234"),
    ("неразрывный пробел в адресе", "client@example.com ", "demo1234"),
    ("невидимый символ в пароле", "client@example.com", "demo1234​"),
    ("перевод строки в конце пароля", "client@example.com", "demo1234\n"),
    ("пробел в конце пароля", "client@example.com", "demo1234 "),
]
for name, email, pw in CASES:
    code, body, url = Client().login("/s/dimecon/account/login", email, pw)
    check(code == 200 and path_of(url) == "/s/dimecon/account/", name, f"вход выполнен, {path_of(url)}")

section("4. ПОНЯТНОСТЬ ОТКАЗА")
code, body, _ = Client().login("/s/dimecon/account/login", "client@example.com", "wrong-pass")
check("Пароль не подошёл" in body, "неверный пароль назван своей причиной",
      "сообщение «Пароль не подошёл», а не общее «неверный e-mail или пароль»")
code, body, _ = Client().login("/s/dimecon/account/login", "nobody@example.com", "demo1234")
check("не найден" in body, "несуществующий адрес назван своей причиной", "сообщение «Пользователь … не найден»")

c = Client()
code, body, url = c.post("/s/dimecon/account/login",
                         {"email": "client@example.com", "password": "demo1234"}, token="устаревший-токен")
check(code == 200 and "устарела" in body, "устаревшая вкладка не даёт ошибку 400",
      f"HTTP {code}, показано предложение повторить ввод")

# ------------------------------------------------------------------ 5. права ролей

section("5. ПРАВА РОЛЕЙ ПОСЛЕ ВХОДА")
MATRIX = [
    ("client@example.com", "/s/dimecon/account/", 200, "свой кабинет"),
    ("client@example.com", "/s/dimecon/partner/", 403, "портал партнёра закрыт"),
    ("client@example.com", "/s/dimecon/admin/", 403, "кабинет компании закрыт"),
    ("client@example.com", "/admin", 403, "администрирование платформы закрыто"),
    ("partner@example.com", "/s/dimecon/partner/", 200, "свой портал"),
    ("partner@example.com", "/s/dimecon/partner/schedule", 200, "график техники"),
    ("partner@example.com", "/s/dimecon/admin/", 403, "кабинет компании закрыт"),
    ("partner@example.com", "/admin", 403, "администрирование платформы закрыто"),
    ("owner@dimecon.md", "/s/dimecon/admin/", 200, "свой кабинет компании"),
    ("owner@dimecon.md", "/s/dimecon/admin/fleet", 200, "свой парк"),
    ("owner@dimecon.md", "/s/macara-nord/admin/", 403, "кабинет чужой компании закрыт"),
    ("owner@dimecon.md", "/admin", 403, "администрирование платформы закрыто"),
    ("admin@platform.local", "/admin", 200, "панель платформы"),
    ("admin@platform.local", "/admin/mail", 200, "журнал почты"),
    ("admin@platform.local", "/s/dimecon/admin/", 200, "кабинет любой компании"),
    ("admin@platform.local", "/s/sudlift/admin/", 200, "кабинет любой компании"),
]
for email, path, expect, what in MATRIX:
    code, _, _ = sessions[email].get(path)
    check(code == expect, f"{ROLES[email][0]}: {path} → {what}", f"HTTP {code} (ожидалось {expect})")

section("6. БЕЗ ВХОДА")
anon = Client()
for path, what in [("/s/dimecon/account/", "кабинет клиента"), ("/s/dimecon/partner/", "портал партнёра"),
                   ("/s/dimecon/admin/", "кабинет компании"), ("/admin", "панель платформы")]:
    code, _, url = anon.get(path)
    check(code == 200 and "login" in path_of(url), f"аноним: {path} → {what}",
          f"перенаправление на {path_of(url)}")

section("7. ВЫХОД")
c = sessions["client@example.com"]
# токен берём с отрисованной страницы кабинета: у /logout нет GET-версии
code, _, url = c.post("/s/dimecon/account/logout", {}, token=c.csrf("/s/dimecon/account/"))
check(code == 200, "выход клиента выполнен", f"перенаправление на {path_of(url)}")
code, _, url = c.get("/s/dimecon/account/")
check("login" in path_of(url), "после выхода кабинет недоступен", f"перенаправление на {path_of(url)}")

out("")
out(f"ИТОГО: пройдено {passed}, ошибок {failed}")
with open("../docs/test_roles.log", "w", encoding="utf-8") as f:
    f.write("\n".join(LOG) + "\n")
sys.exit(1 if failed else 0)
