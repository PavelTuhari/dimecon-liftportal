"""Выгрузка документов: PDF по заявкам и рапортам, XLSX-реестры для кабинета, портала и клиента."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, Response, abort, g, request

from ..auth import is_staff, login_required, partner_required, staff_required
from ..db import SessionLocal as db, first_or_404
from ..models import (Contact, Document, Equipment, Membership, Order, Partner, Product, Service, Shift)
from ..services import documents as D
from ..services.pricing import pricing_of

bp = Blueprint("export", __name__)


def _file(data: bytes, filename: str, kind: str) -> Response:
    mime = ("application/pdf" if kind == "pdf"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return Response(data, mimetype=mime, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Content-Length": str(len(data)),
        "Cache-Control": "no-store",
    })


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _order_for_user(oid: int) -> Order:
    """Заявка, доступная текущему пользователю: сотруднику — любая своей компании,
    партнёру — своей компании-партнёра, клиенту — своя."""
    o = first_or_404(db.query(Order).filter_by(tenant_id=g.tenant.id, id=oid))
    if is_staff():
        return o
    m = g.membership
    if m and m.role == "partner" and m.partner_id and o.partner_id == m.partner_id:
        return o
    if o.contact and o.contact.user_id == g.user.id:
        return o
    abort(403)


# ------------------------------------------------------------------ PDF

@bp.route("/orders/<int:oid>/confirmation.pdf")
@login_required
def order_confirmation(tenant_slug, oid):
    o = _order_for_user(oid)
    return _file(D.order_confirmation_pdf(g.tenant, o), f"Подтверждение_{o.number}.pdf", "pdf")


@bp.route("/documents/<int:did>.pdf")
@login_required
def document_pdf(tenant_slug, did):
    doc = first_or_404(db.query(Document).filter_by(tenant_id=g.tenant.id, id=did))
    o = _order_for_user(doc.order_id) if doc.order_id else abort(404)
    shifts = db.query(Shift).filter_by(order_id=o.id).order_by(Shift.work_date).all()
    data = D.document_pdf(g.tenant, o, doc, shifts)
    name = f"{D.DOC_TITLES.get(doc.type, doc.type)}_{doc.number}.pdf".replace(" ", "_")
    return _file(data, name, "pdf")


@bp.route("/shifts/<int:sid>.pdf")
@login_required
def shift_pdf(tenant_slug, sid):
    s = first_or_404(db.query(Shift).filter_by(tenant_id=g.tenant.id, id=sid))
    o = _order_for_user(s.order_id)
    return _file(D.shift_report_pdf(g.tenant, s, o), f"Рапорт_{s.id}_{s.work_date:%Y-%m-%d}.pdf", "pdf")


# ------------------------------------------------------------------ XLSX: кабинет компании

def _filtered_orders():
    q = db.query(Order).filter_by(tenant_id=g.tenant.id)
    if request.args.get("kind"):
        q = q.filter(Order.kind == request.args["kind"])
    if request.args.get("stage"):
        q = q.filter(Order.stage == request.args["stage"])
    if request.args.get("from"):
        q = q.filter(Order.created_at >= datetime.fromisoformat(request.args["from"]))
    if request.args.get("to"):
        q = q.filter(Order.created_at <= datetime.fromisoformat(request.args["to"]))
    return q.order_by(Order.created_at.desc()).all()


@bp.route("/orders.xlsx")
@staff_required
def orders_xlsx(tenant_slug):
    rows = _filtered_orders()
    return _file(D.orders_xlsx(g.tenant, rows), f"Заявки_{g.tenant.slug}_{_stamp()}.xlsx", "xlsx")


@bp.route("/shifts.xlsx")
@staff_required
def shifts_xlsx(tenant_slug):
    rows = db.query(Shift).filter_by(tenant_id=g.tenant.id).order_by(Shift.work_date.desc()).all()
    orders = {o.id: o for o in db.query(Order).filter_by(tenant_id=g.tenant.id).all()}
    return _file(D.shifts_xlsx(g.tenant, rows, orders), f"Смены_{g.tenant.slug}_{_stamp()}.xlsx", "xlsx")


@bp.route("/documents.xlsx")
@staff_required
def documents_xlsx(tenant_slug):
    rows = db.query(Document).filter_by(tenant_id=g.tenant.id).order_by(Document.issued_at.desc()).all()
    orders = {o.id: o for o in db.query(Order).filter_by(tenant_id=g.tenant.id).all()}
    return _file(D.invoices_xlsx(g.tenant, rows, orders), f"Документы_{g.tenant.slug}_{_stamp()}.xlsx", "xlsx")


@bp.route("/fleet.xlsx")
@staff_required
def fleet_xlsx(tenant_slug):
    rows = db.query(Equipment).filter_by(tenant_id=g.tenant.id).order_by(Equipment.sort).all()
    return _file(D.fleet_xlsx(g.tenant, rows), f"Парк_{g.tenant.slug}_{_stamp()}.xlsx", "xlsx")


@bp.route("/contacts.xlsx")
@staff_required
def contacts_xlsx(tenant_slug):
    rows = db.query(Contact).filter_by(tenant_id=g.tenant.id).order_by(Contact.created_at.desc()).all()
    return _file(D.contacts_xlsx(g.tenant, rows), f"Контакты_{g.tenant.slug}_{_stamp()}.xlsx", "xlsx")


@bp.route("/pricelist.xlsx")
def pricelist_xlsx(tenant_slug):
    """Прайс-лист доступен и публично — это витрина компании."""
    tnt = g.tenant
    eq = db.query(Equipment).filter_by(tenant_id=tnt.id, is_published=True).order_by(Equipment.sort).all()
    sv = db.query(Service).filter_by(tenant_id=tnt.id, is_published=True).order_by(Service.sort).all()
    pr = db.query(Product).filter_by(tenant_id=tnt.id, is_published=True).all()
    return _file(D.pricelist_xlsx(tnt, eq, sv, pr, pricing_of(tnt)), f"Прайс_{tnt.slug}_{_stamp()}.xlsx", "xlsx")


# ------------------------------------------------------------------ XLSX: партнёр и клиент

@bp.route("/partner/orders.xlsx")
@partner_required
def partner_orders_xlsx(tenant_slug):
    pid = request.args.get("partner_id", type=int) if is_staff() else (g.membership.partner_id if g.membership else None)
    partner = db.get(Partner, pid) if pid else None
    if not partner or partner.tenant_id != g.tenant.id:
        abort(404)
    rows = db.query(Order).filter_by(tenant_id=g.tenant.id, partner_id=partner.id).order_by(Order.starts_at.desc()).all()
    return _file(D.orders_xlsx(g.tenant, rows, "Заявки партнёра"), f"Заявки_{partner.name}_{_stamp()}.xlsx", "xlsx")


@bp.route("/partner/shifts.xlsx")
@partner_required
def partner_shifts_xlsx(tenant_slug):
    pid = request.args.get("partner_id", type=int) if is_staff() else (g.membership.partner_id if g.membership else None)
    orders = {o.id: o for o in db.query(Order).filter_by(tenant_id=g.tenant.id, partner_id=pid).all()}
    rows = (db.query(Shift).filter(Shift.tenant_id == g.tenant.id, Shift.order_id.in_(orders.keys() or [0]))
            .order_by(Shift.work_date.desc()).all())
    return _file(D.shifts_xlsx(g.tenant, rows, orders), f"Табель_смен_{_stamp()}.xlsx", "xlsx")


@bp.route("/partner/documents.xlsx")
@partner_required
def partner_documents_xlsx(tenant_slug):
    pid = request.args.get("partner_id", type=int) if is_staff() else (g.membership.partner_id if g.membership else None)
    rows = db.query(Document).filter_by(tenant_id=g.tenant.id, partner_id=pid).order_by(Document.issued_at.desc()).all()
    orders = {o.id: o for o in db.query(Order).filter_by(tenant_id=g.tenant.id, partner_id=pid).all()}
    return _file(D.invoices_xlsx(g.tenant, rows, orders), f"Счета_партнёра_{_stamp()}.xlsx", "xlsx")


@bp.route("/account/orders.xlsx")
@login_required
def account_orders_xlsx(tenant_slug):
    cids = [c.id for c in db.query(Contact).filter_by(tenant_id=g.tenant.id, user_id=g.user.id).all()]
    rows = (db.query(Order).filter(Order.tenant_id == g.tenant.id, Order.contact_id.in_(cids or [0]))
            .order_by(Order.created_at.desc()).all())
    return _file(D.orders_xlsx(g.tenant, rows, "Мои заказы"), f"Мои_заказы_{_stamp()}.xlsx", "xlsx")
