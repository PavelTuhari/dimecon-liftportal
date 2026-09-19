"""Центральный портал: маркетплейс компаний, регистрация компании, суперадмин."""
from __future__ import annotations

import re

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from ..auth import clean_email, hash_password, login_user, logout_user, platform_admin_required, verify_password
from ..db import SessionLocal as db
from ..models import AuditLog, Equipment, Membership, Order, Outbox, Tenant, User
from ..seed import demo_accounts, seed_tenant_defaults

bp = Blueprint("platform", __name__)


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    city = request.args.get("city", "").strip()
    profile = request.args.get("profile", "").strip()
    query = db.query(Tenant).filter_by(status="active", is_listed=True)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Tenant.name.ilike(like), Tenant.city.ilike(like), Tenant.legal_name.ilike(like)))
    if city:
        query = query.filter(Tenant.city == city)
    if profile:
        query = query.filter(Tenant.profile == profile)
    tenants = query.order_by(Tenant.created_at).all()
    stats = {}
    for tnt in tenants:
        fleet = db.query(Equipment).filter_by(tenant_id=tnt.id, is_published=True)
        stats[tnt.id] = {
            "fleet": fleet.count(),
            "max_cap": db.query(func.max(Equipment.capacity_t)).filter_by(tenant_id=tnt.id).scalar() or 0,
            "orders": db.query(func.count(Order.id)).filter_by(tenant_id=tnt.id).scalar() or 0,
        }
    cities = [c[0] for c in db.query(Tenant.city).filter_by(status="active").distinct().all() if c[0]]
    return render_template("platform/index.html", tenants=tenants, stats=stats, cities=cities, q=q, city=city, profile=profile)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = clean_email(request.form.get("email", ""))
        u = db.query(User).filter_by(email=email).first()
        if verify_password(u, request.form.get("password", "")):
            login_user(u)
            u.last_login_at = func.now()
            db.commit()
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            # владельца ведём в кабинет его компании
            m = next((m for m in u.memberships if m.role in Membership.STAFF_ROLES), None)
            if u.is_platform_admin:
                return redirect(url_for("platform.admin"))
            if m:
                return redirect(url_for("admin.dashboard", tenant_slug=m.tenant.slug))
            if u.memberships:
                return redirect(url_for("account.index", tenant_slug=u.memberships[0].tenant.slug))
            return redirect(url_for("platform.index"))
        if not u:
            flash(f"Пользователь {email or '—'} не найден. Проверьте адрес.", "danger")
        elif not u.is_active:
            flash("Учётная запись отключена.", "danger")
        else:
            flash("Пароль не подошёл. Проверьте раскладку и регистр букв.", "danger")
    return render_template("platform/login.html", demo=demo_accounts())


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    return redirect(url_for("platform.index"))


SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(s: str) -> str:
    table = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюяăîșțâ", "abvgdeejziiklmnoprstufhccss-y-eua" + "aista")
    s = s.lower().translate(table)
    s = SLUG_RE.sub("-", s).strip("-")
    return s[:40] or "company"


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Онбординг компании (модель Airbnb: создал профиль — получил сайт и кабинет)."""
    if request.method == "POST":
        f = request.form
        name = f["name"].strip()
        email = f["email"].strip().lower()
        if not name or not email or len(f.get("password", "")) < 6:
            flash("Заполните название, e-mail и пароль (не короче 6 символов)", "danger")
            return render_template("platform/register.html", form=f)
        slug = slugify(f.get("slug") or name)
        base, i = slug, 2
        while db.query(Tenant).filter_by(slug=slug).first():
            slug = f"{base}-{i}"; i += 1
        user = db.query(User).filter_by(email=email).first()
        if user and not verify_password(user, f["password"]):
            flash("Пользователь с таким e-mail уже существует — введите его пароль", "danger")
            return render_template("platform/register.html", form=f)
        if not user:
            user = User(email=email, full_name=f.get("owner_name", "").strip() or name, phone=f.get("phone", ""),
                        password_hash=hash_password(f["password"]))
            db.add(user)
        tenant = Tenant(slug=slug, name=name, legal_name=f.get("legal_name", ""), city=f.get("city", "Chișinău") or "Chișinău",
                        phone=f.get("phone", ""), email=email, profile=f.get("profile", "cranes"),
                        founded_year=int(f["founded_year"]) if f.get("founded_year", "").isdigit() else None,
                        tagline={"ru": f.get("tagline", ""), "ro": "", "en": ""},
                        theme={"accent": f.get("accent") or "#F5A623", "navy": f.get("navy") or "#1F3A52"},
                        status="active")
        db.add(tenant)
        db.flush()
        db.add(Membership(tenant_id=tenant.id, user_id=user.id, role="owner"))
        seed_tenant_defaults(tenant, demo=f.get("demo") == "1")
        db.add(AuditLog(tenant_id=tenant.id, user_id=user.id, action="tenant.created", entity="tenant", entity_id=tenant.id))
        db.commit()
        login_user(user)
        flash(f"Компания «{name}» создана. Ваш сайт: /s/{slug}", "success")
        return redirect(url_for("admin.dashboard", tenant_slug=slug))
    return render_template("platform/register.html", form={})


@bp.route("/pricing")
def pricing():
    return render_template("platform/pricing.html")


# ---------------- суперадмин ----------------

@bp.route("/admin")
@platform_admin_required
def admin():
    tenants = db.query(Tenant).order_by(Tenant.created_at.desc()).all()
    counts = {t.id: db.query(func.count(Order.id)).filter_by(tenant_id=t.id).scalar() for t in tenants}
    totals = {
        "tenants": len(tenants), "users": db.query(func.count(User.id)).scalar(),
        "orders": db.query(func.count(Order.id)).scalar(), "equipment": db.query(func.count(Equipment.id)).scalar(),
        "mail_failed": db.query(func.count(Outbox.id)).filter(Outbox.status != "sent").scalar(),
    }
    return render_template("platform/admin.html", tenants=tenants, counts=counts, totals=totals)


@bp.route("/admin/tenant/<int:tid>/status", methods=["POST"])
@platform_admin_required
def tenant_status(tid):
    tnt = db.get(Tenant, tid)
    tnt.status = request.form["status"]
    tnt.plan = request.form.get("plan", tnt.plan)
    tnt.is_listed = request.form.get("is_listed") == "1"
    db.add(AuditLog(tenant_id=tid, user_id=g.user.id, action="tenant.status", details={"status": tnt.status, "plan": tnt.plan}))
    db.commit()
    flash("Сохранено", "success")
    return redirect(url_for("platform.admin"))


@bp.route("/admin/impersonate/<int:tid>", methods=["POST"])
@platform_admin_required
def impersonate(tid):
    tnt = db.get(Tenant, tid)
    return redirect(url_for("admin.dashboard", tenant_slug=tnt.slug))


@bp.route("/admin/mail")
@platform_admin_required
def mail_log():
    rows = db.query(Outbox).order_by(Outbox.created_at.desc()).limit(200).all()
    return render_template("platform/mail.html", rows=rows)


@bp.route("/admin/ddl")
@platform_admin_required
def ddl():
    from ..db import mysql_ddl
    from flask import Response
    return Response(mysql_ddl(), mimetype="text/plain; charset=utf-8")
