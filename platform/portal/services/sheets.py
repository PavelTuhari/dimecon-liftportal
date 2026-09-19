"""Таблицы: формулы, диапазоны, сводные срезы, диаграммы и живые данные из базы.

Считаем на сервере: клиент присылает содержимое ячеек, получает обратно вычисленные
значения. Формула начинается со знака «=», имена функций русские и английские.

Живые функции (данные компании прямо в ячейке):
    =ЗАЯВКИ("месяц")            — количество заявок за период
    =ВЫРУЧКА("месяц")           — сумма оплаченных счетов за период
    =ДОЛГ()                     — дебиторская задолженность
    =ТЕХНИКА("шт"|"тонн")       — парк: единиц или суммарная грузоподъёмность
    =ЧАСЫ("месяц")              — отработанные часы по табелям
    =ЗАКУПКИ("месяц")           — сумма заказов поставщикам
    =СВОДКА("orders";"stage";"count")  — срез: группировка и мера
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import Document, Equipment, Order, Payment, PurchaseOrder, Task, Tenant, Timesheet

CELL_RE = re.compile(r"^([A-Z]{1,2})(\d{1,4})$")
RANGE_RE = re.compile(r"\b([A-Z]{1,2}\d{1,4}):([A-Z]{1,2}\d{1,4})\b")
REF_RE = re.compile(r"\b([A-Z]{1,2}\d{1,4})\b")
FUNC_RE = re.compile(r"([A-ZА-ЯЁ_]{2,})\s*\(")
NUM_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")
MAX_DEPTH = 24

PERIODS = {"день": 1, "day": 1, "неделя": 7, "week": 7, "месяц": 30, "month": 30,
           "квартал": 90, "quarter": 90, "год": 365, "year": 365, "всё": 36500, "all": 36500}


# ------------------------------------------------------------------ адреса

def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def num_to_col(n: int) -> str:
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def expand_range(a: str, b: str) -> list[str]:
    ma, mb = CELL_RE.match(a), CELL_RE.match(b)
    if not (ma and mb):
        return []
    c1, r1 = col_to_num(ma.group(1)), int(ma.group(2))
    c2, r2 = col_to_num(mb.group(1)), int(mb.group(2))
    cells = []
    for r in range(min(r1, r2), max(r1, r2) + 1):
        for c in range(min(c1, c2), max(c1, c2) + 1):
            cells.append(f"{num_to_col(c)}{r}")
    return cells


# ------------------------------------------------------------------ вычисление

class Engine:
    def __init__(self, cells: dict, tenant: Tenant | None = None):
        self.cells = {k.upper(): v for k, v in (cells or {}).items()}
        self.tenant = tenant
        self.values: dict[str, object] = {}
        self.errors: dict[str, str] = {}
        self._stack: list[str] = []
        self._cycles: set[str] = set()

    def value(self, ref: str) -> object:
        ref = ref.upper()
        if ref in self.values:
            return self.values[ref]
        if ref in self._stack or len(self._stack) > MAX_DEPTH:
            # помечаем всю цепочку: иначе после возврата значение перезапишется нулём
            self.errors[ref] = "циклическая ссылка"
            self._cycles.update(self._stack + [ref])
            self.values[ref] = "#ЦИКЛ"
            return self.values[ref]
        raw = self.cells.get(ref, "")
        self._stack.append(ref)
        try:
            out = self._evaluate(raw, ref)
        finally:
            self._stack.pop()
        if ref in self._cycles:
            out = "#ЦИКЛ"
            self.errors.setdefault(ref, "циклическая ссылка")
        self.values[ref] = out
        return out

    def _evaluate(self, raw, ref: str):
        if raw is None or raw == "":
            return ""
        if isinstance(raw, (int, float)):
            return raw
        text = str(raw).strip()
        if not text.startswith("="):
            return _as_number(text)
        try:
            return self._formula(text[1:])
        except ZeroDivisionError:
            self.errors[ref] = "деление на ноль"
            return "#ДЕЛ/0"
        except Exception as exc:                       # noqa: BLE001 — показываем ошибку в ячейке
            self.errors[ref] = str(exc)[:120]
            return "#ОШИБКА"

    # --- разбор формулы -------------------------------------------------
    def _formula(self, expr: str):
        # порядок важен: живые функции подставляют числа, затем разделители, ссылки и имена
        expr = self._live(expr)
        expr = re.sub(r"(?<=\d),(?=\d)", ".", expr)   # запятая внутри числа — десятичная
        expr = expr.replace(";", ",")                  # аргументы разделяются точкой с запятой
        expr = self._ranges(expr)
        expr = self._refs(expr)
        expr = self._funcs(expr)
        expr = expr.replace("^", "**")
        # одиночное «=» в таблицах означает сравнение
        expr = re.sub(r"(?<![<>=!])=(?!=)", "==", expr)
        # после подстановок остаются только числа, операции сравнения и имена функций
        # из белого списка: ни кавычек, ни подчёркиваний, ни точечного доступа к атрибутам
        if not re.fullmatch(r"[-+*/()\[\],.%\s\d<>=!A-Z]*", expr):
            raise ValueError("недопустимые символы в формуле")
        return _round(eval(expr, {"__builtins__": {}}, _SAFE))   # noqa: S307 — выражение отфильтровано выше

    def _live(self, expr: str) -> str:
        """Функции живых данных вычисляются до арифметики и подставляются числом."""
        def repl(m):
            name = m.group(1).upper()
            args = [a.strip().strip('"\'') for a in (m.group(2) or "").split(";") if a.strip()]
            return str(live_value(self.tenant, name, args))
        pattern = re.compile(r"\b(ЗАЯВКИ|ВЫРУЧКА|ДОЛГ|ТЕХНИКА|ЧАСЫ|ЗАКУПКИ|ЗАДАЧИ|СВОДКА)\s*\(([^()]*)\)",
                             re.IGNORECASE)
        prev = None
        while prev != expr:
            prev = expr
            expr = pattern.sub(repl, expr)
        return expr

    def _ranges(self, expr: str) -> str:
        def repl(m):
            cells = expand_range(m.group(1), m.group(2))
            values = [_num(self.value(c)) for c in cells]
            return "[" + ",".join(str(v) for v in values) + "]"
        return RANGE_RE.sub(repl, expr)

    def _refs(self, expr: str) -> str:
        def repl(m):
            ref = m.group(1)
            if not CELL_RE.match(ref):
                return ref
            return str(_num(self.value(ref)))
        return REF_RE.sub(repl, expr)

    def _funcs(self, expr: str) -> str:
        def repl(m):
            name = m.group(1).upper()
            fn = FUNCS.get(name)
            if not fn:
                raise ValueError(f"неизвестная функция {name}")
            return f"{fn}("
        return FUNC_RE.sub(repl, expr)


def _as_number(text: str):
    t = text.replace(" ", "").replace(" ", "")
    if NUM_RE.match(t):
        return float(t.replace(",", "."))
    return text


def _num(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    v = _as_number(str(value))
    return float(v) if isinstance(v, (int, float)) else 0.0


def _round(value):
    if isinstance(value, float):
        return round(value, 6)
    return value


def _flat(args) -> list[float]:
    out = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out += _flat(a)
        elif isinstance(a, (int, float)):
            out.append(float(a))
        else:
            n = _as_number(str(a))
            if isinstance(n, (int, float)):
                out.append(float(n))
    return out


def f_sum(*a):
    return sum(_flat(a))


def f_avg(*a):
    v = _flat(a)
    return sum(v) / len(v) if v else 0


def f_count(*a):
    return len(_flat(a))


def f_min(*a):
    v = _flat(a)
    return min(v) if v else 0


def f_max(*a):
    v = _flat(a)
    return max(v) if v else 0


def f_round(x, digits=0):
    return round(float(x), int(digits))


def f_if(cond, a, b=0):
    return a if cond else b


def f_pct(part, whole):
    return round(float(part) / float(whole) * 100, 2) if float(whole) else 0


_SAFE = {
    "SUM": f_sum, "AVG": f_avg, "COUNT": f_count, "MIN": f_min, "MAX": f_max,
    "ROUND": f_round, "IF": f_if, "PCT": f_pct, "ABS": abs, "SQRT": math.sqrt, "POW": pow,
}

# русские и английские имена → внутренняя функция
FUNCS = {
    "СУММА": "SUM", "SUM": "SUM",
    "СРЗНАЧ": "AVG", "СРЕДНЕЕ": "AVG", "AVERAGE": "AVG", "AVG": "AVG",
    "СЧЁТ": "COUNT", "СЧЕТ": "COUNT", "COUNT": "COUNT",
    "МИН": "MIN", "MIN": "MIN", "МАКС": "MAX", "MAX": "MAX",
    "ОКРУГЛ": "ROUND", "ROUND": "ROUND",
    "ЕСЛИ": "IF", "IF": "IF",
    "ПРОЦЕНТ": "PCT", "PCT": "PCT",
    "МОДУЛЬ": "ABS", "ABS": "ABS", "КОРЕНЬ": "SQRT", "SQRT": "SQRT", "СТЕПЕНЬ": "POW", "POW": "POW",
}


# ------------------------------------------------------------------ живые данные

def _since(period: str) -> date:
    days = PERIODS.get((period or "месяц").lower(), 30)
    return date.today() - timedelta(days=days)


def live_value(tenant: Tenant | None, name: str, args: list[str]) -> float:
    if tenant is None:
        return 0
    name = name.upper()
    period = args[0] if args else "месяц"
    since = _since(period)
    if name == "ЗАЯВКИ":
        return int(db.query(func.count(Order.id)).filter(
            Order.tenant_id == tenant.id, Order.created_at >= datetime.combine(since, datetime.min.time())).scalar() or 0)
    if name == "ВЫРУЧКА":
        return round(float(db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.tenant_id == tenant.id, Payment.direction == "in", Payment.paid_on >= since).scalar() or 0), 2)
    if name == "ДОЛГ":
        from .invoicing import aging
        return aging(tenant)["total"]
    if name == "ТЕХНИКА":
        what = (args[0] if args else "шт").lower()
        q = db.query(Equipment).filter_by(tenant_id=tenant.id, is_published=True)
        if what in ("тонн", "т", "capacity"):
            return round(float(db.query(func.coalesce(func.sum(Equipment.capacity_t), 0))
                               .filter_by(tenant_id=tenant.id, is_published=True).scalar() or 0), 1)
        return q.count()
    if name == "ЧАСЫ":
        return round(float(db.query(func.coalesce(func.sum(Timesheet.hours), 0)).filter(
            Timesheet.tenant_id == tenant.id, Timesheet.work_date >= since).scalar() or 0), 2)
    if name == "ЗАКУПКИ":
        return round(float(db.query(func.coalesce(func.sum(PurchaseOrder.amount_total), 0)).filter(
            PurchaseOrder.tenant_id == tenant.id, PurchaseOrder.created_at >= datetime.combine(since, datetime.min.time()),
            PurchaseOrder.status != "cancelled").scalar() or 0), 2)
    if name == "ЗАДАЧИ":
        stage = args[0] if args else ""
        q = db.query(func.count(Task.id)).filter(Task.tenant_id == tenant.id)
        if stage:
            q = q.filter(Task.stage == stage)
        return int(q.scalar() or 0)
    if name == "СВОДКА":
        rows = pivot(tenant, args[0] if args else "orders",
                     args[1] if len(args) > 1 else "stage",
                     args[2] if len(args) > 2 else "count")
        return round(sum(r["value"] for r in rows), 2)
    return 0


PIVOT_SOURCES = {
    "orders": ("Заявки", Order, {"stage": Order.stage, "status": Order.status, "source": Order.source,
                                 "kind": Order.kind},
               {"count": func.count(Order.id), "amount": func.coalesce(func.sum(Order.price_final), 0)}),
    "invoices": ("Счета", Document, {"status": Document.status, "type": Document.type},
                 {"count": func.count(Document.id), "amount": func.coalesce(func.sum(Document.amount), 0)}),
    "purchases": ("Закупки", PurchaseOrder, {"status": PurchaseOrder.status},
                  {"count": func.count(PurchaseOrder.id),
                   "amount": func.coalesce(func.sum(PurchaseOrder.amount_total), 0)}),
    "tasks": ("Задачи", Task, {"stage": Task.stage, "priority": Task.priority},
              {"count": func.count(Task.id), "amount": func.coalesce(func.sum(Task.planned_hours), 0)}),
}


def pivot(tenant: Tenant, source: str, group: str, measure: str = "count") -> list[dict]:
    """Сводный срез: группируем записи компании и считаем меру."""
    conf = PIVOT_SOURCES.get(source)
    if not conf:
        return []
    _, model, groups, measures = conf
    # сравнивать выражения SQLAlchemy через «or» нельзя — проверяем наличие ключа явно
    col = groups[group] if group in groups else list(groups.values())[0]
    agg = measures[measure] if measure in measures else measures["count"]
    rows = (db.query(col, agg).filter(model.tenant_id == tenant.id)
            .group_by(col).order_by(agg.desc()).all())
    return [{"key": str(k if k is not None else "—"), "value": round(float(v or 0), 2)} for k, v in rows]


def pivot_to_cells(rows: list[dict], *, title: str, at: str = "A1") -> dict:
    """Срез в ячейки: заголовок, строки и итог формулой — таблица остаётся живой."""
    m = CELL_RE.match(at.upper())
    c0, r0 = (col_to_num(m.group(1)), int(m.group(2))) if m else (1, 1)
    cells = {f"{num_to_col(c0)}{r0}": title, f"{num_to_col(c0 + 1)}{r0}": "Значение"}
    for i, row in enumerate(rows, start=1):
        cells[f"{num_to_col(c0)}{r0 + i}"] = row["key"]
        cells[f"{num_to_col(c0 + 1)}{r0 + i}"] = row["value"]
    last = r0 + len(rows)
    if rows:
        cells[f"{num_to_col(c0)}{last + 1}"] = "Итого"
        cells[f"{num_to_col(c0 + 1)}{last + 1}"] = f"=СУММА({num_to_col(c0 + 1)}{r0 + 1}:{num_to_col(c0 + 1)}{last})"
    return cells


# ------------------------------------------------------------------ расчёт листа

def compute(sheet, tenant: Tenant | None = None) -> dict:
    """Вычисленные значения всех заполненных ячеек листа."""
    engine = Engine(sheet.cells or {}, tenant)
    for ref in list(engine.cells):
        engine.value(ref)
    return {"values": engine.values, "errors": engine.errors}


def conditional(sheet, values: dict) -> dict:
    """Условное форматирование: правила вида {"range": "B2:B9", "op": ">", "value": 0, "class": "ok"}."""
    out: dict[str, str] = {}
    for rule in (sheet.formats or {}).get("rules", []):
        cells = []
        rng = rule.get("range", "")
        if ":" in rng:
            a, b = rng.split(":", 1)
            cells = expand_range(a.strip().upper(), b.strip().upper())
        elif rng:
            cells = [rng.strip().upper()]
        for ref in cells:
            v = _num(values.get(ref, 0))
            target = float(rule.get("value", 0))
            op = rule.get("op", ">")
            hit = (v > target if op == ">" else v < target if op == "<" else
                   abs(v - target) < 1e-9 if op == "=" else v >= target if op == ">=" else v <= target)
            if hit:
                out[ref] = rule.get("class", "ok")
    return out


def chart_series(sheet, values: dict) -> list[dict]:
    """Данные диаграмм листа: подписи и значения по диапазонам."""
    out = []
    for chart in (sheet.charts or []):
        labels = _cells_of(chart.get("labels", ""))
        points = _cells_of(chart.get("values", ""))
        series = [{"label": str(values.get(l, "")), "value": _num(values.get(v, 0))}
                  for l, v in zip(labels, points)]
        top = max([s["value"] for s in series] or [0]) or 1
        for s in series:
            s["pct"] = round(s["value"] / top * 100, 1)
        out.append({"title": chart.get("title", "Диаграмма"), "kind": chart.get("kind", "bar"),
                    "series": series, "max": top})
    return out


def _cells_of(rng: str) -> list[str]:
    rng = (rng or "").upper().replace(" ", "")
    if ":" in rng:
        a, b = rng.split(":", 1)
        return expand_range(a, b)
    return [rng] if rng else []


def to_xlsx(sheet, values: dict) -> bytes:
    """Выгрузка в Excel: значения, а формулы — комментарием в примечании к листу."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = (sheet.name or "Лист")[:28]
    for ref, raw in (sheet.cells or {}).items():
        m = CELL_RE.match(ref.upper())
        if not m:
            continue
        val = values.get(ref.upper(), raw)
        cell = ws[ref.upper()]
        cell.value = val if not isinstance(val, str) or not val.startswith("#") else str(raw)
        if isinstance(val, (int, float)):
            cell.number_format = "#,##0.00"
            cell.alignment = Alignment(horizontal="right")
        if int(m.group(2)) == 1:
            cell.font = Font(bold=True)
    for col in range(1, (sheet.cols or 8) + 1):
        ws.column_dimensions[num_to_col(col)].width = 22
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


