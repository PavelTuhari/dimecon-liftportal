"""Проекты: задачи, подзадачи, зависимости, вехи, учёт времени, рентабельность, шаблоны.

Термины компании: проект — объект работ (стройплощадка, монтаж, длительная аренда),
задача — работа по объекту, веха — этап, который закрывается актом и счётом.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import (Document, Order, Project, Task, Timesheet, Shift, Tenant,
                      PurchaseOrder, SalesOrder)

STAGES = [("todo", "К выполнению"), ("doing", "В работе"), ("review", "На проверке"),
          ("done", "Готово"), ("cancelled", "Отменена")]
STAGE_NAMES = dict(STAGES)
PRIORITIES = {0: "обычная", 1: "важная", 2: "срочная"}
PROJECT_STAGES = [("planning", "Подготовка"), ("works", "Работы"),
                  ("handover", "Сдача"), ("closed", "Закрыт")]


# ------------------------------------------------------------------ задачи

def create_task(tenant: Tenant, project: Project | None, **fields) -> Task:
    seq = (db.query(func.max(Task.sequence)).filter_by(tenant_id=tenant.id,
                                                       project_id=project.id if project else None).scalar() or 0)
    task = Task(tenant_id=tenant.id, project_id=project.id if project else None, sequence=seq + 10, **fields)
    db.add(task)
    db.flush()
    return task


def blocked_by(task: Task) -> Task | None:
    """Задача, из-за которой нельзя начинать: зависимость ещё не завершена."""
    if not task.depends_on_id:
        return None
    dep = db.get(Task, task.depends_on_id)
    return dep if dep and dep.stage not in ("done", "cancelled") else None


def move_task(task: Task, stage: str) -> dict:
    """Перенос по стадиям с проверкой зависимости и запуском повторения."""
    result = {"ok": True, "stage": stage, "spawned": None}
    if stage in ("doing", "review", "done"):
        dep = blocked_by(task)
        if dep:
            return {"ok": False, "reason": f"сначала нужно завершить «{dep.title}»", "stage": task.stage}
    task.stage = stage
    task.done_at = datetime.utcnow() if stage == "done" else None
    if stage == "done":
        result["spawned"] = spawn_recurrence(task)
    db.commit()
    return result


def spawn_recurrence(task: Task) -> Task | None:
    """Повторяющаяся задача: при закрытии создаём следующую по расписанию."""
    rule = task.recurrence or {}
    every, unit = int(rule.get("every") or 0), rule.get("unit", "day")
    if every <= 0:
        return None
    step = {"day": 1, "week": 7, "month": 30}.get(unit, 1) * every
    base = task.due_on or date.today()
    nxt = base + timedelta(days=step)
    until = rule.get("until")
    if until and str(nxt) > str(until):
        return None
    clone = Task(tenant_id=task.tenant_id, project_id=task.project_id, title=task.title,
                 description=task.description, assignee_id=task.assignee_id, priority=task.priority,
                 planned_hours=task.planned_hours, starts_on=nxt - timedelta(days=1), due_on=nxt,
                 tags=task.tags, recurrence=task.recurrence, sequence=task.sequence + 1)
    db.add(clone)
    db.flush()
    return clone


def task_tree(tenant: Tenant, project: Project) -> list[dict]:
    """Иерархия работ: корневые задачи с подзадачами и суммарными часами."""
    rows = (db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id)
            .order_by(Task.sequence, Task.id).all())
    by_parent: dict[int | None, list[Task]] = {}
    for t in rows:
        by_parent.setdefault(t.parent_id, []).append(t)
    spent = spent_hours_by_task(project)

    def pack(task: Task, level: int) -> list[dict]:
        kids = by_parent.get(task.id, [])
        own = spent.get(task.id, 0)
        total = own + sum(spent.get(k.id, 0) for k in kids)
        node = {"task": task, "level": level, "spent": own, "spent_total": round(total, 2),
                "blocked": blocked_by(task), "children": len(kids)}
        out = [node]
        for kid in kids:
            out += pack(kid, level + 1)
        return out

    out: list[dict] = []
    for root in by_parent.get(None, []):
        out += pack(root, 0)
    return out


def spent_hours_by_task(project: Project) -> dict[int, float]:
    rows = (db.query(Timesheet.task_id, func.sum(Timesheet.hours))
            .filter(Timesheet.project_id == project.id).group_by(Timesheet.task_id).all())
    return {tid: float(h or 0) for tid, h in rows if tid}


def progress(tenant: Tenant, project: Project) -> dict:
    rows = db.query(Task.stage, func.count(Task.id)).filter_by(
        tenant_id=tenant.id, project_id=project.id).group_by(Task.stage).all()
    counts = {s: 0 for s, _ in STAGES}
    for stage, n in rows:
        counts[stage] = n
    total = sum(counts.values()) - counts["cancelled"]
    done = counts["done"]
    return {"counts": counts, "total": total, "done": done,
            "pct": round(done / total * 100) if total else 0}


# ------------------------------------------------------------------ учёт времени

def log_time(tenant: Tenant, project: Project, *, hours: float, user_id=None, task_id=None,
             work_date: date | None = None, note: str = "", billable: bool = True) -> Timesheet:
    ts = Timesheet(tenant_id=tenant.id, project_id=project.id, task_id=task_id, user_id=user_id,
                   work_date=work_date or date.today(), hours=hours, note=note, billable=billable,
                   cost_rate=project.hour_cost or 0, bill_rate=project.hour_rate or 0)
    db.add(ts)
    db.commit()
    return ts


def timesheet_totals(project: Project) -> dict:
    rows = db.query(Timesheet).filter_by(project_id=project.id).all()
    hours = sum(r.hours for r in rows)
    billable = sum(r.hours for r in rows if r.billable)
    cost = sum(r.hours * (r.cost_rate or 0) for r in rows)
    revenue = sum(r.hours * (r.bill_rate or 0) for r in rows if r.billable)
    not_invoiced = sum(r.hours * (r.bill_rate or 0) for r in rows if r.billable and not r.invoiced)
    return {"hours": round(hours, 2), "billable": round(billable, 2), "cost": round(cost, 2),
            "revenue": round(revenue, 2), "not_invoiced": round(not_invoiced, 2), "rows": len(rows)}


# ------------------------------------------------------------------ рентабельность

def profitability(tenant: Tenant, project: Project) -> dict:
    """План и факт по объекту: откуда пришли деньги и куда ушли.

    Доход: выставленные счета и акты по объекту плюс заказы техники, привязанные к объекту.
    Расход: заказы поставщикам по объекту и себестоимость отработанных часов.
    """
    invoiced = (db.query(func.coalesce(func.sum(Document.amount), 0))
                .filter(Document.tenant_id == tenant.id, Document.project_id == project.id,
                        Document.type.in_(("invoice", "act")), Document.status != "cancelled").scalar() or 0)
    paid = (db.query(func.coalesce(func.sum(Document.amount), 0))
            .filter(Document.tenant_id == tenant.id, Document.project_id == project.id,
                    Document.type == "invoice", Document.status == "paid").scalar() or 0)
    orders_amount = (db.query(func.coalesce(func.sum(Order.price_final), 0))
                     .filter(Order.tenant_id == tenant.id, Order.project_id == project.id).scalar() or 0)
    quoted = (db.query(func.coalesce(func.sum(SalesOrder.amount_total), 0))
              .filter(SalesOrder.tenant_id == tenant.id, SalesOrder.project_id == project.id,
                      SalesOrder.status.in_(("accepted", "confirmed", "invoiced"))).scalar() or 0)
    purchases = (db.query(func.coalesce(func.sum(PurchaseOrder.amount_total), 0))
                 .filter(PurchaseOrder.tenant_id == tenant.id, PurchaseOrder.project_id == project.id,
                         PurchaseOrder.status.in_(("confirmed", "received", "billed"))).scalar() or 0)
    ts = timesheet_totals(project)
    revenue = float(invoiced) or float(quoted) or float(orders_amount)
    cost = float(purchases) + ts["cost"]
    margin = revenue - cost
    return {
        "budget": project.budget_amount or 0, "planned_cost": project.planned_cost or 0,
        "planned_margin": (project.budget_amount or 0) - (project.planned_cost or 0),
        "revenue": round(revenue, 2), "invoiced": round(float(invoiced), 2), "paid": round(float(paid), 2),
        "quoted": round(float(quoted), 2), "orders": round(float(orders_amount), 2),
        "purchases": round(float(purchases), 2), "labour": ts["cost"], "hours": ts["hours"],
        "cost": round(cost, 2), "margin": round(margin, 2),
        "margin_pct": round(margin / revenue * 100, 1) if revenue else 0,
        "budget_used_pct": round(cost / project.planned_cost * 100) if project.planned_cost else 0,
    }


def dashboard(tenant: Tenant) -> dict:
    """Сводка по всем объектам: план против факта."""
    projects = (db.query(Project).filter_by(tenant_id=tenant.id, is_template=False)
                .order_by(Project.created_at.desc()).all())
    rows = []
    for p in projects:
        pr = profitability(tenant, p)
        pr["project"] = p
        pr["progress"] = progress(tenant, p)
        rows.append(pr)
    return {
        "rows": rows,
        "revenue": round(sum(r["revenue"] for r in rows), 2),
        "cost": round(sum(r["cost"] for r in rows), 2),
        "margin": round(sum(r["margin"] for r in rows), 2),
        "hours": round(sum(r["hours"] for r in rows), 2),
        "late": [r for r in rows if r["project"].ends_at and r["project"].ends_at < date.today()
                 and r["project"].status == "active"],
    }


# ------------------------------------------------------------------ вехи и шаблоны

def milestones(tenant: Tenant, project: Project) -> list[Task]:
    return (db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id, is_milestone=True)
            .order_by(Task.due_on).all())


def from_template(tenant: Tenant, template: Project, *, name: str, partner_id=None, contact_id=None,
                  starts_at: date | None = None) -> Project:
    """Новый объект по шаблону: копируются задачи, вехи, сроки сдвигаются от даты старта."""
    start = starts_at or date.today()
    shift = None
    if template.starts_at:
        shift = (start - template.starts_at).days
    project = Project(tenant_id=tenant.id, name=name, partner_id=partner_id, contact_id=contact_id,
                      code=template.code, address=template.address, stage="planning", status="active",
                      budget_amount=template.budget_amount, planned_cost=template.planned_cost,
                      hour_cost=template.hour_cost, hour_rate=template.hour_rate,
                      starts_at=start, notes=template.notes,
                      ends_at=(template.ends_at + timedelta(days=shift)) if (template.ends_at and shift is not None) else None)
    db.add(project)
    db.flush()
    src = db.query(Task).filter_by(tenant_id=tenant.id, project_id=template.id).order_by(Task.id).all()
    mapping: dict[int, Task] = {}
    for t in src:
        clone = Task(tenant_id=tenant.id, project_id=project.id, title=t.title, description=t.description,
                     stage="todo", priority=t.priority, planned_hours=t.planned_hours,
                     is_milestone=t.is_milestone, milestone_amount=t.milestone_amount, tags=t.tags,
                     sequence=t.sequence, recurrence=t.recurrence,
                     starts_on=(t.starts_on + timedelta(days=shift)) if (t.starts_on and shift is not None) else None,
                     due_on=(t.due_on + timedelta(days=shift)) if (t.due_on and shift is not None) else None)
        db.add(clone)
        db.flush()
        mapping[t.id] = clone
    for t in src:                              # связи восстанавливаем после создания всех задач
        clone = mapping[t.id]
        if t.parent_id and t.parent_id in mapping:
            clone.parent_id = mapping[t.parent_id].id
        if t.depends_on_id and t.depends_on_id in mapping:
            clone.depends_on_id = mapping[t.depends_on_id].id
    db.commit()
    return project


def timeline(tenant: Tenant, project: Project, days: int = 30) -> dict:
    """Данные для календарной ленты: задачи с датами в окне, слева направо."""
    start = min([t.starts_on for t in db.query(Task).filter_by(project_id=project.id).all()
                 if t.starts_on] or [date.today()])
    start = min(start, project.starts_at or start)
    grid = [start + timedelta(days=i) for i in range(days)]
    rows = []
    for t in db.query(Task).filter_by(tenant_id=tenant.id, project_id=project.id).order_by(Task.sequence).all():
        if not (t.starts_on or t.due_on):
            continue
        s = t.starts_on or t.due_on
        e = t.due_on or t.starts_on
        offset = (s - start).days
        length = max((e - s).days + 1, 1)
        if offset + length < 0 or offset > days:
            continue
        rows.append({"task": t, "offset": max(offset, 0), "length": min(length, days - max(offset, 0)),
                     "late": bool(e < date.today() and t.stage != "done")})
    return {"grid": grid, "rows": rows, "start": start}


def shifts_of_project(tenant: Tenant, project: Project) -> list[Shift]:
    """Сменные рапорты по заказам объекта — фактическая работа техники."""
    return (db.query(Shift).join(Order, Shift.order_id == Order.id)
            .filter(Shift.tenant_id == tenant.id, Order.project_id == project.id)
            .order_by(Shift.work_date.desc()).all())
