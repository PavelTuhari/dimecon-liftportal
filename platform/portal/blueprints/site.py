"""Публичный white-label сайт компании + B2C-визард."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func

from ..db import SessionLocal as db, first_or_404
from ..models import Booking, CaseStudy, Equipment, EquipmentCategory, Order, Page, Product, Review, Service
from ..services import selector
from ..services.orders import create_order, upsert_contact
from ..services.pricing import calculate, zone_for

bp = Blueprint("site", __name__)


def _tenant():
    return g.tenant


def _free_today(tid):
    now = datetime.utcnow()
    busy = {b.equipment_id for b in db.query(Booking).filter(Booking.tenant_id == tid, Booking.starts_at <= now + timedelta(hours=8),
                                                            Booking.ends_at >= now, Booking.reason != "soft").all()}
    total = db.query(Equipment).filter_by(tenant_id=tid, is_published=True, status="active").count()
    return max(0, total - len(busy))


@bp.route("/")
def home(tenant_slug):
    tnt = _tenant()
    fleet = db.query(Equipment).filter_by(tenant_id=tnt.id, is_published=True).order_by(Equipment.sort, Equipment.capacity_t.desc()).limit(6).all()
    services = db.query(Service).filter_by(tenant_id=tnt.id, is_published=True).order_by(Service.sort).limit(8).all()
    cases = db.query(CaseStudy).filter_by(tenant_id=tnt.id, is_published=True).limit(3).all()
    reviews = db.query(Review).filter_by(tenant_id=tnt.id, is_published=True).order_by(Review.created_at.desc()).limit(3).all()
    stats = {
        "fleet": db.query(func.count(Equipment.id)).filter_by(tenant_id=tnt.id, is_published=True).scalar(),
        "max_cap": db.query(func.max(Equipment.capacity_t)).filter_by(tenant_id=tnt.id).scalar() or 0,
        "max_r": db.query(func.max(Equipment.radius_m)).filter_by(tenant_id=tnt.id).scalar() or 0,
        "free": _free_today(tnt.id),
    }
    return render_template("site/home.html", fleet=fleet, services=services, cases=cases, reviews=reviews, stats=stats,
                           tasks=selector.TASK_TYPES)


@bp.route("/equipment")
def equipment(tenant_slug):
    tnt = _tenant()
    q = db.query(Equipment).filter_by(tenant_id=tnt.id, is_published=True)
    cat = request.args.get("cat")
    if cat:
        q = q.join(EquipmentCategory).filter(EquipmentCategory.code == cat)
    mn = request.args.get("min_cap", type=float)
    if mn:
        q = q.filter(Equipment.capacity_t >= mn)
    items = q.order_by(Equipment.sort, Equipment.capacity_t.desc()).all()
    cats = db.query(EquipmentCategory).filter_by(tenant_id=tnt.id).order_by(EquipmentCategory.sort).all()
    return render_template("site/equipment.html", items=items, cats=cats, cat=cat, min_cap=mn)


@bp.route("/equipment/<slug>")
def equipment_item(tenant_slug, slug):
    eq = first_or_404(db.query(Equipment).filter_by(tenant_id=_tenant().id, slug=slug, is_published=True))
    upcoming = db.query(Booking).filter(Booking.equipment_id == eq.id, Booking.ends_at >= datetime.utcnow()).order_by(Booking.starts_at).limit(10).all()
    chart = [{"r": c.radius_m, "q": c.capacity_t, "h": c.height_m, "cfg": c.configuration} for c in eq.load_charts]
    return render_template("site/equipment_item.html", eq=eq, upcoming=upcoming, chart=chart)


@bp.route("/services")
def services(tenant_slug):
    items = db.query(Service).filter_by(tenant_id=_tenant().id, is_published=True).order_by(Service.sort).all()
    return render_template("site/services.html", items=items)


@bp.route("/services/<slug>")
def service_item(tenant_slug, slug):
    s = first_or_404(db.query(Service).filter_by(tenant_id=_tenant().id, slug=slug))
    return render_template("site/service_item.html", s=s)


@bp.route("/products")
def products(tenant_slug):
    items = db.query(Product).filter_by(tenant_id=_tenant().id, is_published=True).all()
    cats = sorted({p.category for p in items if p.category})
    return render_template("site/products.html", items=items, cats=cats)


@bp.route("/cases")
def cases(tenant_slug):
    items = db.query(CaseStudy).filter_by(tenant_id=_tenant().id, is_published=True).all()
    return render_template("site/cases.html", items=items)


@bp.route("/about")
def about(tenant_slug):
    reviews = db.query(Review).filter_by(tenant_id=_tenant().id, is_published=True).all()
    return render_template("site/about.html", reviews=reviews)


@bp.route("/contacts", methods=["GET", "POST"])
def contacts(tenant_slug):
    tnt = _tenant()
    if request.method == "POST":
        f = request.form
        c = upsert_contact(tnt, name=f["name"], phone=f["phone"], email=f.get("email", ""), source="contact_form")
        create_order(tnt, c, kind="b2c", source="contact_form", task_type="other", comment=f.get("message", ""),
                     starts_at=datetime.utcnow() + timedelta(days=1), escalated=True,
                     escalation_reasons=["Свободная заявка с формы контактов"])
        flash("Сообщение отправлено — ответим в течение 30 минут в рабочее время", "success")
        return redirect(url_for("site.contacts"))
    return render_template("site/contacts.html")


@bp.route("/p/<slug>")
def page(tenant_slug, slug):
    p = first_or_404(db.query(Page).filter_by(tenant_id=_tenant().id, slug=slug, is_published=True))
    return render_template("site/page.html", p=p)


@bp.route("/partners")
def partners_landing(tenant_slug):
    return render_template("site/partners.html")


# ------------------------------------------------------------- Визард

WZ_KEY = "wz"


def _wz():
    return session.setdefault(WZ_KEY, {})


def _save(d):
    session[WZ_KEY] = d
    session.modified = True


@bp.route("/calculator", methods=["GET", "POST"])
def wizard(tenant_slug):
    tnt = _tenant()
    d = _wz()
    step = int(request.values.get("step", d.get("step", 1)))
    if request.method == "POST":
        f = request.form
        if f.get("back"):
            step = max(1, step - 1)
        else:
            if step == 1:
                d["task"] = f.get("task", "lift_height")
                if d["task"] == "other":
                    d["weight"] = 0; d["preset"] = "custom"
                step = 2 if d["task"] != "other" else 6
            elif step == 2:
                d["preset"] = f.get("preset", "custom")
                p = selector.PRESET_MAP.get(d["preset"], selector.PRESET_MAP["custom"])
                w = f.get("weight", type=float)
                if f.get("unknown"):
                    lo, hi = selector.estimate_mass(f.get("l", 1, type=float), f.get("w", 1, type=float), f.get("h", 1, type=float),
                                                    f.get("material", "concrete"), f.get("hollow") == "1")
                    d["weight"] = hi; d["weight_range"] = [lo, hi]
                else:
                    d["weight"] = w if w else p[3] or p[2]
                    d.pop("weight_range", None)
                d["qty"] = f.get("qty", 1, type=int)
                d["dim"] = f.get("dim", type=float) or p[4]
                d["cargo_h"] = p[5]
                step = 3 if d["task"] != "unload" else 4
                if d["task"] == "unload":
                    d["height"] = 2
            elif step == 3:
                d["height"] = f.get("height", 3, type=float)
                step = 4
            elif step == 4:
                d["radius_code"] = f.get("radius_code", "sidewalk")
                custom = f.get("radius_m", type=float)
                d["offset"] = custom if custom else next((r[1] for r in selector.RADIUS_OPTIONS if r[0] == d["radius_code"]), 10)
                step = 5
            elif step == 5:
                d["conditions"] = f.getlist("cond")
                step = 6
            elif step == 6:
                try:
                    d["start"] = datetime.strptime(f["start"], "%Y-%m-%dT%H:%M").isoformat()
                except (ValueError, KeyError):
                    d["start"] = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).isoformat()
                d["hours"] = f.get("hours", 4, type=float)
                d["flex"] = f.get("flex") == "1"
                d["address"] = f.get("address", "")
                d["distance"] = f.get("distance", 10, type=float)
                step = 7
        d["step"] = step
        _save(d)
        return redirect(url_for("site.wizard", step=step))

    d["step"] = step
    _save(d)
    ctx = dict(step=step, d=d, tasks=selector.TASK_TYPES, presets=selector.CARGO_PRESETS, materials=selector.MATERIALS,
               heights=selector.HEIGHT_OPTIONS, radii=selector.RADIUS_OPTIONS, conditions=selector.CONDITIONS,
               default_start=(datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).strftime("%Y-%m-%dT%H:%M"))
    if step == 7:
        ctx.update(_result(tnt, d))
    return render_template("site/wizard.html", **ctx)


def _result(tnt, d):
    start = datetime.fromisoformat(d.get("start")) if d.get("start") else datetime.now() + timedelta(days=1)
    sel = selector.select_equipment(tnt.id, weight_t=float(d.get("weight") or 0), height_m=float(d.get("height") or 0),
                                    offset_m=float(d.get("offset") or 10), cargo_dim_m=float(d.get("dim") or 2),
                                    cargo_h_m=float(d.get("cargo_h") or 1.5), start=start, hours=float(d.get("hours") or 4),
                                    conditions=d.get("conditions", []), task_type=d.get("task", "lift_height"))
    first_online = not g.user
    offers = []
    for c in sel.candidates:
        price = calculate(tnt, c.equipment, start=start, hours=float(d.get("hours") or 4), distance_km=float(d.get("distance") or 10),
                          conditions=d.get("conditions", []), flexible=d.get("flex", False), first_online=first_online)
        offers.append({"c": c, "price": price})
    zone = zone_for(tnt, float(d.get("distance") or 10))
    return {"sel": sel, "offers": offers, "zone": zone, "start": start}


@bp.route("/calculator/submit", methods=["POST"])
def wizard_submit(tenant_slug):
    tnt = _tenant()
    d = _wz()
    if not d.get("step"):
        return redirect(url_for("site.wizard"))
    f = request.form
    res = _result(tnt, d)
    eq_id = f.get("equipment_id", type=int)
    offer = next((o for o in res["offers"] if o["c"].equipment.id == eq_id), None)
    contact = upsert_contact(tnt, name=f["name"].strip(), phone=f["phone"], email=f.get("email", ""),
                             user_id=g.user.id if g.user else None, source="wizard")
    preset = selector.PRESET_MAP.get(d.get("preset"), selector.PRESET_MAP["custom"])
    order = create_order(
        tnt, contact, kind="b2c", source="wizard", task_type=d.get("task", ""),
        cargo=preset[1]["ru"] if d.get("preset") != "custom" else "груз по вводу",
        weight_t=float(d.get("weight") or 0), height_m=float(d.get("height") or 0), radius_m=float(d.get("offset") or 0),
        conditions=d.get("conditions", []), address=d.get("address", ""), zone=res["zone"]["code"],
        distance_km=float(d.get("distance") or 0), starts_at=res["start"], hours=float(d.get("hours") or 4),
        flexible_date=bool(d.get("flex")), equipment_id=eq_id,
        price_min=offer["price"]["min"] if offer else 0, price_max=offer["price"]["max"] if offer else 0,
        breakdown=offer["price"]["lines"] if offer else [],
        escalated=res["sel"].escalated or not offer, escalation_reasons=res["sel"].reasons,
        selector_log={"m_calc": res["sel"].m_calc, "h_req": res["sel"].h_req,
                      "candidates": [{"eq": o["c"].equipment.model, "reserve": o["c"].reserve, "r_req": o["c"].r_req, "label": o["c"].label} for o in res["offers"]]},
        comment=f.get("comment", ""),
    )
    session.pop(WZ_KEY, None)
    session["last_order"] = order.number
    return redirect(url_for("site.wizard_done", number=order.number))


@bp.route("/calculator/done/<number>")
def wizard_done(tenant_slug, number):
    order = first_or_404(db.query(Order).filter_by(tenant_id=_tenant().id, number=number))
    return render_template("site/wizard_done.html", order=order)


@bp.route("/calculator/reset")
def wizard_reset(tenant_slug):
    session.pop(WZ_KEY, None)
    return redirect(url_for("site.wizard"))


@bp.route("/track/<number>")
def track(tenant_slug, number):
    order = first_or_404(db.query(Order).filter_by(tenant_id=_tenant().id, number=number))
    if session.get("last_order") != number and not (g.user and (g.user.is_platform_admin or (order.contact and order.contact.user_id == g.user.id) or getattr(g, "membership", None))):
        abort(403)
    return render_template("site/track.html", order=order)