TEMPLATES = {
    "Отчёт по продажам": {
        "cells": {"A1": "Показатель", "B1": "Значение",
                  "A2": "Заявок за месяц", "B2": "=ЗАЯВКИ(\"месяц\")",
                  "A3": "Выручка за месяц", "B3": "=ВЫРУЧКА(\"месяц\")",
                  "A4": "Дебиторская задолженность", "B4": "=ДОЛГ()",
                  "A5": "Закупки за месяц", "B5": "=ЗАКУПКИ(\"месяц\")",
                  "A6": "Валовая разница", "B6": "=B3-B5",
                  "A7": "Доля закупок, %", "B7": "=ПРОЦЕНТ(B5;B3)"},
        "charts": [{"title": "Деньги за месяц", "kind": "bar", "labels": "A3:A5", "values": "B3:B5"}],
        "formats": {"rules": [{"range": "B6:B6", "op": "<", "value": 0, "class": "bad"},
                              {"range": "B6:B6", "op": ">", "value": 0, "class": "ok"}]},
    },
    "Загрузка парка": {
        "cells": {"A1": "Показатель", "B1": "Значение",
                  "A2": "Единиц техники", "B2": "=ТЕХНИКА(\"шт\")",
                  "A3": "Суммарная грузоподъёмность, т", "B3": "=ТЕХНИКА(\"тонн\")",
                  "A4": "Отработано часов за месяц", "B4": "=ЧАСЫ(\"месяц\")",
                  "A5": "Часов на единицу", "B5": "=ОКРУГЛ(B4/B2;1)"},
        "charts": [], "formats": {},
    },
    "Задачи по стадиям": {
        "cells": {"A1": "Стадия", "B1": "Задач",
                  "A2": "К выполнению", "B2": "=ЗАДАЧИ(\"todo\")",
                  "A3": "В работе", "B3": "=ЗАДАЧИ(\"doing\")",
                  "A4": "На проверке", "B4": "=ЗАДАЧИ(\"review\")",
                  "A5": "Готово", "B5": "=ЗАДАЧИ(\"done\")",
                  "A6": "Итого", "B6": "=СУММА(B2:B5)"},
        "charts": [{"title": "Задачи по стадиям", "kind": "bar", "labels": "A2:A5", "values": "B2:B5"}],
        "formats": {},
    },
}
