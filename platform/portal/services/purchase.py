"""Закупки: запрос цены, заказ поставщику, приёмка, счёт поставщика, пополнение склада.

Поток: rfq (запрос цены) → sent (отправлен поставщикам) → confirmed (заказ подтверждён)
→ received (принято полностью или частично) → billed (счёт поставщика проведён).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from ..db import SessionLocal as db
from ..models import (Payment, Product, PurchaseAgreement, PurchaseLine, PurchaseOrder,
                      ReorderRule, Tenant, Vendor)

STATUSES = [("rfq", "Запрос цены"), ("sent", "Отправлен"), ("confirmed", "Подтверждён"),
            ("received", "Принято"), ("billed", "Счёт проведён"), ("cancelled", "Отменён")]
STATUS_NAMES = dict(STATUSES)


def next_number(tenant: Tenant) -> str:
    year = date.today().year
    prefix = f"ЗК-{year}"
    n = (db.query(func.count(PurchaseOrder.id))
         .filter(PurchaseOrder.tenant_id == tenant.id, PurchaseOrder.number.like(f"{prefix}-%")).scalar() or 0) + 1
    return f"{prefix}-{n:04d}"


def create(tenant: Tenant, *, vendor_id=None, project_id=None, agreement_id=None, note: str = "",
           expected_on: date | None = None, created_by=None) -> PurchaseOrder:
    vendor = db.get(Vendor, vendor_id) if vendor_id else None
    po = PurchaseOrder(tenant_id=tenant.id, number=next_number(tenant), vendor_id=vendor_id,
                       project_id=project_id, agreement_id=agreement_id, note=note,
                       currency=tenant.currency or "MDL", created_by=created_by,
                       expected_on=expected_on or (date.today() + timedelta(days=vendor.lead_days if vendor else 3)))
    db.add(po)
    db.flush()
    db.commit()
    return po


def add_line(po: PurchaseOrder, *, name: str, qty: float = 1, price: float = 0, unit: str = "шт",
             product_id=None) -> PurchaseLine:
    seq = (max([l.sequence for l in po.lines], default=0) or 0) + 10
    line = PurchaseLine(po_id=po.id, name=name, qty=qty, price=price, unit=unit,
                        product_id=product_id, sequence=seq)
    db.add(line)
    db.flush()
    db.expire(po, ["lines"])   # список строк перечитываем, иначе итог посчитается без новой
    recalc(po)
    return line


def recalc(po: PurchaseOrder) -> PurchaseOrder:
    """Итог заказа с учётом скидки рамочного соглашения, если оно указано."""
    lines = po.lines if po.lines else db.query(PurchaseLine).filter_by(po_id=po.id).all()
    net = sum(l.amount for l in lines)
    agreement = db.get(PurchaseAgreement, po.agreement_id) if po.agreement_id else None
    discount = float((agreement.terms or {}).get("discount_pct", 0)) if agreement else 0
    net = round(net * (1 - discount / 100), 2)
    po.amount_net = net
    po.amount_vat = round(net * (po.vat_pct or 0) / 100, 2)
    po.amount_total = round(po.amount_net + po.amount_vat, 2)
    db.flush()
    return po


def send(po: PurchaseOrder) -> PurchaseOrder:
    if po.status == "rfq":
        po.status = "sent"
    db.commit()
    return po


def confirm(po: PurchaseOrder) -> PurchaseOrder:
    po.status = "confirmed"
    vendor = db.get(Vendor, po.vendor_id) if po.vendor_id else None
    if vendor and not po.bill_due_on:
        po.bill_due_on = date.today() + timedelta(days=vendor.payment_days or 14)
    db.commit()
    return po


def receive(po: PurchaseOrder, quantities: dict[int, float] | None = None, on: date | None = None) -> dict:
    """Приёмка: по умолчанию принимаем всё заказанное, иначе — построчно.

    Принятое количество пополняет остаток товара на складе, если строка связана с карточкой.
    """
    quantities = quantities or {}
    received_lines = 0
    for line in po.lines:
        qty = quantities.get(line.id, line.qty if not quantities else 0)
        if qty <= 0:
            continue
        line.received_qty = min(line.qty, (line.received_qty or 0) + qty)
        received_lines += 1
        if line.product_id:
            product = db.get(Product, line.product_id)
            if product is not None:
                product.stock = (product.stock or 0) + qty
    full = all((l.received_qty or 0) >= l.qty for l in po.lines) if po.lines else False
    po.status = "received" if full else po.status if po.status == "received" else "confirmed"
    po.received_on = on or date.today()
    db.commit()
    return {"lines": received_lines, "full": full, "status": po.status}


def bill(po: PurchaseOrder, *, amount: float | None = None, due_on: date | None = None) -> PurchaseOrder:
    """Счёт поставщика: фиксируем сумму к оплате и срок."""
    po.billed_amount = round(amount if amount is not None else po.amount_total, 2)
    po.status = "billed"
    if due_on:
        po.bill_due_on = due_on
    db.commit()
    return po


def pay(po: PurchaseOrder, *, amount: float, on: date | None = None, method: str = "bank",
        reference: str = "", user_id=None) -> Payment:
    p = Payment(tenant_id=po.tenant_id, purchase_id=po.id, direction="out", amount=round(amount, 2),
                paid_on=on or date.today(), method=method, reference=reference, created_by=user_id)
    db.add(p)
    db.commit()
    return p


def paid_amount(po: PurchaseOrder) -> float:
    return float(db.query(func.coalesce(func.sum(Payment.amount), 0))
                 .filter(Payment.purchase_id == po.id, Payment.direction == "out").scalar() or 0)


def to_pay(tenant: Tenant) -> list[dict]:
    """Кредиторка: что должны поставщикам и когда срок."""
    rows = (db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant.id,
                                           PurchaseOrder.status == "billed").all())
    out = []
    for po in rows:
        paid = paid_amount(po)
        balance = round((po.billed_amount or po.amount_total) - paid, 2)
        if balance <= 0:
            continue
        overdue = bool(po.bill_due_on and po.bill_due_on < date.today())
        out.append({"po": po, "paid": paid, "balance": balance, "overdue": overdue,
                    "days": (date.today() - po.bill_due_on).days if po.bill_due_on else 0})
    return sorted(out, key=lambda r: (not r["overdue"], r["po"].bill_due_on or date.max))


# ------------------------------------------------------------------ пополнение склада

def check_reorder(tenant: Tenant, *, create_rfq: bool = True, user_id=None) -> list[dict]:
    """Правила пополнения: где остаток ниже минимума — готовим запрос цены поставщику.

    Заказы группируются по поставщику: один запрос на все его позиции.
    """
    rules = db.query(ReorderRule).filter_by(tenant_id=tenant.id, is_active=True).all()
    need: dict[int | None, list[dict]] = {}
    report = []
    for rule in rules:
        product = db.get(Product, rule.product_id)
        if product is None:
            continue
        stock = product.stock or 0
        if stock > rule.min_qty:
            continue
        qty = max((rule.max_qty or rule.min_qty) - stock, 1)
        title = product.title.get("ru") if isinstance(product.title, dict) else str(product.title)
        row = {"rule": rule, "product": product, "title": title, "stock": stock, "qty": qty}
        report.append(row)
        need.setdefault(rule.vendor_id, []).append(row)

    created = []
    if create_rfq:
        for vendor_id, rows in need.items():
            po = create(tenant, vendor_id=vendor_id, note="Автоматическое пополнение по правилам", created_by=user_id)
            for row in rows:
                add_line(po, name=row["title"], qty=row["qty"], unit=row["product"].unit or "шт",
                         price=row["product"].price or 0, product_id=row["product"].id)
                row["rule"].last_run_at = date.today()
            recalc(po)
            created.append(po)
        db.commit()
    for row in report:
        row["po"] = next((p for p in created if p.vendor_id == row["rule"].vendor_id), None)
    return report


# ------------------------------------------------------------------ аналитика

def vendor_stats(tenant: Tenant) -> list[dict]:
    """Анализ закупок: объём, число заказов, сроки поставки и доля просрочек по поставщику."""
    out = []
    for vendor in db.query(Vendor).filter_by(tenant_id=tenant.id).order_by(Vendor.name).all():
        orders = db.query(PurchaseOrder).filter_by(tenant_id=tenant.id, vendor_id=vendor.id).all()
        done = [p for p in orders if p.status in ("received", "billed")]
        late = [p for p in done if p.received_on and p.expected_on and p.received_on > p.expected_on]
        delays = [(p.received_on - p.expected_on).days for p in done if p.received_on and p.expected_on]
        out.append({
            "vendor": vendor, "orders": len(orders), "done": len(done),
            "amount": round(sum(p.amount_total for p in orders if p.status != "cancelled"), 2),
            "late": len(late), "late_pct": round(len(late) / len(done) * 100) if done else 0,
            "avg_delay": round(sum(delays) / len(delays), 1) if delays else 0,
            "open": len([p for p in orders if p.status in ("rfq", "sent", "confirmed")]),
        })
    return sorted(out, key=lambda r: -r["amount"])


def summary(tenant: Tenant) -> dict:
    rows = db.query(PurchaseOrder.status, func.count(PurchaseOrder.id),
                    func.coalesce(func.sum(PurchaseOrder.amount_total), 0)) \
        .filter(PurchaseOrder.tenant_id == tenant.id).group_by(PurchaseOrder.status).all()
    by = {s: {"count": 0, "amount": 0.0} for s, _ in STATUSES}
    for status, n, amount in rows:
        by[status] = {"count": n, "amount": round(float(amount), 2)}
    debts = to_pay(tenant)
    return {"by": by, "total_amount": round(sum(v["amount"] for v in by.values()), 2),
            "open": sum(by[s]["count"] for s in ("rfq", "sent", "confirmed")),
            "to_pay": round(sum(d["balance"] for d in debts), 2),
            "overdue": round(sum(d["balance"] for d in debts if d["overdue"]), 2)}
