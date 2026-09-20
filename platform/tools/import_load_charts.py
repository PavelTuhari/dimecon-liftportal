"""Загрузка паспортных грузовых таблиц из файла.

    ../.venv/Scripts/python tools/import_load_charts.py файл.xlsx [--tenant dimecon]
                                                       [--equipment КБ-403А] [--apply] [--keep-approx]

Без --apply скрипт только показывает, что распознал, и ничего не меняет.
Колонки распознаются по заголовкам: машина, вылет, грузоподъёмность, высота, конфигурация,
стрела, противовес — по-русски, по-румынски или по-английски.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Equipment, Tenant  # noqa: E402
from portal.services import loadcharts as lc  # noqa: E402


def arg(name: str, default=None):
    if name in sys.argv:
        idx = sys.argv.index(name)
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return default


if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    raise SystemExit(__doc__)

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"файл не найден: {path}")

slug = arg("--tenant", "dimecon")
machine = arg("--equipment")
apply_now = "--apply" in sys.argv
replace = "--keep-approx" not in sys.argv

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")

    default_eq = None
    if machine:
        index = lc.machine_index(tenant)
        default_eq = lc.match_machine(index, machine)
        if default_eq is None:
            raise SystemExit(f"машина «{machine}» не найдена в парке компании")

    headers, rows = lc.read_table(path.read_bytes(), path.name)
    if not headers:
        raise SystemExit("файл пуст или не распознан")
    mapping = lc.detect_mapping(headers)
    print("Колонки файла:")
    for idx, head in enumerate(headers):
        print(f"  {idx}: {head}  →  {mapping.get(idx, '— не используется —')}")

    parsed, report = lc.parse(tenant, headers, rows, mapping, default_equipment=default_eq)
    print(f"\n{report.line()}")
    for name, count in sorted(report.machines.items()):
        print(f"  {name:<28} строк: {count}")
    if report.unknown:
        print("\nНе найдены в парке: " + ", ".join(sorted(set(report.unknown))[:10]))
    for warn in report.warnings[:10]:
        print(f"  ! {warn}")

    problems = lc.validate(parsed)
    for p in problems[:10]:
        print(f"  !! {p}")

    if not apply_now:
        print("\nЭто предварительный разбор. Добавьте --apply, чтобы записать строки в парк.")
        sys.exit(0 if parsed and not problems else 1)

    applied = lc.apply(tenant, parsed, replace=replace)
    print(f"\nЗаписано: {applied.line()}")
    summary = lc.summary(tenant)
    print(f"Паспортные таблицы теперь у {summary['with_passport']} из {summary['machines']} машин, "
          f"строк всего {summary['chart_rows']}")
