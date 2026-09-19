"""Кабинет компании: дашборд, CRM, заказы, парк, контент, настройки white-label."""
from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth import hash_password, owner_required, staff_required
from ..db import SessionLocal as db, first_or_404
from ..mailer import send_mail, test_smtp
from ..models import (LEAD_STAGES, ORDER_STATUSES, Activity, AuditLog, Booking, CaseStudy, Contact, Document, Domain,
                      Equipment, EquipmentCategory, Invite, LoadChart, Media, Membership, Order, Outbox, Page, Partner,
                      Product, Project, Review, Service, Shift, User)
from ..services.orders import issue_document, set_status
from ..services.pricing import DEFAULT_PRICING, pricing_of
from ..storage import add_by_url, delete_media, save_upload, test_storage

bp = Blueprint("admin", __name__)


def T():
    return g.tenant


def i18n_from_form(f, field):
    return {l: f.get(f"{field}_{l}", "").strip() for l in ("ru", "ro", "en")}


def log(action, entity="", entity_id=None, **details):
    db.add(AuditLog(tenant_id=T().id, user_id=g.user.id, action=action, entity=entity, entity_id=entity_id, details=details))


# ------------------------------------------------------------------ Дашборд

@bp.route("/")
@staff_required
def dashboard(tenant_slug):
    tid = T().id
    now = datetime.utcnow()
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    q = db.query(Order).filter_by(tenant_id=tid)
    kpi = {
        "new": q.filter(Order.stage == "new").count(),
        "today": q.filter(Order.starts_at >= now.replace(hour=0, minute=0), Order.starts_at < now.replace(hour=0, minute=0) + timedelta(days=1),
                          Order.status.in_(("confirmed", "scheduled", "in_progress"))).count(),
        "month_orders": q.filter(Order.created_at >= month).count(),
        "month_revenue": db.query(func.sum(Order.price_final)).filter(Order.tenant_id == tid, Order.created_at >= month,
                                                                      Order.status.in_(("completed", "invoiced", "paid"))).scalar() or 0,
        "escalated": q.filter(Order.escalated == True, Order.stage.in_(("new", "contacted"))).count(),  # noqa: E712
        "contacts": db.query(func.count(Contact.id)).filter_by(tenant_id=tid).scalar(),
        "fleet": db.query(func.count(Equipment.id)).filter_by(tenant_id=tid).scalar(),
        "partners": db.query(func.count(Partner.id)).filter_by(tenant_id=tid, status="active").scalar(),
        "pending_shifts": db.query(func.count(Shift.id)).filter_by(tenant_id=tid, status="submitted").scalar(),
        "mail_issues": db.query(func.count(Outbox.id)).filter(Outbox.tenant_id == tid, Outbox.status != "sent").scalar(),
    }
    funnel = {s: q.filter(Order.stage == s).count() for s in LEAD_STAGES}
    recent = q.order_by(Order.created_at.desc()).limit(8).all()
    upcoming = q.filter(Order.starts_at >= now, Order.status.in_(("confirmed", "scheduled"))).order_by(Order.starts_at).limit(8).all()
    return render_template("admin/dashboard.html", kpi=kpi, funnel=funnel, recent=recent, upcoming=upcoming)


# ------------------------------------------------------------------ CRM: заказы/лиды

@bp.route("/orders")
@staff_required
def orders(tenant_slug):
    view = request.args.get("view", "kanban")
    q = db.query(Order).filter_by(tenant_id=T().id)
    kind = request.args.get("kind")
    if kind:
        q = q.filter(Order.kind == kind)
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.join(Contact, isouter=True).filter((Order.number.ilike(like)) | (Contact.name.ilike(like)) | (Contact.phone.ilike(like)) | (Order.address.ilike(like)))
    rows = q.order_by(Order.created_at.desc()).limit(500).all()
    by_stage = {s: [o for o in rows if o.stage == s] for s in LEAD_STAGES}
    return render_template("admin/orders.html", rows=rows, by_stage=by_stage, stages=LEAD_STAGES, view=view, kind=kind)


