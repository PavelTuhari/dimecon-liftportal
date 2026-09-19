"""Продажи: коммерческие предложения, шаблоны, допработы, принятие клиентом, счёт.

Предложение и заказ — одна запись: пока статус draft/sent, это КП; после принятия
клиентом и подтверждения менеджером — заказ, по которому выставляется счёт и,
при необходимости, открывается объект работ.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import (Contact, Equipment, Partner, Product, Project, SalesLine, SalesOrder,
                      SalesTemplate, Service, Tenant)

STATUSES = [("draft", "Черновик"), ("sent", "Отправлено"), ("accepted", "Принято клиентом"),
            ("confirmed", "Подтверждено"), ("invoiced", "Выставлен счёт"), ("cancelled", "Отменено")]
STATUS_NAMES = dict(STATUSES)
OPEN_STATUSES = ("draft", "sent", "accepted", "confirmed")


def next_number(tenant: Tenant) -> str:
    year = date.today().year
    prefix = f"КП-{year}"
    n = (db.query(func.count(SalesOrder.id))
         .filter(SalesOrder.tenant_id == tenant.id, SalesOrder.number.like(f"{prefix}-%")).scalar() or 0) + 1
    return f"{prefix}-{n:04d}"


def create(tenant: Tenant, *, contact_id=None, partner_id=None, project_id=None, assignee_id=None,
           template: SalesTemplate | None = None, valid_days: int = 14, note: str = "") -> SalesOrder:
    so = SalesOrder(tenant_id=tenant.id, number=next_number(tenant), contact_id=contact_id,
                    partner_id=partner_id, project_id=project_id, assignee_id=assignee_id,
                    currency=tenant.currency or "MDL", note=note,
                    template_id=template.id if template else None,
                    valid_until=date.today() + timedelta(days=template.valid_days if template else valid_days))
    partner = db.get(Partner, partner_id) if partner_id else None
    if partner and partner.discount_pct:
        so.discount_pct = partner.discount_pct        # договорная скидка партнёра подставляется сразу
    db.add(so)
    db.flush()
    if template:
        so.terms = template.note
        for i, line in enumerate(template.lines or []):
            add_line(so, name=line.get("name", ""), qty=float(line.get("qty", 1)),
                     price=float(line.get("price", 0)), unit=line.get("unit", "шт"),
                     cost=float(line.get("cost", 0)), kind=line.get("kind", "text"),
                     ref_id=line.get("ref_id"), is_optional=bool(line.get("optional")), sequence=(i + 1) * 10)
    recalc(so)
    db.commit()
    return so


def add_line(so: SalesOrder, *, name: str, qty: float = 1, price: float = 0, unit: str = "шт",
             cost: float = 0, kind: str = "text", ref_id=None, discount_pct: float = 0,
             is_optional: bool = False, sequence: int | None = None) -> SalesLine:
    if sequence is None:
        sequence = (max([l.sequence for l in so.lines], default=0) or 0) + 10
    line = SalesLine(so_id=so.id, name=name, qty=qty, price=price, unit=unit, cost=cost, kind=kind,
                     ref_id=ref_id, discount_pct=discount_pct, is_optional=is_optional, sequence=sequence)
    db.add(line)
    db.flush()
    db.expire(so, ["lines"])   # иначе уже загруженный список строк останется без новой позиции
    return line


def add_from_catalog(so: SalesOrder, kind: str, ref_id: int, qty: float = 1) -> SalesLine | None:
    """Строка из парка, услуг или товаров — с ценой и единицей измерения из карточки."""
    tenant_id = so.tenant_id
    if kind == "equipment":
        eq = db.query(Equipment).filter_by(id=ref_id, tenant_id=tenant_id).first()
        if not eq:
            return None
        title = eq.title.get("ru") if isinstance(eq.title, dict) else str(eq.title)
        return add_line(so, name=title or f"{eq.brand} {eq.model}", qty=qty, unit="ч",
                        price=eq.hourly_rate or 0, kind=kind, ref_id=eq.id)
    if kind == "service":
        sv = db.query(Service).filter_by(id=ref_id, tenant_id=tenant_id).first()
        if not sv:
            return None
        title = sv.title.get("ru") if isinstance(sv.title, dict) else str(sv.title)
        return add_line(so, name=title, qty=qty, unit="усл.", price=sv.price_from or 0, kind=kind, ref_id=sv.id)
    if kind == "product":
        pr = db.query(Product).filter_by(id=ref_id, tenant_id=tenant_id).first()
        if not pr:
            return None
        title = pr.title.get("ru") if isinstance(pr.title, dict) else str(pr.title)
        return add_line(so, name=title, qty=qty, unit=pr.unit or "шт", price=pr.price or 0,
                        kind=kind, ref_id=pr.id)
    return None


def recalc(so: SalesOrder) -> SalesOrder:
    """Итоги: обязательные строки в сумму, необязательные — отдельной строкой «допработы»."""
    lines = so.lines if so.lines else db.query(SalesLine).filter_by(so_id=so.id).all()
    base = sum(l.amount for l in lines if not l.is_optional)
    optional = sum(l.amount for l in lines if l.is_optional)
    net = round(base * (1 - (so.discount_pct or 0) / 100), 2)
    vat = round(net * (so.vat_pct or 0) / 100, 2)
    so.amount_net = net
    so.amount_vat = vat
    so.amount_total = round(net + vat, 2)
    so.amount_optional = round(optional, 2)
    db.flush()
    return so


def margin(so: SalesOrder) -> dict:
    """Маржа по предложению: цена минус плановая себестоимость строк."""
    lines = so.lines or db.query(SalesLine).filter_by(so_id=so.id).all()
    revenue = sum(l.amount for l in lines if not l.is_optional)
    cost = sum((l.cost or 0) * l.qty for l in lines if not l.is_optional)
    value = revenue - cost
    return {"revenue": round(revenue, 2), "cost": round(cost, 2), "margin": round(value, 2),
            "pct": round(value / revenue * 100, 1) if revenue else 0}


def send(so: SalesOrder) -> SalesOrder:
    if so.status == "draft":
        so.status = "sent"
    db.commit()
    return so


def accept(so: SalesOrder, *, by_name: str, selected_optional: list[int] | None = None) -> SalesOrder:
    """Принятие клиентом по ссылке: выбранные допработы становятся обязательными строками."""
    from datetime import datetime
    for line in so.lines:
        if line.is_optional and selected_optional and line.id in selected_optional:
            line.is_optional = False
    recalc(so)
    so.status = "accepted"
    so.accepted_at = datetime.utcnow()
    so.accepted_by = by_name[:160]
    db.commit()
    return so


def confirm(so: SalesOrder, *, create_project: bool = False, project_name: str = "") -> SalesOrder:
    """Подтверждение менеджером. По желанию сразу открывается объект работ."""
    so.status = "confirmed"
    if create_project and not so.project_id:
        contact = db.get(Contact, so.contact_id) if so.contact_id else None
        name = project_name or f"Объект по {so.number}" + (f" — {contact.company or contact.name}" if contact else "")
        project = Project(tenant_id=so.tenant_id, name=name[:160], partner_id=so.partner_id,
                          contact_id=so.contact_id, status="active", stage="planning",
                          budget_amount=so.amount_total, planned_cost=margin(so)["cost"],
                          starts_at=date.today())
        db.add(project)
        db.flush()
        so.project_id = project.id
    db.commit()
    return so


def cancel(so: SalesOrder, reason: str = "") -> SalesOrder:
    so.status = "cancelled"
    if reason:
        so.note = (so.note + "\n" if so.note else "") + f"Отменено: {reason}"
    db.commit()
    return so


def save_as_template(so: SalesOrder, name: str) -> SalesTemplate:
    lines = [{"name": l.name, "qty": l.qty, "unit": l.unit, "price": l.price, "cost": l.cost,
              "kind": l.kind, "ref_id": l.ref_id, "optional": l.is_optional} for l in so.lines]
    tpl = SalesTemplate(tenant_id=so.tenant_id, name=name[:160], lines=lines, note=so.terms,
                        valid_days=14)
    db.add(tpl)
    db.commit()
    return tpl


def stats(tenant: Tenant) -> dict:
    """Воронка предложений: сколько в работе, сколько выиграно, средний чек и конверсия."""
    rows = db.query(SalesOrder.status, func.count(SalesOrder.id), func.coalesce(func.sum(SalesOrder.amount_total), 0)) \
        .filter(SalesOrder.tenant_id == tenant.id).group_by(SalesOrder.status).all()
    by = {s: {"count": 0, "amount": 0.0} for s, _ in STATUSES}
    for status, n, amount in rows:
        by.setdefault(status, {"count": 0, "amount": 0.0})
        by[status] = {"count": n, "amount": round(float(amount), 2)}
    sent = sum(by[s]["count"] for s in ("sent", "accepted", "confirmed", "invoiced") if s in by)
    won = by.get("confirmed", {}).get("count", 0) + by.get("invoiced", {}).get("count", 0)
    open_amount = sum(by[s]["amount"] for s in ("draft", "sent", "accepted") if s in by)
    won_amount = by.get("confirmed", {}).get("amount", 0) + by.get("invoiced", {}).get("amount", 0)
    total = sum(v["count"] for v in by.values())
    return {"by": by, "total": total, "sent": sent, "won": won, "open_amount": round(open_amount, 2),
            "won_amount": round(won_amount, 2),
            "conversion": round(won / sent * 100, 1) if sent else 0,
            "avg_check": round(won_amount / won, 2) if won else 0}


def expiring(tenant: Tenant, days: int = 3) -> list[SalesOrder]:
    """Предложения, у которых на днях истекает срок — повод позвонить клиенту."""
    limit = date.today() + timedelta(days=days)
    return (db.query(SalesOrder)
            .filter(SalesOrder.tenant_id == tenant.id, SalesOrder.status.in_(("sent", "accepted")),
                    SalesOrder.valid_until.isnot(None), SalesOrder.valid_until <= limit)
            .order_by(SalesOrder.valid_until).all())
