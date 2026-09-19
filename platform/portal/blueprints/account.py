"""Личный кабинет клиента компании (B2C)."""
from __future__ import annotations

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..auth import clean_email, hash_password, login_required, login_user, logout_user, verify_password
from ..db import SessionLocal as db, first_or_404
from ..models import Contact, Document, Membership, Order, Review, User
from ..seed import demo_accounts

bp = Blueprint("account", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login(tenant_slug):
    if request.method == "POST":
        email = clean_email(request.form.get("email", ""))
        u = db.query(User).filter_by(email=email).first()
        if verify_password(u, request.form.get("password", "")):
            login_user(u)
            if not db.query(Membership).filter_by(tenant_id=g.tenant.id, user_id=u.id).first():
                db.add(Membership(tenant_id=g.tenant.id, user_id=u.id, role="customer"))
                db.commit()
            nxt = request.args.get("next")
            m = db.query(Membership).filter_by(tenant_id=g.tenant.id, user_id=u.id).first()
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            if m and m.role in Membership.STAFF_ROLES:
                return redirect(url_for("admin.dashboard"))
            if m and m.role == "partner":
                return redirect(url_for("partner.index"))
            return redirect(url_for("account.index"))
        # разные причины отказа называем разными словами: так видно, что именно исправить
        if not u:
            flash(f"Пользователь {email or '—'} не найден. Проверьте адрес или зарегистрируйтесь.", "danger")
        elif not u.is_active:
            flash("Учётная запись отключена — обратитесь к администратору компании.", "danger")
        else:
            flash("Пароль не подошёл. Проверьте раскладку и регистр букв.", "danger")
    return render_template("account/login.html",
                           demo=demo_accounts(("client@example.com", "partner@example.com", "owner@dimecon.md")))


@bp.route("/register", methods=["GET", "POST"])
def register(tenant_slug):
    if request.method == "POST":
        f = request.form
        email = clean_email(f["email"])
        if db.query(User).filter_by(email=email).first():
            flash("Такой e-mail уже зарегистрирован — войдите", "warning")
            return redirect(url_for("account.login"))
        if len(f["password"]) < 6:
            flash("Пароль не короче 6 символов", "danger")
            return render_template("account/register.html")
        u = User(email=email, full_name=f["name"].strip(), phone=f.get("phone", ""), password_hash=hash_password(f["password"]))
        db.add(u); db.flush()
        db.add(Membership(tenant_id=g.tenant.id, user_id=u.id, role="customer"))
        # привязываем ранее оставленные заявки по телефону/почте
        from ..services.orders import normalize_phone
        for c in db.query(Contact).filter_by(tenant_id=g.tenant.id).filter(
                (Contact.email == email) | (Contact.phone == normalize_phone(f.get("phone", "")))).all():
            c.user_id = u.id
        db.commit()
        login_user(u)
        return redirect(url_for("account.index"))
    return render_template("account/register.html")


@bp.route("/logout", methods=["POST"])
def logout(tenant_slug):
    logout_user()
    return redirect(url_for("site.home"))


def _my_orders():
    cids = [c.id for c in db.query(Contact).filter_by(tenant_id=g.tenant.id, user_id=g.user.id).all()]
    if not cids:
        return db.query(Order).filter(Order.id < 0)
    return db.query(Order).filter(Order.tenant_id == g.tenant.id, Order.contact_id.in_(cids))


@bp.route("/")
@login_required
def index(tenant_slug):
    orders = _my_orders().order_by(Order.created_at.desc()).all()
    active = [o for o in orders if o.status not in ("completed", "paid", "cancelled")]
    return render_template("account/index.html", orders=orders, active=active)


@bp.route("/orders/<int:oid>")
@login_required
def order(tenant_slug, oid):
    o = first_or_404(_my_orders().filter(Order.id == oid))
    docs = db.query(Document).filter_by(order_id=o.id).all()
    review = db.query(Review).filter_by(order_id=o.id).first()
    return render_template("account/order.html", o=o, docs=docs, review=review)


@bp.route("/orders/<int:oid>/repeat", methods=["POST"])
@login_required
def repeat(tenant_slug, oid):
    o = first_or_404(_my_orders().filter(Order.id == oid))
    session["wz"] = {"step": 6, "task": o.task_type or "lift_height", "preset": "custom", "weight": o.weight_t,
                     "height": o.height_m, "offset": o.radius_m, "dim": 2.0, "cargo_h": 1.5,
                     "conditions": o.conditions or [], "address": o.address, "distance": o.distance_km or 10, "qty": 1}
    flash("Параметры прошлого заказа подставлены — выберите дату", "success")
    return redirect(url_for("site.wizard", step=6))


@bp.route("/orders/<int:oid>/review", methods=["POST"])
@login_required
def review(tenant_slug, oid):
    o = first_or_404(_my_orders().filter(Order.id == oid))
    db.add(Review(tenant_id=g.tenant.id, order_id=o.id, author=g.user.full_name, rating=int(request.form["rating"]),
                  body=request.form.get("body", "")))
    db.commit()
    flash("Спасибо за оценку! Отзыв появится после модерации.", "success")
    return redirect(url_for("account.order", oid=oid))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile(tenant_slug):
    if request.method == "POST":
        g.user.full_name = request.form["name"]; g.user.phone = request.form["phone"]
        g.user.locale = request.form.get("locale", g.user.locale)
        if request.form.get("password"):
            g.user.password_hash = hash_password(request.form["password"])
        db.commit(); flash("Сохранено", "success")
    return render_template("account/profile.html")