@bp.route("/orders/<int:oid>", methods=["GET", "POST"])
@staff_required
def order(tenant_slug, oid):
    o = first_or_404(db.query(Order).filter_by(tenant_id=T().id, id=oid))
    if request.method == "POST":
        f = request.form
        act = f.get("action")
        if act == "status":
            set_status(o, f["status"], g.user.id, f.get("note", ""))
        elif act == "stage":
            o.stage = f["stage"]; db.commit()
        elif act == "note":
            db.add(Activity(tenant_id=T().id, order_id=o.id, contact_id=o.contact_id, user_id=g.user.id, kind=f.get("kind", "note"), body=f["body"]))
            db.commit()
        elif act == "assign":
            o.equipment_id = f.get("equipment_id", type=int) or None
            o.assignee_id = f.get("assignee_id", type=int) or None
            o.price_final = f.get("price_final", type=float) or o.price_final
            if f.get("starts_at"):
                o.starts_at = datetime.strptime(f["starts_at"], "%Y-%m-%dT%H:%M")
            o.hours = f.get("hours", type=float) or o.hours
            o.internal_note = f.get("internal_note", o.internal_note)
            db.query(Booking).filter_by(order_id=o.id).delete()
            if o.equipment_id and o.starts_at:
                db.add(Booking(tenant_id=T().id, equipment_id=o.equipment_id, starts_at=o.starts_at,
                               ends_at=o.starts_at + timedelta(hours=o.hours or 4),
                               reason="order" if o.status in ("confirmed", "scheduled", "in_progress") else "soft", order_id=o.id))
            db.commit()
        elif act == "document":
            doc = issue_document(T(), o, f["doc_type"], f.get("amount", type=float) or o.price_final or o.price_max)
            if o.contact and o.contact.email and f.get("send") == "1":
                send_mail(T(), o.contact.email, f"[{T().name}] {doc.type.upper()} {doc.number} по заявке {o.number}",
                          f"Документ {doc.number} на сумму {doc.amount:,.0f} {T().currency}.\n\n{T().name} · {T().phone}")
            if f["doc_type"] == "quote":
                set_status(o, "quoted", g.user.id, f"КП {doc.number}")
        elif act == "shift":
            db.add(Shift(tenant_id=T().id, order_id=o.id, project_id=o.project_id, equipment_id=o.equipment_id,
                         work_date=datetime.strptime(f["work_date"], "%Y-%m-%d").date(), operator=f.get("operator", ""),
                         hours_worked=f.get("hours_worked", 0, type=float), hours_idle=f.get("hours_idle", 0, type=float),
                         idle_fault=f.get("idle_fault", ""), lifts=f.get("lifts", 0, type=int), notes=f.get("notes", "")))
            db.commit()
        flash("Сохранено", "success")
        return redirect(url_for("admin.order", oid=oid))
    fleet = db.query(Equipment).filter_by(tenant_id=T().id).order_by(Equipment.capacity_t.desc()).all()
    staff = [m.user for m in db.query(Membership).filter(Membership.tenant_id == T().id, Membership.role.in_(Membership.STAFF_ROLES)).all()]
    docs = db.query(Document).filter_by(order_id=o.id).all()
    shifts = db.query(Shift).filter_by(order_id=o.id).order_by(Shift.work_date.desc()).all()
    return render_template("admin/order.html", o=o, fleet=fleet, staff=staff, docs=docs, shifts=shifts, statuses=ORDER_STATUSES, stages=LEAD_STAGES)


@bp.route("/orders/<int:oid>/stage", methods=["POST"])
@staff_required
def order_stage(tenant_slug, oid):
    """HTMX/JS: перетаскивание карточки в канбане."""
    o = first_or_404(db.query(Order).filter_by(tenant_id=T().id, id=oid))
    stage = request.form.get("stage") or (request.get_json(silent=True) or {}).get("stage")
    if stage in LEAD_STAGES:
        o.stage = stage
        db.add(Activity(tenant_id=T().id, order_id=o.id, user_id=g.user.id, kind="status", body=f"Этап → {stage}"))
        db.commit()
    return {"ok": True, "stage": o.stage}


@bp.route("/contacts")
@staff_required
def contacts(tenant_slug):
    q = db.query(Contact).filter_by(tenant_id=T().id)
    if request.args.get("q"):
        like = f"%{request.args['q']}%"
        q = q.filter((Contact.name.ilike(like)) | (Contact.phone.ilike(like)) | (Contact.email.ilike(like)) | (Contact.company.ilike(like)))
    kind = request.args.get("kind")
    if kind:
        q = q.filter_by(kind=kind)
    return render_template("admin/contacts.html", rows=q.order_by(Contact.created_at.desc()).limit(500).all(), kind=kind)


@bp.route("/contacts/<int:cid>", methods=["GET", "POST"])
@staff_required
def contact(tenant_slug, cid):
    c = first_or_404(db.query(Contact).filter_by(tenant_id=T().id, id=cid))
    if request.method == "POST":
        f = request.form
        c.name, c.company, c.phone, c.email, c.tags, c.notes = f["name"], f.get("company", ""), f["phone"], f.get("email", ""), f.get("tags", ""), f.get("notes", "")
        c.kind = f.get("kind", c.kind)
        db.commit(); flash("Сохранено", "success")
    orders = db.query(Order).filter_by(contact_id=c.id).order_by(Order.created_at.desc()).all()
    acts = db.query(Activity).filter_by(contact_id=c.id).order_by(Activity.created_at.desc()).limit(50).all()
    return render_template("admin/contact.html", c=c, orders=orders, acts=acts)


