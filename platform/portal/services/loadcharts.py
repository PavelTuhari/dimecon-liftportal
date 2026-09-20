"""Грузовые таблицы производителя: разбор файла, проверка и загрузка в парк.

Пока у машины нет паспортной таблицы, подбор работает по ориентировочной кривой и
предупреждает об этом. Здесь — приём таблиц из файла (CSV или Excel), проверка их
осмысленности и замена ориентировочных строк паспортными.

Ожидаемые колонки (заголовки распознаются по-русски, по-румынски и по-английски):
    машина | вылет | грузоподъёмность | высота | конфигурация | стрела | противовес
Машина сопоставляется по инвентарному номеру, модели, slug или «бренд модель».
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime

from ..db import SessionLocal as db
from ..models import Equipment, LoadChart, Tenant

COLUMNS = {
    "equipment": ["машина", "техника", "модель", "utilaj", "model", "equipment", "кран", "инв", "inventory"],
    "radius": ["вылет", "радиус", "raza", "radius", "r,", "r "],
    "capacity": ["грузопод", "нагрузка", "capacit", "sarcina", "load", "q,", "q "],
    "height": ["высот", "inalt", "height", "h,", "h "],
    "configuration": ["конфиг", "исполн", "config", "стрела+", "jib", "гусёк", "гусек"],
    "boom": ["стрела", "brat", "boom"],
    "counterweight": ["противовес", "contragreutate", "counterweight", "балласт"],
}
NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass
class ChartReport:
    machines: dict[str, int] = field(default_factory=dict)   # название → сколько строк принято
    unknown: list[str] = field(default_factory=list)          # не нашли машину
    skipped: list[str] = field(default_factory=list)          # строки без чисел
    warnings: list[str] = field(default_factory=list)         # подозрительные данные
    rows: int = 0
    imported: int = 0
    replaced: int = 0

    @property
    def ok(self) -> bool:
        return self.imported > 0 and not self.unknown

    recognized: int = 0          # сколько строк удалось привязать к машинам при разборе

    def line(self) -> str:
        parts = [f"строк в файле: {self.rows}"]
        parts.append(f"принято: {self.imported}" if self.imported else f"распознано: {self.recognized}")
        if self.replaced:
            parts.append(f"заменено ориентировочных: {self.replaced}")
        if self.unknown:
            parts.append(f"не опознано машин: {len(set(self.unknown))}")
        if self.skipped:
            parts.append(f"пропущено строк: {len(self.skipped)}")
        return "; ".join(parts)


def read_table(data: bytes, filename: str) -> tuple[list[str], list[list[str]]]:
    """CSV или XLSX → заголовки и строки. Используется тот же разбор, что и в импорте CRM."""
    from .crm_import import read_table as _read
    return _read(data, filename)


def detect_mapping(headers: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for idx, head in enumerate(headers):
        low = (head or "").strip().lower()
        for field_name, needles in COLUMNS.items():
            if field_name in out.values():
                continue
            if any(n in low for n in needles):
                out[idx] = field_name
                break
    return out


def _num(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = NUM_RE.search(str(value).replace(" ", " "))
    return float(m.group(0).replace(",", ".")) if m else None


def _key(text: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", (text or "").lower())


def machine_index(tenant: Tenant) -> dict[str, Equipment]:
    """Все способы назвать машину в файле → карточка парка."""
    index: dict[str, Equipment] = {}
    for eq in db.query(Equipment).filter_by(tenant_id=tenant.id).all():
        title = eq.title.get("ru") if isinstance(eq.title, dict) else str(eq.title or "")
        for variant in (eq.inventory_no, eq.slug, eq.model, f"{eq.brand} {eq.model}", title):
            k = _key(variant)
            if k:
                index.setdefault(k, eq)
    return index


def match_machine(index: dict[str, Equipment], text: str) -> Equipment | None:
    k = _key(text)
    if not k:
        return None
    if k in index:
        return index[k]
    # частичное совпадение: «КБ-403А, паспорт 2019» → КБ-403А
    for key, eq in index.items():
        if len(key) >= 4 and (key in k or k in key):
            return eq
    return None


def parse(tenant: Tenant, headers: list[str], rows: list[list[str]], mapping: dict[int, str],
          default_equipment: Equipment | None = None) -> tuple[list[dict], ChartReport]:
    """Файл → список строк грузовой таблицы, привязанных к машинам."""
    rep = ChartReport(rows=len(rows))
    index = machine_index(tenant)
    parsed: list[dict] = []
    for row in rows:
        def cell(name: str):
            for idx, field_name in mapping.items():
                if field_name == name and idx < len(row):
                    return row[idx]
            return None

        radius, capacity = _num(cell("radius")), _num(cell("capacity"))
        if radius is None or capacity is None:
            rep.skipped.append(" | ".join(str(x) for x in row[:4]))
            continue
        eq = default_equipment
        raw_name = cell("equipment")
        if raw_name:
            found = match_machine(index, str(raw_name))
            if found is not None:
                eq = found
            elif default_equipment is None:
                rep.unknown.append(str(raw_name))
                continue
        if eq is None:
            rep.unknown.append(str(raw_name or "—"))
            continue
        if radius <= 0 or capacity <= 0:
            rep.warnings.append(f"{eq.model}: вылет {radius} и нагрузка {capacity} — строка пропущена")
            continue
        if capacity > (eq.capacity_t or 0) * 1.05 and eq.capacity_t:
            rep.warnings.append(f"{eq.model}: {capacity} т на вылете {radius} м больше паспортной "
                                f"грузоподъёмности {eq.capacity_t} т — проверьте файл")
        parsed.append({
            "equipment": eq, "radius_m": radius, "capacity_t": capacity,
            "height_m": _num(cell("height")) or 0,
            "configuration": str(cell("configuration") or "main").strip()[:80] or "main",
            "boom_m": _num(cell("boom")) or 0,
            "counterweight_t": _num(cell("counterweight")) or 0,
        })
        rep.machines[eq.model] = rep.machines.get(eq.model, 0) + 1
    rep.recognized = len(parsed)
    return parsed, rep


def validate(parsed: list[dict]) -> list[str]:
    """Здравый смысл таблицы: с ростом вылета грузоподъёмность не должна расти."""
    problems: list[str] = []
    by_machine: dict[int, list[dict]] = {}
    for row in parsed:
        by_machine.setdefault(row["equipment"].id, []).append(row)
    for rows in by_machine.values():
        rows.sort(key=lambda r: r["radius_m"])
        name = rows[0]["equipment"].model
        for prev, nxt in zip(rows, rows[1:]):
            if prev["configuration"] != nxt["configuration"]:
                continue
            if nxt["capacity_t"] > prev["capacity_t"] + 0.01:
                problems.append(f"{name}: на вылете {nxt['radius_m']:g} м указано {nxt['capacity_t']:g} т — "
                                f"больше, чем {prev['capacity_t']:g} т на {prev['radius_m']:g} м")
    return problems


def apply(tenant: Tenant, parsed: list[dict], *, replace: bool = True,
          doc_media_id: int | None = None) -> ChartReport:
    """Загрузка проверенных строк в парк. Ориентировочные строки машины заменяются."""
    rep = ChartReport(rows=len(parsed))
    touched: set[int] = set()
    for row in parsed:
        eq = row["equipment"]
        if replace and eq.id not in touched:
            # загружаемый файл — источник истины по этой машине: прежние строки убираем целиком,
            # иначе повторная загрузка паспорта удваивала бы таблицу
            old = db.query(LoadChart).filter_by(equipment_id=eq.id).all()
            for c in old:
                db.delete(c)
            rep.replaced += len(old)
            touched.add(eq.id)
        db.add(LoadChart(equipment_id=eq.id, configuration=row["configuration"],
                         radius_m=row["radius_m"], capacity_t=row["capacity_t"],
                         height_m=row["height_m"], boom_m=row["boom_m"],
                         counterweight_t=row["counterweight_t"], source="passport",
                         doc_media_id=doc_media_id, updated_at=datetime.utcnow()))
        rep.imported += 1
        rep.machines[eq.model] = rep.machines.get(eq.model, 0) + 1
    db.commit()
    return rep


def coverage(tenant: Tenant) -> list[dict]:
    """Состояние по каждой машине: есть ли паспортная таблица и сколько в ней строк."""
    out = []
    for eq in (db.query(Equipment).filter_by(tenant_id=tenant.id)
               .order_by(Equipment.sort, Equipment.capacity_t.desc()).all()):
        rows = db.query(LoadChart).filter_by(equipment_id=eq.id).all()
        passport = [r for r in rows if (r.source or "") == "passport"]
        approx = [r for r in rows if (r.source or "") != "passport"]
        out.append({
            "eq": eq, "rows": len(rows), "passport": len(passport), "approx": len(approx),
            "state": "passport" if passport else ("approx" if approx else "none"),
            "updated": max([r.updated_at for r in passport if r.updated_at], default=None),
            "configurations": sorted({r.configuration for r in rows if r.configuration}),
            "max_capacity": max([r.capacity_t for r in rows], default=0),
            "max_radius": max([r.radius_m for r in rows], default=0),
        })
    return out


def summary(tenant: Tenant) -> dict:
    rows = coverage(tenant)
    return {"machines": len(rows),
            "with_passport": len([r for r in rows if r["state"] == "passport"]),
            "approx_only": len([r for r in rows if r["state"] == "approx"]),
            "without": len([r for r in rows if r["state"] == "none"]),
            "chart_rows": sum(r["rows"] for r in rows)}


def template_csv() -> bytes:
    """Пустой образец файла — чтобы заказчику было куда вписать данные из паспорта."""
    lines = ["машина;вылет, м;грузоподъёмность, т;высота, м;конфигурация;стрела, м;противовес, т",
             "КБ-403А;10;8;30;main;30;10",
             "КБ-403А;16;5;28;main;30;10",
             "КБ-403А;25;2,5;25;main;30;10"]
    return ("﻿" + "\n".join(lines)).encode("utf-8")
