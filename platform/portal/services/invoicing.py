"""Счета и оплаты: выставление, платежи и сверка, просрочка и напоминания,
авансы, поэтапные счета, кредит-ноты, повторяющиеся счета, дебиторка по срокам.

Счёт — запись Document типа invoice; кредит-нота — credit_note со ссылкой на исходный.
Статус считается по платежам: issued → partial → paid, а по сроку — overdue.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import (Contact, Document, Partner, Payment, Project, RecurringPlan, SalesLine,
                      SalesOrder, Task, Tenant, Timesheet)

TYPE_NAMES = {"invoice": "Счёт", "credit_note": "Кредит-нота", "act": "Акт", "quote": "КП",
              "confirmation": "Подтверждение", "bill": "Счёт поставщика"}
STATUS_NAMES = {"issued": "Выставлен", "partial": "Оплачен частично", "paid": "Оплачен",
                "overdue": "Просрочен", "cancelled": "Отменён"}


def next_number(tenant: Tenant, doc_type: str = "invoice") -> str:
    # префиксы берём из настроек компании, если владелец их задал
    prefixes = {"invoice": "СЧ", "credit_note": "КН", "act": "АКТ", "bill": "СП"}
    prefixes.update({k: v for k, v in (getattr(tenant, "doc_prefixes", None) or {}).items() if v})
    prefix = prefixes.get(doc_type, "ДОК")
    year = date.today().year
    n = (db.query(func.count(Document.id))
         .filter(Document.tenant_id == tenant.id, Document.type == doc_type,
                 Document.number.like(f"{prefix}-{year}-%")).scalar() or 0) + 1
    return f"{prefix}-{year}-{n:04d}"


def create_invoice(tenant: Tenant, *, amount: float, lines: list[dict] | None = None, contact_id=None,
                   partner_id=None, project_id=None, sales_id=None, order_id=None, plan_id=None,
                   payment_days: int | None = None, doc_type: str = "invoice", note: str = "",
                   issued_on: date | None = None) -> Document:
    issued = issued_on or date.today()
    if payment_days is None:   # срок оплаты по умолчанию — из настроек компании
        payment_days = getattr(tenant, "invoice_due_days", None) or 10
    doc = Document(tenant_id=tenant.id, type=doc_type, number=next_number(tenant, doc_type),
                   amount=round(amount, 2), currency=tenant.currency or "MDL", status="issued",
                   issued_at=issued, due_at=issued + timedelta(days=payment_days),
                   contact_id=contact_id, partner_id=partner_id, project_id=project_id,
                   sales_id=sales_id, order_id=order_id, plan_id=plan_id,
                   payload={"lines": lines or [], "note": note})
    db.add(doc)
    db.commit()
    return doc


def from_sales(tenant: Tenant, so: SalesOrder, *, advance_pct: float = 0, payment_days: int = 10) -> Document:
    """Счёт по подтверждённому предложению: полностью или авансом на долю суммы."""
    lines = [{"title": l.name, "qty": l.qty, "unit": l.unit, "price": l.price, "amount": l.amount}
             for l in so.lines if not l.is_optional]
    amount = so.amount_total
    note = ""
    if advance_pct:
        amount = round(so.amount_total * advance_pct / 100, 2)
        note = f"Аванс {advance_pct:g} % по предложению {so.number}"
        lines = [{"title": note, "qty": 1, "unit": "усл.", "price": amount, "amount": amount}]
    doc = create_invoice(tenant, amount=amount, lines=lines, contact_id=so.contact_id,
                         partner_id=so.partner_id, project_id=so.project_id, sales_id=so.id,
                         order_id=so.order_id, payment_days=payment_days, note=note or so.terms)
    so.status = "invoiced"
    db.commit()
    return doc


def from_milestone(tenant: Tenant, task: Task, *, payment_days: int = 10) -> Document:
    """Поэтапный счёт: закрываем веху объекта и выставляем её сумму."""
    project = db.get(Project, task.project_id)
    amount = task.milestone_amount or 0
    doc = create_invoice(tenant, amount=amount,
                         lines=[{"title": f"Этап: {task.title}", "qty": 1, "unit": "этап",
                                 "price": amount, "amount": amount}],
                         project_id=project.id if project else None,
                         partner_id=project.partner_id if project else None,
                         contact_id=project.contact_id if project else None,
                         payment_days=payment_days, note=f"Объект: {project.name}" if project else "")
    task.invoiced = True
    db.commit()
    return doc


def from_timesheets(tenant: Tenant, project: Project, *, payment_days: int = 10) -> Document | None:
    """Счёт по фактически отработанным часам, которые ещё не выставлялись."""
    rows = (db.query(Timesheet)
            .filter_by(tenant_id=tenant.id, project_id=project.id, billable=True, invoiced=False).all())
    rows = [r for r in rows if r.hours and (r.bill_rate or 0) > 0]
    if not rows:
        return None
    total = round(sum(r.hours * r.bill_rate for r in rows), 2)
    lines = [{"title": f"Работы {r.work_date:%d.%m.%Y}: {r.note or 'по объекту'}", "qty": r.hours,
              "unit": "ч", "price": r.bill_rate, "amount": round(r.hours * r.bill_rate, 2)} for r in rows]
    doc = create_invoice(tenant, amount=total, lines=lines, project_id=project.id,
                         partner_id=project.partner_id, contact_id=project.contact_id,
                         payment_days=payment_days, note=f"Объект: {project.name}")
    for r in rows:
        r.invoiced = True
    db.commit()
    return doc


# ------------------------------------------------------------------ платежи и статусы

def register_payment(tenant: Tenant, doc: Document, *, amount: float, on: date | None = None,
                     method: str = "bank", reference: str = "", user_id=None) -> Payment:
    p = Payment(tenant_id=tenant.id, document_id=doc.id, direction="in", amount=round(amount, 2),
                paid_on=on or date.today(), method=method, reference=reference, created_by=user_id)
    db.add(p)
    db.flush()
    refresh_status(doc)
    db.commit()
    return p


def paid_amount(doc: Document) -> float:
    return float(db.query(func.coalesce(func.sum(Payment.amount), 0))
                 .filter(Payment.document_id == doc.id, Payment.direction == "in").scalar() or 0)


def balance(doc: Document) -> float:
    return round((doc.amount or 0) - paid_amount(doc), 2)


def refresh_status(doc: Document) -> str:
    """Статус по фактам оплаты и сроку — без ручного проставления."""
    if doc.status == "cancelled":
        return doc.status
    paid = paid_amount(doc)
    if paid >= (doc.amount or 0) - 0.01:
        doc.status = "paid"
    elif paid > 0:
        doc.status = "partial"
    elif doc.due_at and doc.due_at < date.today():
        doc.status = "overdue"
    else:
        doc.status = "issued"
    db.flush()
    return doc.status


def refresh_all(tenant: Tenant) -> dict:
    rows = db.query(Document).filter(Document.tenant_id == tenant.id,
                                     Document.type.in_(("invoice", "act"))).all()
    counts = {}
    for doc in rows:
        st = refresh_status(doc)
        counts[st] = counts.get(st, 0) + 1
    db.commit()
    return counts


def credit_note(tenant: Tenant, doc: Document, *, amount: float | None = None, reason: str = "") -> Document:
    """Кредит-нота: возврат или исправление ранее выставленного счёта."""
    value = round(amount if amount is not None else doc.amount, 2)
    note = create_invoice(tenant, amount=value, doc_type="credit_note",
                          lines=[{"title": f"Корректировка счёта {doc.number}: {reason or 'возврат'}",
                                  "qty": 1, "unit": "усл.", "price": value, "amount": value}],
                          contact_id=doc.contact_id, partner_id=doc.partner_id,
                          project_id=doc.project_id, payment_days=0, note=reason)
    note.ref_document_id = doc.id
    if value >= (doc.amount or 0) - 0.01:
        doc.status = "cancelled"
    db.commit()
    return note


# ------------------------------------------------------------------ просрочка и напоминания

def overdue(tenant: Tenant) -> list[dict]:
    rows = (db.query(Document)
            .filter(Document.tenant_id == tenant.id, Document.type == "invoice",
                    Document.status.in_(("issued", "partial", "overdue")),
                    Document.due_at.isnot(None), Document.due_at < date.today())
            .order_by(Document.due_at).all())
    out = []
    for doc in rows:
        bal = balance(doc)
        if bal <= 0:
            continue
        out.append({"doc": doc, "balance": bal, "days": (date.today() - doc.due_at).days,
                    "paid": paid_amount(doc)})
    return out


def aging(tenant: Tenant) -> dict:
    """Дебиторка по срокам: не просрочено, 1–30, 31–60, 61–90, свыше 90 дней."""
    buckets = {"current": 0.0, "d1_30": 0.0, "d31_60": 0.0, "d61_90": 0.0, "d90": 0.0}
    rows = (db.query(Document)
            .filter(Document.tenant_id == tenant.id, Document.type == "invoice",
                    Document.status.in_(("issued", "partial", "overdue"))).all())
    detail = []
    for doc in rows:
        bal = balance(doc)
        if bal <= 0:
            continue
        days = (date.today() - doc.due_at).days if doc.due_at else 0
        key = ("current" if days <= 0 else "d1_30" if days <= 30 else
               "d31_60" if days <= 60 else "d61_90" if days <= 90 else "d90")
        buckets[key] += bal
        detail.append({"doc": doc, "balance": bal, "days": max(days, 0), "bucket": key})
    return {"buckets": {k: round(v, 2) for k, v in buckets.items()},
            "total": round(sum(buckets.values()), 2), "detail": detail}


def send_reminders(tenant: Tenant, *, min_days: int = 1) -> list[dict]:
    """Письма-напоминания по просроченным счетам, не чаще одного раза в день на счёт."""
    from ..mailer import send_mail
    sent = []
    for row in overdue(tenant):
        doc, days = row["doc"], row["days"]
        if days < min_days or doc.reminded_at == date.today():
            continue
        to = _recipient(doc)
        if not to:
            continue
        subject = f"Напоминание об оплате счёта {doc.number}"
        body = (f"Здравствуйте!\n\nСчёт {doc.number} от {doc.issued_at:%d.%m.%Y} на сумму "
                f"{doc.amount:,.2f} {doc.currency} не оплачен, срок истёк {doc.due_at:%d.%m.%Y} "
                f"({days} дн. назад). К оплате: {row['balance']:,.2f} {doc.currency}.\n\n"
                f"С уважением, {tenant.name}".replace(",", " "))
        send_mail(tenant, to, subject, body)
        doc.reminded_at = date.today()
        sent.append({"doc": doc, "to": to, "days": days, "balance": row["balance"]})
    db.commit()
    return sent


def _recipient(doc: Document) -> str:
    if doc.contact_id:
        contact = db.get(Contact, doc.contact_id)
        if contact and contact.email:
            return contact.email
    if doc.partner_id:
        partner = db.get(Partner, doc.partner_id)
        if partner and partner.email:
            return partner.email
    return ""


# ------------------------------------------------------------------ повторяющиеся счета

def plan_next_date(plan: RecurringPlan, base: date | None = None) -> date:
    base = base or date.today()
    step = {"month": 1, "quarter": 3, "year": 12}.get(plan.period, 1)
    month = base.month + step
    year = base.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(plan.day_of_month or 1, monthrange(year, month)[1])
    return date(year, month, day)


def run_recurring(tenant: Tenant, on: date | None = None) -> list[Document]:
    """Выставить счета по планам, срок которых наступил."""
    today = on or date.today()
    plans = (db.query(RecurringPlan)
             .filter(RecurringPlan.tenant_id == tenant.id, RecurringPlan.is_active.is_(True),
                     RecurringPlan.next_run.isnot(None), RecurringPlan.next_run <= today).all())
    out = []
    for plan in plans:
        lines = plan.lines or [{"title": plan.name, "qty": 1, "unit": "мес.",
                                "price": plan.amount, "amount": plan.amount}]
        doc = create_invoice(tenant, amount=plan.amount, lines=lines, contact_id=plan.contact_id,
                             partner_id=plan.partner_id, plan_id=plan.id,
                             payment_days=plan.payment_days, issued_on=plan.next_run,
                             note=f"Регулярный счёт: {plan.name}")
        plan.last_run = plan.next_run
        plan.next_run = plan_next_date(plan, plan.next_run)
        plan.issued_count = (plan.issued_count or 0) + 1
        out.append(doc)
    db.commit()
    return out


# ------------------------------------------------------------------ сводка

def summary(tenant: Tenant) -> dict:
    invoices = db.query(Document).filter(Document.tenant_id == tenant.id,
                                         Document.type == "invoice").all()
    issued = sum(d.amount for d in invoices if d.status != "cancelled")
    paid = sum(paid_amount(d) for d in invoices)
    ag = aging(tenant)
    month_start = date.today().replace(day=1)
    this_month = sum(d.amount for d in invoices if d.issued_at >= month_start and d.status != "cancelled")
    collected = (db.query(func.coalesce(func.sum(Payment.amount), 0))
                 .filter(Payment.tenant_id == tenant.id, Payment.direction == "in",
                         Payment.paid_on >= month_start).scalar() or 0)
    return {"count": len(invoices), "issued": round(issued, 2), "paid": round(paid, 2),
            "debt": ag["total"], "buckets": ag["buckets"],
            "overdue_count": len([1 for r in ag["detail"] if r["days"] > 0]),
            "this_month": round(this_month, 2), "collected_month": round(float(collected), 2),
            "avg_days_to_pay": _avg_days_to_pay(tenant)}


def _avg_days_to_pay(tenant: Tenant) -> float:
    rows = (db.query(Document.issued_at, func.min(Payment.paid_on))
            .join(Payment, Payment.document_id == Document.id)
            .filter(Document.tenant_id == tenant.id, Document.type == "invoice",
                    Document.status == "paid")
            .group_by(Document.id, Document.issued_at).all())
    days = [(paid - issued).days for issued, paid in rows if issued and paid]
    return round(sum(days) / len(days), 1) if days else 0