@bp.route("/tasks")
@staff_required
def tasks(tenant_slug):
    rows = db.query(Activity).filter(Activity.tenant_id == T().id, Activity.kind == "task", Activity.done == False).order_by(Activity.due_at).all()  # noqa: E712
    return render_template("admin/tasks.html", rows=rows)


@bp.route("/tasks/<int:aid>/done", methods=["POST"])
@staff_required
def task_done(tenant_slug, aid):
    a = first_or_404(db.query(Activity).filter_by(tenant_id=T().id, id=aid))
    a.done = True; db.commit()
    return redirect(request.referrer or url_for("admin.tasks"))


# ------------------------------------------------------------------ Парк техники

@bp.route("/fleet")
@staff_required
def fleet(tenant_slug):
    rows = db.query(Equipment).filter_by(tenant_id=T().id).order_by(Equipment.sort, Equipment.capacity_t.desc()).all()
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    days = [start + timedelta(days=i) for i in range(14)]
    bookings = db.query(Booking).filter(Booking.tenant_id == T().id, Booking.ends_at >= start, Booking.starts_at <= start + timedelta(days=14)).all()
    grid = {}
    for b in bookings:
        for d in days:
            if b.starts_at < d + timedelta(days=1) and b.ends_at > d:
                grid[(b.equipment_id, d.date())] = b.reason
    return render_template("admin/fleet.html", rows=rows, days=days, grid=grid)


@bp.route("/fleet/new", methods=["GET", "POST"])
@bp.route("/fleet/<int:eid>", methods=["GET", "POST"])
@staff_required
def equipment(tenant_slug, eid=None):
    eq = first_or_404(db.query(Equipment).filter_by(tenant_id=T().id, id=eid)) if eid else None
    cats = db.query(EquipmentCategory).filter_by(tenant_id=T().id).order_by(EquipmentCategory.sort).all()
    if request.method == "POST":
        f = request.form
        if f.get("action") == "delete" and eq:
            db.delete(eq); db.commit(); flash("Удалено", "success")
            return redirect(url_for("admin.fleet"))
        if not eq:
            eq = Equipment(tenant_id=T().id); db.add(eq)
        eq.brand, eq.model = f["brand"], f["model"]
        eq.slug = f.get("slug") or f"{f['brand']}-{f['model']}".lower().replace(" ", "-")
        eq.inventory_no = f.get("inventory_no", ""); eq.year = f.get("year", type=int)
        eq.category_id = f.get("category_id", type=int) or None
        eq.status = f.get("status", "active"); eq.is_published = f.get("is_published") == "1"
        eq.title = i18n_from_form(f, "title"); eq.description = i18n_from_form(f, "description")
        for k in ("capacity_t", "radius_m", "height_m", "outrigger_half_m", "payload_kg", "platform_l_mm", "platform_w_mm",
                  "hourly_rate", "min_hours", "mobilization_fee", "per_km_rate"):
            setattr(eq, k, f.get(k, 0, type=float) or 0)
        eq.photo_url = f.get("photo_url", ""); eq.sort = f.get("sort", 0, type=int)
        if f.get("action") == "chart_add":
            db.flush()
            db.add(LoadChart(equipment_id=eq.id, configuration=f.get("cfg", "main"), outriggers=f.get("outriggers", "full"),
                             radius_m=f.get("c_radius", type=float), capacity_t=f.get("c_capacity", type=float), height_m=f.get("c_height", 0, type=float) or 0))
        if f.get("action") == "chart_csv":
            db.flush()
            for line in f.get("csv", "").splitlines():
                parts = [x.strip() for x in line.replace(";", ",").split(",")]
                if len(parts) >= 2 and parts[0].replace(".", "", 1).isdigit():
                    db.add(LoadChart(equipment_id=eq.id, configuration=f.get("cfg", "main"), radius_m=float(parts[0]),
                                     capacity_t=float(parts[1]), height_m=float(parts[2]) if len(parts) > 2 and parts[2] else 0))
        if f.get("action") == "booking":
            db.flush()
            st = datetime.strptime(f["b_start"], "%Y-%m-%dT%H:%M"); en = datetime.strptime(f["b_end"], "%Y-%m-%dT%H:%M")
            db.add(Booking(tenant_id=T().id, equipment_id=eq.id, starts_at=st, ends_at=en, reason=f.get("b_reason", "maintenance"), note=f.get("b_note", "")))
        db.commit()
        flash("Сохранено", "success")
        return redirect(url_for("admin.equipment", eid=eq.id))
    charts = eq.load_charts if eq else []
    bookings = db.query(Booking).filter_by(equipment_id=eq.id).order_by(Booking.starts_at.desc()).limit(20).all() if eq else []
    media = db.query(Media).filter_by(tenant_id=T().id).order_by(Media.created_at.desc()).limit(40).all()
    return render_template("admin/equipment.html", eq=eq, cats=cats, charts=charts, bookings=bookings, media=media)


