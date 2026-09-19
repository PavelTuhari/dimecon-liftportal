"""Сборка пакета для демо-хостинга eminescu.md, слот TehnCons.

    python tools/build_deploy.py

Собирает в dist/TehnCons автономный комплект: приложение, фотографии заказчика,
готовую базу SQLite (на демо-сервере MySQL не предполагается), статическую
документацию и файлы обслуживания — systemd-юнит, блок nginx, скрипты установки.

Секреты в пакет не попадают: локальный .env исключён, для сервера создаётся свой
со случайным ключом сессий.
"""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "TehnCons"
APP = DIST / "app"
SITE = DIST / "docs_site"

SLOT = "TehnCons"
PREFIX = f"/{SLOT}"
PORT = 3005
REMOTE_DIR = f"/var/www/eminescu/{SLOT}"
HOST = "eminescu.md"

# что не уезжает на сервер ни при каких условиях
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache", "dist", ".idea", ".vscode"}
SKIP_FILES = {".env", "platform.db", "liftportal.db", ".DS_Store"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log~"}


def copy_tree(src: Path, dst: Path, keep=lambda rel: True) -> int:
    n = 0
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_FILES or path.suffix in SKIP_SUFFIX:
            continue
        if not keep(rel.as_posix()):
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            n += 1
    return n


def size_of(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return f"{total / 1024 / 1024:.1f} МБ"


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    APP.mkdir(parents=True)
    SITE.mkdir(parents=True)

    print("1. База данных SQLite: схема, демо-компании, перенос сайта заказчика")
    db_path = (APP / "data" / "liftportal.sqlite3")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["UPLOAD_DIR"] = str(ROOT / "platform" / "uploads")
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, "tools/port_dimecon.py"], cwd=str(ROOT / "platform"),
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit("перенос содержимого в базу пакета не выполнен")
    for line in r.stdout.splitlines():
        if line.startswith(("Перенесено", "Фотографии", "ГОТОВО")):
            print("   " + line)

    # демо-данные управленческих модулей: объекты, предложения, закупки, счета, таблицы
    r2 = subprocess.run([sys.executable, "tools/seed_erp.py"], cwd=str(ROOT / "platform"),
                        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r2.returncode != 0:
        print(r2.stdout[-1500:])
        print(r2.stderr[-1500:])
        raise SystemExit("демо-данные модулей в базу пакета не добавлены")
    for line in r2.stdout.splitlines():
        if line.strip() and not line.startswith("ГОТОВО"):
            print("   " + line.strip())

    # закрываем журнал: без этого на сервер уезжает файл, к которому нужны -wal и -shm,
    # и приложение падает с «database disk image is malformed»
    import sqlite3
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("VACUUM")
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    con.close()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()
    if integrity != "ok":
        raise SystemExit(f"база пакета повреждена: {integrity}")
    print(f"   база: {db_path.stat().st_size / 1024 / 1024:.1f} МБ, проверка целостности — {integrity}")

    print("2. Приложение")
    n = copy_tree(ROOT / "platform", APP)
    print(f"   файлов: {n}  ({size_of(APP)} вместе с фотографиями и базой)")

    print("3. Документация (хаб, акты, презентация, снимки)")
    def keep_docs(rel: str) -> bool:
        first = rel.split("/")[0]
        if first in ("platform", "dist", "figma_Dimecon"):
            return False
        return True
    n = copy_tree(ROOT, SITE, keep_docs)
    print(f"   файлов: {n}  ({size_of(SITE)})")

    print("4. Манифест документации для копии")
    sys.path.insert(0, str(ROOT / "tools"))
    import build_manifest  # noqa: E402
    build_manifest.ROOT, build_manifest.OUT = SITE, SITE / "manifest.json"
    build_manifest.main()
    # возвращаем сборщик на основной проект, иначе его манифест останется от копии
    build_manifest.ROOT, build_manifest.OUT = ROOT, ROOT / "manifest.json"
    build_manifest.main()

    print("5. Файлы обслуживания")
    (DIST / "deploy").mkdir(parents=True, exist_ok=True)
    write_files()

    print(f"\nГотово: {DIST}  ({size_of(DIST)})")
    print(f"Публичный адрес после установки: https://{HOST}{PREFIX}/")
    print(f"Документация:                    https://{HOST}{PREFIX}/docs/")


def write_files():
    env = DIST / "deploy" / "env.production"
    env.write_text(
        "# Конфигурация слота TehnCons на eminescu.md. Копируется в app/.env при установке.\n"
        f"PORT={PORT}\n"
        f"LISTEN=127.0.0.1:{PORT}\n"
        f"URL_PREFIX={SLOT}\n"
        "BEHIND_PROXY=1\n"
        "SESSION_COOKIE_SECURE=1\n"
        f"PLATFORM_HOST={HOST}\n"
        "PLATFORM_NAME=LiftPortal\n"
        f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
        f"DATABASE_URL=sqlite:///{REMOTE_DIR}/app/data/liftportal.sqlite3\n"
        f"UPLOAD_DIR={REMOTE_DIR}/app/uploads\n"
        f"DOCS_DIR={REMOTE_DIR}/docs_site\n",
        encoding="utf-8")

    (DIST / "deploy" / "tehncons.service").write_text(
        "[Unit]\n"
        "Description=TehnCons — LiftPortal (Flask + waitress)\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=opc\n"
        f"WorkingDirectory={REMOTE_DIR}/app\n"
        f"EnvironmentFile=-{REMOTE_DIR}/app/.env\n"
        f"Environment=PORT={PORT}\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        f"ExecStart={REMOTE_DIR}/venv/bin/python {REMOTE_DIR}/app/run.py\n"
        "Restart=always\n"
        "RestartSec=5\n"
        "StandardOutput=journal\n"
        "StandardError=journal\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n",
        encoding="utf-8")

    (DIST / "deploy" / "nginx_TehnCons.conf").write_text(
        "# Вставить в https-блок /etc/nginx/conf.d/eminescu.md.conf\n"
        "# строго перед финальным location / { try_files ... }\n"
        "# Перед правкой: sudo cp /etc/nginx/conf.d/eminescu.md.conf \\\n"
        "#                        /etc/nginx/conf.d/eminescu.md.conf.bak_$(date +%s)\n\n"
        "# --- TehnCons (LiftPortal, Flask SSR) ---\n"
        f"location {PREFIX}/ {{\n"
        f"    proxy_pass http://127.0.0.1:{PORT}{PREFIX}/;\n"
        "    proxy_http_version 1.1;\n"
        "    proxy_set_header Host $host;\n"
        "    proxy_set_header X-Real-IP $remote_addr;\n"
        "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "    proxy_set_header X-Forwarded-Proto $scheme;\n"
        "    proxy_redirect off;\n"
        "    client_max_body_size 32m;\n"
        "}\n\n"
        "# --- TehnCons: статика приложения и фотографии, длинный кэш ---\n"
        f"location {PREFIX}/static/ {{\n"
        f"    proxy_pass http://127.0.0.1:{PORT}{PREFIX}/static/;\n"
        "    proxy_http_version 1.1;\n"
        "    proxy_set_header Host $host;\n"
        "    expires 30d;\n"
        '    add_header Cache-Control "public";\n'
        "}\n\n"
        f"location {PREFIX}/media/ {{\n"
        f"    proxy_pass http://127.0.0.1:{PORT}{PREFIX}/media/;\n"
        "    proxy_http_version 1.1;\n"
        "    proxy_set_header Host $host;\n"
        "    expires 30d;\n"
        '    add_header Cache-Control "public";\n'
        "}\n",
        encoding="utf-8")

    (DIST / "deploy" / "remote_setup.sh").write_text(
        "#!/usr/bin/env bash\n"
        "# Установка слота TehnCons. Запускать на сервере из каталога слота.\n"
        "#   bash deploy/remote_setup.sh\n"
        "set -euo pipefail\n\n"
        f"SLOT_DIR={REMOTE_DIR}\n"
        f"PORT={PORT}\n\n"
        'echo "== 1. Окружение Python =="\n'
        'python3 -V\n'
        'if [ ! -d "$SLOT_DIR/venv" ]; then python3 -m venv "$SLOT_DIR/venv"; fi\n'
        '"$SLOT_DIR/venv/bin/pip" install --upgrade pip -q\n'
        '"$SLOT_DIR/venv/bin/pip" install -q -r "$SLOT_DIR/app/requirements.txt"\n\n'
        'echo "== 2. Конфигурация =="\n'
        'if [ ! -f "$SLOT_DIR/app/.env" ]; then cp "$SLOT_DIR/deploy/env.production" "$SLOT_DIR/app/.env"; fi\n'
        'mkdir -p "$SLOT_DIR/app/data"\n'
        'chown -R opc:opc "$SLOT_DIR"\n\n'
        'echo "== 3. Служба =="\n'
        'sudo cp "$SLOT_DIR/deploy/tehncons.service" /etc/systemd/system/tehncons.service\n'
        'sudo systemctl daemon-reload\n'
        'sudo systemctl enable --now tehncons\n'
        'sleep 3\n'
        'sudo systemctl status --no-pager tehncons | head -n 12\n\n'
        'echo "== 4. Проверка напрямую =="\n'
        f'curl -sS -o /dev/null -w "127.0.0.1:%{{http_code}} %{{url_effective}}\\n" '
        f'http://127.0.0.1:{PORT}{PREFIX}/ || true\n\n'
        'echo "== 5. nginx =="\n'
        'echo "Блок location — в deploy/nginx_TehnCons.conf. Вставьте его вручную:"\n'
        'echo "  sudo cp /etc/nginx/conf.d/eminescu.md.conf /etc/nginx/conf.d/eminescu.md.conf.bak_\\$(date +%s)"\n'
        'echo "  sudo \\$EDITOR /etc/nginx/conf.d/eminescu.md.conf   # вставить перед финальным location /"\n'
        'echo "  sudo nginx -t && sudo systemctl reload nginx"\n',
        encoding="utf-8", newline="\n")

    (DIST / "deploy" / "README.md").write_text(
        f"""# Слот TehnCons на {HOST}

Что внутри пакета:

| Каталог | Содержимое |
|---|---|
| `app/` | приложение LiftPortal (Flask + waitress), фотографии заказчика, готовая база SQLite |
| `docs_site/` | документация проекта: хаб, 9 актов тестирования, презентация, снимки экрана |
| `deploy/` | systemd-юнит, блок nginx, конфигурация, скрипт установки |

Параметры слота (из контракта, менять нельзя): порт **{PORT}**, каталог
**{REMOTE_DIR}**, юнит **tehncons.service**, префикс **{PREFIX}/**, владелец `opc:opc`.

## Установка

```bash
# 1. каталог слота (один раз)
sudo mkdir -p {REMOTE_DIR}
sudo chown -R opc:opc {REMOTE_DIR}

# 2. загрузка пакета (с локальной машины)
scp -r dist/TehnCons/* opc@СЕРВЕР:{REMOTE_DIR}/

# 3. установка (на сервере)
cd {REMOTE_DIR} && bash deploy/remote_setup.sh

# 4. nginx: бэкап, вставка блока из deploy/nginx_TehnCons.conf, проверка
sudo cp /etc/nginx/conf.d/{HOST}.conf /etc/nginx/conf.d/{HOST}.conf.bak_$(date +%s)
sudo nginx -t && sudo systemctl reload nginx
```

## Проверка

```bash
curl -I http://127.0.0.1:{PORT}{PREFIX}/
curl -k -H 'Host: {HOST}' -I https://127.0.0.1{PREFIX}/
curl -s https://{HOST}{PREFIX}/ | grep -o '<title>.*</title>'
```

## Что будет доступно

| Адрес | Что это |
|---|---|
| `https://{HOST}{PREFIX}/` | витрина платформы: список компаний |
| `https://{HOST}{PREFIX}/s/dimecon/` | сайт заказчика: парк, услуги, товары, расчёт |
| `https://{HOST}{PREFIX}/s/dimecon/calculator` | подбор техники и расчёт стоимости |
| `https://{HOST}{PREFIX}/docs/` | хаб документации |
| `https://{HOST}{PREFIX}/docs/docs/acts/index.html` | акты тестирования |
| `https://{HOST}{PREFIX}/docs/docs/presentation.html` | презентация для заказчика |

Демо-доступы на странице входа — кнопками: клиент, партнёр B2B, компания, платформа.

## Обновление

```bash
scp -r dist/TehnCons/app dist/TehnCons/docs_site opc@СЕРВЕР:{REMOTE_DIR}/
ssh opc@СЕРВЕР 'sudo systemctl restart tehncons'
```

## Границы прав соблюдены

Слушаем только порт {PORT}; пишем только в {REMOTE_DIR}; в nginx добавляются
только блоки `location {PREFIX}/…`; чужие слоты, финальный `location /`,
`/etc/letsencrypt/` и чужие юниты не трогаются; правка конфигурации — после бэкапа
и `nginx -t`.

## База данных

MySQL на демо-сервере не требуется: пакет содержит готовую базу SQLite со всем
перенесённым содержимым сайта заказчика (22 единицы техники, 14 услуг, товары,
страницы, 74 фотографии, демо-заявки). Приложение работает на ней без изменений;
при появлении MySQL достаточно поменять `DATABASE_URL` в `app/.env`.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
