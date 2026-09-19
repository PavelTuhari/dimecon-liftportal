"""Сканирует проект и собирает манифест всех файлов для HTML-хаба документации.

Запуск из корня проекта:  python tools/build_manifest.py
Результат: manifest.json — его читает index.html.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "manifest.json"

SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", ".claude", "figma_Dimecon", "dist"}
SKIP_FILES = {"manifest.json"}
TEXT_EXT = {".md", ".log", ".txt", ".json", ".py", ".html", ".css", ".js", ".sql", ".yaml", ".yml", ".ini", ".cfg"}
VIEWERS = {
    ".md": "markdown", ".log": "text", ".txt": "text", ".json": "json", ".py": "code", ".sql": "code",
    ".css": "code", ".js": "code", ".html": "html", ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".svg": "image", ".pdf": "pdf", ".xlsx": "xlsx", ".csv": "csv", ".ttf": "binary",
    ".db": "binary", ".zip": "binary",
}

# порядок и подписи разделов хаба
GROUPS = [
    ("Проект", "Главный файл, правила ведения документации"),
    ("Техническое задание", "Тома 0–7 комплекта ТЗ v2.0"),
    ("Акты и отчёты", "Результаты испытаний и приёмки"),
    ("Протоколы испытаний", "Сырые журналы прогонов тестов"),
    ("Сгенерированные документы", "PDF и Excel, созданные платформой"),
    ("Скриншоты", "Экраны платформы и документов"),
    ("Исходные данные заказчика", "Выгрузка с dimecon.md"),
    ("Медиатека компании", "Фотографии техники, перенесённые с сайта заказчика"),
    ("Код платформы", "Приложение на Flask"),
    ("Шаблоны", "Jinja2-шаблоны интерфейса"),
    ("Интеграции", "Связь с экосистемой Artgranit / OfficePlus"),
    ("Инструменты и тесты", "Скрипты переноса, тестов и съёмки"),
    ("Схема и конфигурация", "DDL, зависимости, настройки"),
    ("Архив", "Предыдущие версии документов"),
]

DOC_TITLES = {
    "README.md": "Главный файл проекта",
    "00_Obzor_i_opcii.md": "Том 0. Обзор, опции, пакеты",
    "01_B2C_podborshchik.md": "Том 1. B2C: подборщик и заявка",
    "02_Pricing_engine.md": "Том 2. Движок ценообразования",
    "03_B2B_portal.md": "Том 3. B2B-портал партнёра",
    "04_Uderzhanie_klienta.md": "Том 4. Удержание клиента",
    "05_Model_dannyh_DDL.md": "Том 5. Модель данных и DDL",
    "06_Plan_realizacii.md": "Том 6. План реализации",
    "07_Figma_TZ.md": "Том 7. ТЗ для Figma",
    "AKT_testirovaniya.md": "Акт № 1: развёртывание MySQL и платформы",
    "AKT_testirovaniya_2_portirovanie.md": "Акт № 2: перенос сайта, расчёты, PDF и Excel",
    "platform/README.md": "Документация платформы",
    "platform/integration/INTEGRATION.md": "Интеграция с Artgranit и OfficePlus",
    "platform/portal/services/officeplus.py": "Клиент Partner B2B API (OfficePlus)",
    "platform/portal/services/crm_import.py": "Импорт данных из внешней CRM",
    "docs/test_officeplus.log": "Протокол: клиент Partner B2B API (33 проверки)",
    "docs/test_crm_import.log": "Протокол: импорт из CRM (24 проверки)",
    "docs/test_calc_docs.log": "Протокол: расчёты, заказы, PDF и Excel (50 проверок)",
    "docs/smoke_mysql.log": "Протокол: маршруты, роли, изоляция компаний",
    "docs/acceptance.log": "Протокол: СУБД, целостность, производительность",
    "docs/port.log": "Протокол переноса сайта заказчика",
    "docs/acts/index.html": "Акты тестирования: сводка по разделам",
    "docs/acts/01_infrastruktura.html": "Акт № 1. Инфраструктура и база данных",
    "docs/acts/02_sajt_zakazchika.html": "Акт № 2. Сайт заказчика и перенос содержимого",
    "docs/acts/03_podbor_i_raschet.html": "Акт № 3. Подбор техники и расчёт стоимости",
    "docs/acts/04_zakazy_crm.html": "Акт № 4. Заказы, формы и CRM компании",
    "docs/acts/05_b2b_portal.html": "Акт № 5. Портал партнёра B2B",
    "docs/acts/06_dokumenty.html": "Акт № 6. Документы: PDF и Excel",
    "docs/acts/07_bezopasnost.html": "Акт № 7. Мультиарендность и доступ",
    "docs/acts/08_integracii.html": "Акт № 8. Интеграции с экосистемой заказчика",
    "docs/acts/09_vhod_i_roli.html": "Акт № 9. Вход и роли пользователей",
    "docs/presentation.html": "Презентация платформы для заказчика",
    "docs/test_roles.log": "Протокол: вход и права ролей (40 проверок)",
    "docs/test_richtext.log": "Протокол: безопасный вывод текста из базы (16 проверок)",
    "platform/portal/richtext.py": "Безопасный вывод форматированного текста",
}


def group_of(rel: str) -> str:
    p = rel.replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    if p.startswith("backup/"):
        return "Архив"
    if p.startswith("docs/screens/"):
        return "Скриншоты"
    if p.startswith("docs/generated/"):
        return "Сгенерированные документы"
    if p.startswith("docs/dimecon_source/"):
        return "Исходные данные заказчика"
    if p.startswith("platform/uploads/"):
        return "Медиатека компании"
    if p.startswith("platform/assets/"):
        return "Схема и конфигурация"
    if p.startswith("docs/") and name.endswith(".md"):
        return "Акты и отчёты"
    if p.startswith("docs/"):
        return "Протоколы испытаний"
    if p.startswith("platform/integration/"):
        return "Интеграции"
    if p.startswith("platform/tools/"):
        return "Инструменты и тесты"
    if p.startswith("platform/portal/templates/"):
        return "Шаблоны"
    if p.startswith("platform/portal/") or p in ("platform/run.py", "platform/config.py"):
        return "Код платформы"
    if name.endswith(".sql") or name in ("requirements.txt", ".env.example", "docs.json", "launch.json"):
        return "Схема и конфигурация"
    if re.match(r"^\d\d_.*\.md$", name) or name == "docs.json":
        return "Техническое задание"
    if name.endswith(".md") and "/" not in p:
        return "Проект" if name == "README.md" else "Техническое задание"
    if name in ("index.html", "manifest.json"):
        return "Проект"
    return "Схема и конфигурация"


def human(size: int) -> str:
    for unit in ("Б", "КБ", "МБ"):
        if size < 1024 or unit == "МБ":
            return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} МБ"


def title_of(rel: str, name: str) -> str:
    if rel in DOC_TITLES:
        return DOC_TITLES[rel]
    if name in DOC_TITLES:
        return DOC_TITLES[name]
    return name


def caption_of(rel: str, name: str, screens_index: dict) -> str:
    if rel.startswith("docs/screens/"):
        return screens_index.get(name.rsplit(".", 1)[0], "")
    return ""


def main():
    screens_index = {}
    idx = ROOT / "docs" / "screens" / "index.txt"
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                key, cap = line.split("\t", 1)
                screens_index[key] = cap

    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES or path.suffix in (".pyc", ".db-wal", ".db-shm"):
            continue
        ext = path.suffix.lower()
        stat = path.stat()
        files.append({
            "path": rel,
            "name": path.name,
            "title": title_of(rel, path.name),
            "caption": caption_of(rel, path.name, screens_index),
            "group": group_of(rel),
            "ext": ext,
            "viewer": VIEWERS.get(ext, "text" if ext in TEXT_EXT else "binary"),
            "size": stat.st_size,
            "size_h": human(stat.st_size),
            "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
            "searchable": ext in TEXT_EXT and stat.st_size < 2_000_000,
        })

    order = {g: i for i, (g, _) in enumerate(GROUPS)}
    files.sort(key=lambda f: (order.get(f["group"], 99), f["path"]))
    manifest = {
        "project": "dimecon.md — ТЗ, платформа LiftPortal и документы",
        "generated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "groups": [{"name": g, "hint": h} for g, h in GROUPS],
        "files": files,
        "stats": {
            "files": len(files),
            "bytes": sum(f["size"] for f in files),
            "by_group": {g: sum(1 for f in files if f["group"] == g) for g, _ in GROUPS},
        },
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"файлов: {len(files)}, объём: {human(manifest['stats']['bytes'])}")
    for g, _ in GROUPS:
        n = manifest["stats"]["by_group"][g]
        if n:
            print(f"  {g:<32} {n}")
    print("манифест:", OUT)


if __name__ == "__main__":
    main()