@bp.route("/fleet/chart/<int:cid>/delete", methods=["POST"])
@staff_required
def chart_delete(tenant_slug, cid):
    c = db.get(LoadChart, cid)
    if c and c.equipment_id and db.get(Equipment, c.equipment_id).tenant_id == T().id:
        eid = c.equipment_id; db.delete(c); db.commit()
        return redirect(url_for("admin.equipment", eid=eid))
    abort(404)


@bp.route("/fleet/booking/<int:bid>/delete", methods=["POST"])
@staff_required
def booking_delete(tenant_slug, bid):
    b = first_or_404(db.query(Booking).filter_by(tenant_id=T().id, id=bid))
    eid = b.equipment_id; db.delete(b); db.commit()
    return redirect(url_for("admin.equipment", eid=eid))


# ------------------------------------------------------------------ Контент: услуги, товары, кейсы, страницы

CONTENT = {
    "services": (Service, ["title", "short", "body"], ["slug", "code", "icon", "pricing_model", "image_url"], ["price_from", "sort"], ["is_orderable", "is_published"]),
    "products": (Product, ["title", "description"], ["slug", "sku", "category", "unit", "image_url"], ["price", "stock"], ["made_to_order", "is_published"]),
    "cases": (CaseStudy, ["title", "body"], ["slug", "client_name", "location", "image_url"], ["year"], ["is_published"]),
    "pages": (Page, ["title", "body"], ["slug"], [], ["in_menu", "is_published"]),
}


@bp.route("/content/<kind>")
@staff_required
def content_list(tenant_slug, kind):
    if kind not in CONTENT:
        abort(404)
    model = CONTENT[kind][0]
    rows = db.query(model).filter_by(tenant_id=T().id).all()
    return render_template("admin/content_list.html", kind=kind, rows=rows)


@bp.route("/content/<kind>/new", methods=["GET", "POST"])
@bp.route("/content/<kind>/<int:iid>", methods=["GET", "POST"])
@staff_required
def content_edit(tenant_slug, kind, iid=None):
    if kind not in CONTENT:
        abort(404)
    model, i18n_fields, str_fields, num_fields, bool_fields = CONTENT[kind]
    obj = first_or_404(db.query(model).filter_by(tenant_id=T().id, id=iid)) if iid else None
    if request.method == "POST":
        f = request.form
        if f.get("action") == "delete" and obj:
            db.delete(obj); db.commit()
            return redirect(url_for("admin.content_list", kind=kind))
        if not obj:
            obj = model(tenant_id=T().id); db.add(obj)
        for fld in i18n_fields:
            setattr(obj, fld, i18n_from_form(f, fld))
        for fld in str_fields:
            setattr(obj, fld, f.get(fld, "").strip())
        for fld in num_fields:
            v = f.get(fld, type=float)
            setattr(obj, fld, int(v) if fld in ("year", "sort") and v is not None else (v or 0))
        for fld in bool_fields:
            setattr(obj, fld, f.get(fld) == "1")
        if kind == "cases":
            obj.metrics = {"weight_t": f.get("m_weight", 0, type=float), "height_m": f.get("m_height", 0, type=float), "hours": f.get("m_hours", 0, type=float)}
        if kind == "products":
            try:
                obj.attributes = json.loads(f.get("attributes_json") or "{}")
            except ValueError:
                flash("Атрибуты: некорректный JSON", "danger")
        if not obj.slug:
            obj.slug = f"{kind}-{secrets.token_hex(3)}"
        db.commit(); flash("Сохранено", "success")
        return redirect(url_for("admin.content_edit", kind=kind, iid=obj.id))
    media = db.query(Media).filter_by(tenant_id=T().id).order_by(Media.created_at.desc()).limit(40).all()
    return render_template("admin/content_edit.html", kind=kind, obj=obj, i18n_fields=i18n_fields, str_fields=str_fields,
                           num_fields=num_fields, bool_fields=bool_fields, media=media)


