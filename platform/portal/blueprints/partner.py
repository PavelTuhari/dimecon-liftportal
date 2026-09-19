"""Портал партнёра (B2B): проекты, заявки, график, смены, документы."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth import is_staff, login_required, partner_required
from ..db import SessionLocal as db, first_or_404
from ..models import Booking, Contact, Document, Equipment, Order, Partner, Project, Shift
from ..services.orders import create_order, upsert_contact
from ..services.pricing import calculate

bp = Blueprint("partner", __name__)


def _partner() -> Partner:
    if is_staff() and request.args.get("partner_id"):
        return db.get(Partner, request.args.get("partner_id", type=int))
    pid = g.membership.partner_id if g.membership else None
    return db.get(Partner, pid) if pid else None


@bp.route("/apply", methods=["GET", "POST"])
def apply(tenant_slug):
    if request.method == "POST":
        f = request.form
        p = Partner(tenant_id=g.tenant.id, name=f["company"], idno=f.get("idno", ""), contact_name=f["name"],
                    phone=f["phone"], email=f.get("email", ""), status="lead")
        db.add(p); db.flush()
        c = upsert_contact(g.tenant, name=f["name"], phone=f["phone"], email=f.get("email", ""), kind="b2b",
                           partner_id=p.id, source="partner_apply", company=f["company"])
        create_order(g.tenant, c, kind="b2b", source="partner_apply", task_type="construction", partner_id=p.id,
                     comment=f.get("about", ""), starts_at=datetime.utcnow() + timedelta(days=3), escalated=True,
                     escalation_reasons=["Заявка на подключение партнёра"])
        flash("Заявка отправлена. Менеджер подключит компанию в течение 1 рабочего дня.", "success")
        return redirect(url_for("site.partners_landing"))
    return render_template("partner/apply.html")


@bp.route("/")
@partner_required
def index(tenant_slug):
    p = _partner()
    if not p:
        return render_template("partner/no_partner.html")
    projects = db.query(Project).filter_by(partner_id=p.id).order_by(Project.created_at.desc()).all()
    orders = db.query(Order).filter_by(partner_id=p.id).order_by(Order.starts_at.desc()).limit(20).all()
    pending_shifts = db.query(Shift).join(Order).filter(Order.partner_id == p.id, Shift.status == "submitted").all()
    docs = db.query(Document).filter_by(partner_id=p.id).order_by(Document.issued_at.desc()).limit(10).all()
    month_spend = db.query(func.sum(Order.price_final)).filter(Order.partner_id == p.id,
                                                              Order.created_at >= datetime.utcnow().replace(day=1)).scalar() or 0
    tiers = [("base", 0), ("bronze", 100000), ("silver", 400000), ("gold", 1000000), ("platinum", 3000000)]
    nxt = next(((t, th) for t, th in tiers if th > (p.turnover or 0)), None)
    return render_template("partner/index.html", p=p, projects=projects, orders=orders, pending=pending_shifts, docs=docs,
                           month_spend=month_spend, next_tier=nxt)


@bp.route("/projects/new", methods=["POST"])
@partner_required
def project_new(tenant_slug):
    p = _partner()
    f = request.form
    pr = Project(tenant_id=g.tenant.id, partner_id=p.id, name=f["name"], address=f.get("address", ""),
                 starts_at=datetime.strptime(f["starts_at"], "%Y-%m-%d").date() if f.get("starts_at") else None)
    db.add(pr); db.commit()
    return redirect(url_for("partner.project", pid=pr.id))


@bp.route("/projects/<int:pid>")
@partner_required
def project(tenant_slug, pid):
    p = _partner()
    pr = first_or_404(db.query(Project).filter_by(id=pid, partner_id=p.id))
    orders = db.query(Order).filter_by(project_id=pr.id).order_by(Order.starts_at.desc()).all()
    shifts = db.query(Shift).filter_by(project_id=pr.id).order_by(Shift.work_date.desc()).all()
    fleet = db.query(Equipment).filter_by(tenant_id=g.tenant.id, is_published=True, status="active").all()
    templates = orders[:3]
    hours = sum(s.hours_worked for s in shifts if s.status == "approved")
    return render_template("partner/project.html", p=p, pr=pr, orders=orders, shifts=shifts, fleet=fleet,
                           templates=templates, hours=hours, view=request.args.get("view", "list"))


@bp.route("/projects/<int:pid>/request", methods=["POST"])
@partner_required
def request_new(tenant_slug, pid):
    p = _partner()
    pr = first_or_404(db.query(Project).filter_by(id=pid, partner_id=p.id))
    f = request.form
    eq = db.get(Equipment, f.get("equipment_id", type=int)) if f.get("equipment_id") else None
    start = datetime.strptime(f["start"], "%Y-%m-%dT%H:%M")
    hours = f.get("hours", 8, type=float)
    repeat = f.get("repeat_weeks", 0, type=int)
    contact = upsert_contact(g.tenant, name=g.user.full_name, phone=g.user.phone, email=g.user.email, kind="b2b",
                             partner_id=p.id, user_id=g.user.id, company=p.name, source="portal")
    for i in range(max(1, repeat)):
        st = start + timedelta(weeks=i)
        price = calculate(g.tenant, eq, start=st, hours=hours, distance_km=f.get("distance", 10, type=float),
                          conditions=f.getlist("cond"), partner_discount=(p.discount_pct or 0) / 100) if eq else None
        create_order(g.tenant, contact, kind="b2b", source="portal", partner_id=p.id, project_id=pr.id,
                     equipment_id=eq.id if eq else None, task_type=f.get("task", "construction"), cargo=f.get("cargo", ""),
                     weight_t=f.get("weight", 0, type=float), address=pr.address, starts_at=st, hours=hours,
                     conditions=f.getlist("cond"), price_min=price["total"] if price else 0,
                     price_max=price["total"] if price else 0, breakdown=price["lines"] if price else [],
                     comment=f.get("comment", ""), stage="contacted", status="under_review")
    flash(f"Создано заявок: {max(1, repeat)}", "success")
    return redirect(url_for("partner.project", pid=pr.id))


@bp.route("/shifts/<int:sid>/<action>", methods=["POST"])
@partner_required
def shift_action(tenant_slug, sid, action):
    p = _partner()
    s = first_or_404(db.query(Shift).join(Order).filter(Shift.id == sid, Order.partner_id == p.id))
    if action == "approve":
        s.status = "approved"
    elif action == "dispute":
        s.status = "disputed"; s.dispute_reason = request.form.get("reason", "")
    db.commit()
    flash("Рапорт обновлён", "success")
    return redirect(request.referrer or url_for("partner.index"))


@bp.route("/schedule")
@partner_required
def schedule(tenant_slug):
    p = _partner()
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    days = [start + timedelta(days=i) for i in range(14)]
    my_orders = {o.id: o for o in db.query(Order).filter_by(partner_id=p.id).all()}
    bookings = db.query(Booking).filter(Booking.tenant_id == g.tenant.id, Booking.ends_at >= start,
                                        Booking.starts_at <= start + timedelta(days=14)).all()
    fleet = db.query(Equipment).filter_by(tenant_id=g.tenant.id, is_published=True).all()
    grid = {}
    for b in bookings:
        for d in days:
            if b.starts_at < d + timedelta(days=1) and b.ends_at > d:
                key = (b.equipment_id, d.date())
                mine = b.order_id in my_orders
                grid[key] = "mine" if mine else ("busy" if grid.get(key) != "mine" else "mine")
    return render_template("partner/schedule.html", p=p, days=days, fleet=fleet, grid=grid)


@bp.route("/documents")
@partner_required
def documents(tenant_slug):
    p = _partner()
    docs = db.query(Document).filter_by(partner_id=p.id).order_by(Document.issued_at.desc()).all()
    return render_template("partner/documents.html", p=p, docs=docs)
