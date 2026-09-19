"""REST API v1 для партнёров: ключ компании в заголовке X-API-Key (tenant.settings.api_key)."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, jsonify, request

from ..db import SessionLocal as db
from ..models import Equipment, Order, Tenant
from ..services.pricing import calculate

bp = Blueprint("api", __name__)


def _tenant() -> Tenant:
    key = request.headers.get("X-API-Key", "")
    if not key:
        abort(401, "X-API-Key required")
    for tnt in db.query(Tenant).filter_by(status="active").all():
        if (tnt.settings or {}).get("api_key") == key:
            return tnt
    abort(401, "invalid key")


@bp.route("/v1/equipment")
def equipment():
    tnt = _tenant()
    rows = db.query(Equipment).filter_by(tenant_id=tnt.id, is_published=True).all()
    return jsonify([{"id": e.id, "brand": e.brand, "model": e.model, "category": e.category.code if e.category else None,
                     "capacity_t": e.capacity_t, "radius_m": e.radius_m, "height_m": e.height_m,
                     "hourly_rate": e.hourly_rate, "min_hours": e.min_hours,
                     "load_chart": [{"r": c.radius_m, "q": c.capacity_t, "h": c.height_m} for c in e.load_charts]} for e in rows])


@bp.route("/v1/quotes", methods=["POST"])
def quotes():
    tnt = _tenant()
    j = request.get_json(force=True) or {}
    eq = db.get(Equipment, j.get("equipment_id"))
    if not eq or eq.tenant_id != tnt.id:
        abort(404)
    start = datetime.fromisoformat(j.get("start")) if j.get("start") else datetime.utcnow()
    return jsonify(calculate(tnt, eq, start=start, hours=float(j.get("hours", 4)), distance_km=float(j.get("distance_km", 10)),
                             conditions=j.get("conditions", []), flexible=bool(j.get("flexible"))))


@bp.route("/v1/orders")
def orders():
    tnt = _tenant()
    rows = db.query(Order).filter_by(tenant_id=tnt.id).order_by(Order.created_at.desc()).limit(200).all()
    return jsonify([{"number": o.number, "status": o.status, "stage": o.stage, "starts_at": o.starts_at.isoformat() if o.starts_at else None,
                     "equipment_id": o.equipment_id, "price_min": o.price_min, "price_max": o.price_max, "address": o.address} for o in rows])


@bp.route("/v1/health")
def health():
    return jsonify({"ok": True, "time": datetime.utcnow().isoformat()})