@bp.route("/reviews", methods=["GET", "POST"])
@staff_required
def reviews(tenant_slug):
    if request.method == "POST":
        r = first_or_404(db.query(Review).filter_by(tenant_id=T().id, id=request.form.get("id", type=int)))
        r.is_published = request.form.get("is_published") == "1"; r.reply = request.form.get("reply", "")
        db.commit()
    rows = db.query(Review).filter_by(tenant_id=T().id).order_by(Review.created_at.desc()).all()
    return render_template("admin/reviews.html", rows=rows)


# ------------------------------------------------------------------ Медиа

@bp.route("/media", methods=["GET", "POST"])
@staff_required
def media(tenant_slug):
    if request.method == "POST":
        try:
            if request.files.get("file") and request.files["file"].filename:
                m = save_upload(T(), request.files["file"])
            elif request.form.get("url"):
                m = add_by_url(T(), request.form["url"].strip(), request.form.get("filename", ""))
            else:
                raise ValueError("Выберите файл или укажите URL")
            m.tags = request.form.get("tags", "")
            db.add(m); db.commit(); flash("Файл добавлен", "success")
        except Exception as exc:  # noqa: BLE001
            flash(f"Ошибка: {exc}", "danger")
        return redirect(url_for("admin.media"))
    rows = db.query(Media).filter_by(tenant_id=T().id).order_by(Media.created_at.desc()).all()
    ok, msg = test_storage(T())
    return render_template("admin/media.html", rows=rows, storage_ok=ok, storage_msg=msg)


@bp.route("/media/<int:mid>/delete", methods=["POST"])
@staff_required
def media_delete(tenant_slug, mid):
    m = first_or_404(db.query(Media).filter_by(tenant_id=T().id, id=mid))
    delete_media(T(), m); db.delete(m); db.commit()
    return redirect(url_for("admin.media"))


# ------------------------------------------------------------------ Партнёры и смены

@bp.route("/partners", methods=["GET", "POST"])
@staff_required
def partners(tenant_slug):
    if request.method == "POST":
        f = request.form
        p = db.get(Partner, f.get("id", type=int)) if f.get("id") else Partner(tenant_id=T().id, name=f["name"])
        if p.tenant_id != T().id:
            abort(404)
        if not f.get("id"):
            db.add(p)
        p.name = f["name"]; p.idno = f.get("idno", ""); p.contact_name = f.get("contact_name", ""); p.phone = f.get("phone", "")
        p.email = f.get("email", ""); p.tier = f.get("tier", "base"); p.discount_pct = f.get("discount_pct", 0, type=float)
        p.credit_limit = f.get("credit_limit", 0, type=float); p.payment_days = f.get("payment_days", 0, type=int); p.status = f.get("status", "active")
        db.flush()
        if f.get("invite_email"):
            inv = Invite(tenant_id=T().id, email=f["invite_email"].strip().lower(), role="partner", partner_id=p.id)
            db.add(inv)
            link = url_for("admin.accept_invite", token=inv.token, _external=True)
            send_mail(T(), inv.email, f"[{T().name}] Доступ к порталу партнёра", f"Вас пригласили в портал партнёра {T().name}.\nАктивация: {link}")
            flash(f"Приглашение отправлено: {link}", "success")
        db.commit(); flash("Партнёр сохранён", "success")
        return redirect(url_for("admin.partners"))
    rows = db.query(Partner).filter_by(tenant_id=T().id).order_by(Partner.created_at.desc()).all()
    return render_template("admin/partners.html", rows=rows)


@bp.route("/shifts")
@staff_required
def shifts(tenant_slug):
    rows = db.query(Shift).filter_by(tenant_id=T().id).order_by(Shift.work_date.desc()).limit(300).all()
    return render_template("admin/shifts.html", rows=rows)


# ------------------------------------------------------------------ Настройки white-label

