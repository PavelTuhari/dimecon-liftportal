"""Создание заказов/лидов, контактов, документов, нумерация, уведомления."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import url_for
from sqlalchemy import func

from ..db import SessionLocal
from ..mailer import send_mail
from ..models import Activity, Booking, Contact, Document, Order, Tenant


def next_number(tenant: Tenant, prefix: str = "") -> str:
    prefix = prefix or tenant.slug[:3].upper()
    year = date.today().year
    n = (SessionLocal.query(func.count(Order.id))
         .filter(Order.tenant_id == tenant.id, Order.number.like(f"{prefix}-{year}-%")).scalar() or 0) + 1
    return f"{prefix}-{year}-{n:05d}"


def upsert_contact(tenant: Tenant, *, name: str, phone: str, email: str = "", kind="b2c",
                   user_id=None, partner_id=None, source="site", company="") -> Contact:
    phone_n = normalize_phone(phone)
    q = SessionLocal.query(Contact).filter_by(tenant_id=tenant.id)
    c = None
    if phone_n:
        c = q.filter_by(phone=phone_n).first()
    if not c and email:
        c = q.filter_by(email=email.lower()).first()
    if not c:
        c = Contact(tenant_id=tenant.id, name=name, phone=phone_n, email=email.lower(), kind=kind,
                    user_id=user_id, partner_id=partner_id, source=source, company=company)
        SessionLocal.add(c)
        SessionLocal.flush()
    else:
        if user_id and not c.user_id:
            c.user_id = user_id
        if name and not c.name:
            c.name = name
    return c


def normalize_phone(p: str) -> str:
    digits = "".join(ch for ch in (p or "") if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("0") and len(digits) == 9:
        digits = "373" + digits[1:]
    return "+" + digits


def create_order(tenant: Tenant, contact: Contact, **fields) -> Order:
    order = Order(tenant_id=tenant.id, contact_id=contact.id, number=next_number(tenant), **fields)
    SessionLocal.add(order)
    SessionLocal.flush()
    contact.orders_count = (contact.orders_count or 0) + 1
    SessionLocal.add(Activity(tenant_id=tenant.id, order_id=order.id, contact_id=contact.id, kind="status",
                              body=f"Заявка создана через {order.source}"))
    if order.equipment_id and order.starts_at:
        SessionLocal.add(Booking(tenant_id=tenant.id, equipment_id=order.equipment_id, starts_at=order.starts_at,
                                 ends_at=order.starts_at + timedelta(hours=order.hours or 4), reason="soft",
                                 order_id=order.id, note="мягкая бронь из визарда"))
    SessionLocal.commit()
    notify_new_order(tenant, order, contact)
    return order


def notify_new_order(tenant: Tenant, order: Order, contact: Contact):
    price = f"{order.price_min:,.0f}–{order.price_max:,.0f} {tenant.currency}".replace(",", " ") if order.price_max else "по запросу"
    if contact.email:
        send_mail(tenant, contact.email, f"[{tenant.name}] Заявка {order.number} принята",
                  f"Здравствуйте, {contact.name}!\n\nВаша заявка {order.number} принята.\n"
                  f"Техника: {order.equipment.brand + ' ' + order.equipment.model if order.equipment else 'подбирает инженер'}\n"
                  f"Дата: {order.starts_at:%d.%m.%Y %H:%M}\nОриентировочная стоимость: {price}\n\n"
                  f"Мы подтвердим заявку в течение 30 минут в рабочее время.\n{tenant.name} · {tenant.phone}")
    if tenant.email:
        send_mail(tenant, tenant.email, f"Новая заявка {order.number}",
                  f"{contact.name}, {contact.phone}\n{order.cargo} {order.weight_t} т, H={order.height_m} м, "
                  f"R={order.radius_m} м\n{order.address}\n{order.starts_at}\nЭскалация: {'да' if order.escalated else 'нет'}")


def set_status(order: Order, status: str, user_id=None, note=""):
    old = order.status
    order.status = status
    stage_map = {"quoted": "quoted", "confirmed": "won", "scheduled": "won", "completed": "won",
                 "paid": "won", "cancelled": "lost", "under_review": "contacted"}
    if status in stage_map:
        order.stage = stage_map[status]
    SessionLocal.add(Activity(tenant_id=order.tenant_id, order_id=order.id, user_id=user_id, kind="status",
                              body=f"Статус: {old} → {status}" + (f". {note}" if note else "")))
    if status in ("confirmed", "scheduled") and order.equipment_id and order.starts_at:
        for b in SessionLocal.query(Booking).filter_by(order_id=order.id).all():
            b.reason = "order"
    if status == "cancelled":
        SessionLocal.query(Booking).filter_by(order_id=order.id).delete()
    SessionLocal.commit()


def issue_document(tenant: Tenant, order: Order, doc_type: str, amount: float) -> Document:
    prefix = {"quote": "KP", "confirmation": "CF", "act": "ACT", "invoice": "INV"}[doc_type]
    n = SessionLocal.query(func.count(Document.id)).filter_by(tenant_id=tenant.id, type=doc_type).scalar() + 1
    doc = Document(tenant_id=tenant.id, order_id=order.id, partner_id=order.partner_id, type=doc_type,
                   number=f"{prefix}-{date.today().year}-{n:04d}", amount=amount,
                   due_at=date.today() + timedelta(days=7) if doc_type in ("quote", "invoice") else None,
                   payload={"lines": order.breakdown, "order": order.number})
    SessionLocal.add(doc)
    SessionLocal.commit()
    return doc