@bp.route("/settings/branding", methods=["GET", "POST"])
@owner_required
def branding(tenant_slug):
    tnt = T()
    if request.method == "POST":
        f = request.form
        tnt.name = f["name"]; tnt.legal_name = f.get("legal_name", ""); tnt.city = f.get("city", ""); tnt.address = f.get("address", "")
        tnt.phone = f.get("phone", ""); tnt.phone2 = f.get("phone2", ""); tnt.email = f.get("email", ""); tnt.website = f.get("website", "")
        tnt.idno = f.get("idno", ""); tnt.founded_year = f.get("founded_year", type=int)
        tnt.tagline = i18n_from_form(f, "tagline"); tnt.about = i18n_from_form(f, "about")
        tnt.default_locale = f.get("default_locale", "ru"); tnt.locales = f.getlist("locales") or ["ru"]
        tnt.currency = f.get("currency", "MDL"); tnt.vat_rate = f.get("vat_rate", 20, type=float)
        tnt.is_listed = f.get("is_listed") == "1"; tnt.profile = f.get("profile", "cranes")
        tnt.theme = {"accent": f.get("accent", "#F5A623"), "navy": f.get("navy", "#1F3A52"), "logo_url": f.get("logo_url", ""),
                     "hero_image_url": f.get("hero_image_url", ""), "dark": f.get("dark") == "1", "font": f.get("font", "Manrope")}
        tnt.hero = {"title": i18n_from_form(f, "hero_title"), "subtitle": i18n_from_form(f, "hero_subtitle"),
                    "badge": i18n_from_form(f, "hero_badge")}
        faq = []
        for i in range(1, 9):
            q = i18n_from_form(f, f"faq{i}_q"); a = i18n_from_form(f, f"faq{i}_a")
            if q["ru"] or q["ro"] or q["en"]:
                faq.append({"q": q, "a": a})
        tnt.faq = faq
        tnt.social = {k: f.get(f"social_{k}", "") for k in ("facebook", "instagram", "telegram", "whatsapp", "viber")}
        log("tenant.branding"); db.commit(); flash("Сохранено", "success")
    media = db.query(Media).filter_by(tenant_id=tnt.id).order_by(Media.created_at.desc()).limit(40).all()
    return render_template("admin/branding.html", media=media)


@bp.route("/settings/mail", methods=["GET", "POST"])
@owner_required
def mail_settings(tenant_slug):
    tnt = T()
    if request.method == "POST":
        f = request.form
        if f.get("action") == "test":
            ok, msg = test_smtp(tnt, f.get("test_to") or g.user.email)
            flash(msg, "success" if ok else "danger")
        else:
            tnt.smtp = {"host": f.get("host", "").strip(), "port": f.get("port", "587"), "user": f.get("user", ""),
                        "password": f.get("password") or (tnt.smtp or {}).get("password", ""), "tls": f.get("tls", "1"),
                        "ssl": f.get("ssl", "0"), "from_email": f.get("from_email", ""), "from_name": f.get("from_name", tnt.name)}
            log("tenant.smtp"); db.commit(); flash("Настройки почты сохранены", "success")
        return redirect(url_for("admin.mail_settings"))
    outbox = db.query(Outbox).filter_by(tenant_id=tnt.id).order_by(Outbox.created_at.desc()).limit(50).all()
    return render_template("admin/mail.html", outbox=outbox)


@bp.route("/settings/storage", methods=["GET", "POST"])
@owner_required
def storage_settings(tenant_slug):
    tnt = T()
    if request.method == "POST":
        f = request.form
        tnt.storage = {"backend": f.get("backend", "local"), "endpoint": f.get("endpoint", ""), "bucket": f.get("bucket", ""),
                       "region": f.get("region", ""), "access_key": f.get("access_key", ""),
                       "secret_key": f.get("secret_key") or (tnt.storage or {}).get("secret_key", ""),
                       "prefix": f.get("prefix", ""), "public_base_url": f.get("public_base_url", "")}
        log("tenant.storage"); db.commit()
        ok, msg = test_storage(tnt)
        flash(f"Сохранено. {msg}", "success" if ok else "warning")
        return redirect(url_for("admin.storage_settings"))
    ok, msg = test_storage(tnt)
    return render_template("admin/storage.html", ok=ok, msg=msg)


@bp.route("/settings/pricing", methods=["GET", "POST"])
@owner_required
def pricing_settings(tenant_slug):
    tnt = T()
    if request.method == "POST":
        try:
            tnt.pricing = json.loads(request.form["pricing_json"])
            log("tenant.pricing"); db.commit(); flash("Тарифы сохранены", "success")
        except ValueError as exc:
            flash(f"Некорректный JSON: {exc}", "danger")
        return redirect(url_for("admin.pricing_settings"))
    return render_template("admin/pricing.html", pricing=pricing_of(tnt), defaults=DEFAULT_PRICING)


@bp.route("/settings/team", methods=["GET", "POST"])
@owner_required
def team(tenant_slug):
    tnt = T()
    if request.method == "POST":
        f = request.form
        if f.get("action") == "invite":
            inv = Invite(tenant_id=tnt.id, email=f["email"].strip().lower(), role=f.get("role", "staff"))
            db.add(inv); db.commit()
            link = url_for("admin.accept_invite", token=inv.token, _external=True)
            send_mail(tnt, inv.email, f"[{tnt.name}] Приглашение в кабинет", f"Вас пригласили в команду {tnt.name} с ролью {inv.role}.\nСсылка: {link}")
            flash(f"Приглашение создано. Ссылка: {link}", "success")
        elif f.get("action") == "role":
            m = first_or_404(db.query(Membership).filter_by(tenant_id=tnt.id, id=f.get("mid", type=int)))
            if m.role == "owner" and f["role"] != "owner" and db.query(Membership).filter_by(tenant_id=tnt.id, role="owner").count() == 1:
                flash("Нельзя понизить единственного владельца", "danger")
            else:
                m.role = f["role"]; db.commit(); flash("Роль обновлена", "success")
        elif f.get("action") == "remove":
            m = first_or_404(db.query(Membership).filter_by(tenant_id=tnt.id, id=f.get("mid", type=int)))
            if m.role != "owner":
                db.delete(m); db.commit()
        elif f.get("action") == "domain":
            host = f.get("host", "").strip().lower()
            if host:
                db.add(Domain(tenant_id=tnt.id, host=host, is_primary=True)); tnt.custom_domain = host; db.commit()
                flash(f"Домен {host} добавлен. Направьте A/CNAME-запись на сервер платформы.", "success")
        elif f.get("action") == "apikey":
            s = dict(tnt.settings or {}); s["api_key"] = secrets.token_urlsafe(32); tnt.settings = s; db.commit()
            flash("Новый API-ключ выпущен", "success")
        return redirect(url_for("admin.team"))
    members = db.query(Membership).filter(Membership.tenant_id == tnt.id, Membership.role != "customer").all()
    invites = db.query(Invite).filter_by(tenant_id=tnt.id, used_at=None).all()
    domains = db.query(Domain).filter_by(tenant_id=tnt.id).all()
    return render_template("admin/team.html", members=members, invites=invites, domains=domains)


@bp.route("/invite/<token>", methods=["GET", "POST"])
def accept_invite(tenant_slug, token):
    inv = first_or_404(db.query(Invite).filter_by(tenant_id=T().id, token=token, used_at=None))
    if request.method == "POST":
        f = request.form
        u = db.query(User).filter_by(email=inv.email).first()
        if not u:
            if len(f.get("password", "")) < 6:
                flash("Пароль не короче 6 символов", "danger")
                return render_template("admin/accept_invite.html", inv=inv)
            u = User(email=inv.email, full_name=f.get("name", ""), phone=f.get("phone", ""), password_hash=hash_password(f["password"]))
            db.add(u); db.flush()
        m = db.query(Membership).filter_by(tenant_id=T().id, user_id=u.id).first()
        if not m:
            m = Membership(tenant_id=T().id, user_id=u.id); db.add(m)
        m.role = inv.role; m.partner_id = inv.partner_id
        inv.used_at = datetime.utcnow()
        if inv.partner_id:
            p = db.get(Partner, inv.partner_id)
            if p and p.status == "lead":
                p.status = "active"
        db.commit()
        from ..auth import login_user
        login_user(u)
        return redirect(url_for("partner.index") if inv.role == "partner" else url_for("admin.dashboard"))
    return render_template("admin/accept_invite.html", inv=inv)


@bp.route("/integrations", methods=["GET", "POST"])
@owner_required
def integrations(tenant_slug):
    """Интеграция с внешней CRM: импорт контактов и истории из CSV/XLSX, ключи для обмена."""
    from ..services import crm_import as ci

    tnt = T()
    result = session_preview = None
    if request.method == "POST":
        f = request.form
        try:
            up = request.files.get("file")
            if not up or not up.filename:
                raise ValueError("Выберите файл выгрузки CRM (CSV или XLSX)")
            data = up.read()
            headers, rows = ci.read_table(data, up.filename)
            if not headers:
                raise ValueError("Файл пуст или не распознан")
            mapping = {}
            for idx in range(len(headers)):
                chosen = f.get(f"col{idx}")
                if chosen:
                    mapping[idx] = chosen
            if not mapping:
                mapping = ci.detect_mapping(headers)
            dry = f.get("action") != "import"
            rep = ci.import_contacts(tnt, headers, rows, mapping, dry_run=dry,
                                     source_label=f.get("source_label") or "crm-import",
                                     create_orders=f.get("create_orders") == "1",
                                     partner_id=f.get("partner_id", type=int) or None)
            session_preview = {"headers": headers, "mapping": mapping, "rows": ci.preview(headers, rows, mapping),
                               "count": len(rows), "filename": up.filename}
            result = rep
            if not dry:
                log("crm.import", details={"file": up.filename, "created": rep.created, "updated": rep.updated})
                db.commit()
                flash(rep.line(), "success" if rep.ok else "warning")
        except Exception as exc:  # noqa: BLE001
            flash(f"Импорт не выполнен: {exc}", "danger")

    partners = db.query(Partner).filter_by(tenant_id=tnt.id).all()
    stats = {
        "contacts": db.query(func.count(Contact.id)).filter_by(tenant_id=tnt.id).scalar(),
        "imported": db.query(func.count(Contact.id)).filter(Contact.tenant_id == tnt.id,
                                                            Contact.source.like("%crm%")).scalar(),
        "orders": db.query(func.count(Order.id)).filter_by(tenant_id=tnt.id).scalar(),
        "op_products": db.query(func.count(Product.id)).filter(
            Product.tenant_id == tnt.id, Product.attributes.isnot(None),
            Product.sku.like("%")).scalar(),
    }
    op = (tnt.settings or {}).get("officeplus") or {}
    ora = (tnt.settings or {}).get("oracle") or {}
    return render_template("admin/integrations.html", result=result, prev=session_preview,
                           fields=ci.FIELD_TITLES, partners=partners, stats=stats, op=op, ora=ora)


@bp.route("/integrations/officeplus", methods=["POST"])
@owner_required
def officeplus(tenant_slug):
    """Подключение к Partner B2B API системы OfficePlus (платформа Artgranit)."""
    from ..services import officeplus as op

    tnt = T()
    f = request.form
    action = f.get("action")
    try:
        if action == "save":
            settings = dict(tnt.settings or {})
            cfg = dict(settings.get("officeplus") or {})
            cfg.update({"base_url": f.get("base_url", "").strip() or op.DEFAULT_BASE,
                        "username": f.get("username", "").strip(),
                        "password": f.get("password") or cfg.get("password", ""),
                        "auto_publish": f.get("auto_publish") == "1"})
            settings["officeplus"] = cfg
            tnt.settings = settings
            log("officeplus.settings")
            db.commit()
            flash("Параметры подключения сохранены", "success")
        else:
            client = op.client_from_tenant(tnt)
            if action == "check":
                ok, msg = client.check()
                if ok:
                    op.save_token(tnt, client)
                flash(f"OfficePlus: {msg}", "success" if ok else "danger")
            elif action in ("sync_preview", "sync"):
                dry = action == "sync_preview"
                rep = op.sync_catalog(tnt, client, dry_run=dry,
                                      since=f.get("since") or None,
                                      limit_pages=f.get("pages", 5, type=int) or 5)
                op.save_token(tnt, client)
                if not dry:
                    log("officeplus.sync", details={"created": rep.created, "updated": rep.updated})
                    db.commit()
                flash(rep.line() + ("" if not rep.errors else f"; ошибок: {len(rep.errors)}"),
                      "success" if not rep.errors else "warning")
    except Exception as exc:  # noqa: BLE001
        flash(f"OfficePlus: {exc}", "danger")
    return redirect(url_for("admin.integrations"))


@bp.route("/integrations/oracle", methods=["POST"])
@owner_required
def oracle_source(tenant_slug):
    """Прямое чтение контрагентов из Oracle ERP OfficePlus."""
    from ..services import oracle_source as osrc

    tnt = T()
    f = request.form
    action = f.get("action")
    try:
        if action == "save":
            settings = dict(tnt.settings or {})
            cfg = dict(settings.get("oracle") or {})
            cfg.update({k: f.get(k, "").strip() for k in ("dsn", "user", "mode", "lib_dir", "wallet_dir", "schema")})
            cfg["sql_counterparties"] = f.get("sql_counterparties", "").strip()
            if f.get("password"):
                cfg["password"] = f["password"]
            settings["oracle"] = cfg
            tnt.settings = settings
            log("oracle.settings")
            db.commit()
            flash("Параметры подключения к Oracle сохранены", "success")
        else:
            cfg = osrc.OracleConfig.from_tenant(tnt)
            if action == "check":
                ok, msg = osrc.test_connection(cfg)
                flash(f"Oracle: {msg}", "success" if ok else "danger")
            elif action in ("preview", "import"):
                rep = osrc.import_counterparties(
                    tnt, cfg, dry_run=action == "preview",
                    limit=f.get("limit", 200, type=int) or 200,
                    search=f.get("search", "").strip(),
                    with_revenue=f.get("with_revenue") == "1",
                    days=f.get("days", 365, type=int) or 365)
                if action == "import":
                    log("oracle.import", details={"created": rep.created, "updated": rep.updated})
                    db.commit()
                flash(rep.line() + (f"; замечаний: {len(rep.errors)}" if rep.errors else ""),
                      "success" if not rep.errors else "warning")
    except Exception as exc:  # noqa: BLE001
        flash(f"Oracle: {exc}", "danger")
    return redirect(url_for("admin.integrations"))


@bp.route("/audit")
@owner_required
def audit(tenant_slug):
    rows = db.query(AuditLog).filter_by(tenant_id=T().id).order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit.html", rows=rows)
