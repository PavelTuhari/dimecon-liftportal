"""Движок цен (Том 2). Все коэффициенты берутся из tenant.pricing и редактируются в кабинете."""
from __future__ import annotations

from datetime import datetime

from ..models import Equipment, Tenant

DEFAULT_PRICING = {
    "time": {"day": 1.0, "evening": 1.2, "night": 1.5, "saturday": 1.25, "sunday": 1.4},
    "season": {"11": 0.9, "12": 0.9, "1": 0.9, "2": 0.9, "3": 1.05, "4": 1.05, "5": 1.05, "6": 1.1, "7": 1.1, "8": 1.1, "9": 1.1, "10": 1.0},
    "conditions": {"tight": 1.15, "soft_ground": 1.10, "power_line": 1.30, "night": 1.0},
    "conditions_cap": 1.5,
    "urgency": [[72, 1.0], [24, 1.05], [6, 1.15], [0, 1.3]],
    "zones": [
        {"code": "city", "name": "Город", "fee": 1500, "free_km": 15, "per_km": 25, "max_km": 15},
        {"code": "suburb", "name": "Пригород до 30 км", "fee": 1500, "free_km": 15, "per_km": 25, "max_km": 30},
        {"code": "region", "name": "Регионы", "fee": 2500, "free_km": 0, "per_km": 25, "max_km": 400},
    ],
    "addons": {"rigger": 600, "slings": 200, "pads": 300, "road_closure": 2500, "night_light": 700},
    "discounts": {"flexible_date": 0.07, "first_online": 0.05, "max_total": 0.25},
    "range_width": 0.35,
}


def pricing_of(tenant: Tenant) -> dict:
    p = dict(DEFAULT_PRICING)
    p.update(tenant.pricing or {})
    return p


def _num(form, name: str, default: float = 0.0) -> float:
    raw = (form.get(name) or "").replace(",", ".").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def pricing_from_form(form, current: dict | None = None) -> dict:
    """Форма настроек прайса → структура коэффициентов, зон, допуслуг и скидок.

    Поля формы называются по смыслу (time_night, zone_name_0, addon_rigger…), поэтому
    владелец компании правит цены обычными полями, а не JSON-документом.
    """
    base = dict(DEFAULT_PRICING)
    base.update(current or {})
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in base.items()}

    out["time"] = {key: _num(form, f"time_{key}", value)
                   for key, value in DEFAULT_PRICING["time"].items()}
    out["season"] = {month: _num(form, f"season_{month}", value)
                     for month, value in DEFAULT_PRICING["season"].items()}
    out["conditions"] = {key: _num(form, f"cond_{key}", value)
                         for key, value in DEFAULT_PRICING["conditions"].items()}
    out["conditions_cap"] = _num(form, "conditions_cap", DEFAULT_PRICING["conditions_cap"])
    out["addons"] = {key: _num(form, f"addon_{key}", value)
                     for key, value in DEFAULT_PRICING["addons"].items()}
    out["discounts"] = {
        "flexible_date": _num(form, "discount_flexible", DEFAULT_PRICING["discounts"]["flexible_date"]),
        "first_online": _num(form, "discount_first", DEFAULT_PRICING["discounts"]["first_online"]),
        "max_total": _num(form, "discount_max", DEFAULT_PRICING["discounts"]["max_total"]),
    }
    out["range_width"] = _num(form, "range_width", DEFAULT_PRICING["range_width"])

    urgency = []
    for hours, coef in DEFAULT_PRICING["urgency"]:
        urgency.append([hours, _num(form, f"urgency_{hours}", coef)])
    out["urgency"] = urgency

    zones = []
    for idx in range(0, 12):
        name = (form.get(f"zone_name_{idx}") or "").strip()
        if not name:
            continue
        code = (form.get(f"zone_code_{idx}") or "").strip() or f"zone{idx + 1}"
        zones.append({"code": code, "name": name, "fee": _num(form, f"zone_fee_{idx}"),
                      "free_km": _num(form, f"zone_free_{idx}"), "per_km": _num(form, f"zone_perkm_{idx}"),
                      "max_km": _num(form, f"zone_max_{idx}")})
    if zones:
        out["zones"] = sorted(zones, key=lambda z: z["max_km"])
    return out


def pricing_problems(tenant: Tenant) -> list[str]:
    """Что в прайсе выглядит незаполненным — показывается в настройках."""
    p = pricing_of(tenant)
    out = []
    zones = p.get("zones") or []
    if not zones:
        out.append("не заданы зоны подачи")
    if zones and any(z.get("max_km", 0) <= 0 for z in zones):
        out.append("у зоны не указан предел по километрам")
    if p.get("discounts", {}).get("max_total", 0) <= 0:
        out.append("не задан потолок скидок")
    if p.get("conditions_cap", 0) <= 1:
        out.append("потолок надбавок за условия меньше единицы")
    return out


def zone_for(tenant: Tenant, distance_km: float) -> dict:
    zones = pricing_of(tenant)["zones"]
    for z in zones:
        if distance_km <= z["max_km"]:
            return z
    return zones[-1]


def time_factor(p: dict, start: datetime) -> tuple[float, str]:
    wd = start.weekday()
    if wd == 6:
        return p["time"]["sunday"], "воскресенье"
    if wd == 5:
        return p["time"]["saturday"], "суббота"
    h = start.hour
    if 22 <= h or h < 7:
        return p["time"]["night"], "ночь"
    if 19 <= h < 22:
        return p["time"]["evening"], "вечер"
    return 1.0, ""


def urgency_factor(p: dict, start: datetime, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    hrs = (start - now).total_seconds() / 3600
    for threshold, k in p["urgency"]:
        if hrs >= threshold:
            return k
    return p["urgency"][-1][1]


def calculate(tenant: Tenant, eq: Equipment, *, start: datetime, hours: float, distance_km: float,
              conditions: list[str], flexible: bool = False, first_online: bool = False,
              partner_discount: float = 0.0) -> dict:
    p = pricing_of(tenant)
    lines = []
    cur = tenant.currency

    billable = max(hours, eq.min_hours or 0)
    base = billable * eq.hourly_rate
    lines.append({"code": "base", "title": f"Работа техники ({billable:g} ч × {eq.hourly_rate:g} {cur})", "amount": round(base)})

    kt, tlabel = time_factor(p, start)
    if kt != 1.0:
        lines.append({"code": "time", "title": f"Надбавка за время ({tlabel}) × {kt}", "amount": round(base * (kt - 1))})
    ks = float(p["season"].get(str(start.month), 1.0))
    if ks != 1.0:
        lines.append({"code": "season", "title": f"Сезонный коэффициент × {ks}", "amount": round(base * kt * (ks - 1))})

    kc_list = [p["conditions"].get(c, 1.0) for c in conditions if p["conditions"].get(c, 1.0) != 1.0]
    kc = 1.0
    if kc_list:
        kc = min(p["conditions_cap"], max(kc_list) + 0.05 * (len(kc_list) - 1))
        lines.append({"code": "cond", "title": f"Условия площадки × {kc:.2f}", "amount": round(base * kt * ks * (kc - 1))})

    zone = zone_for(tenant, distance_km)
    fee = eq.mobilization_fee or zone["fee"]
    extra_km = max(0.0, distance_km - zone["free_km"])
    per_km = eq.per_km_rate or zone["per_km"]
    mob = fee + extra_km * per_km * 2
    lines.append({"code": "mob", "title": f"Подача техники (зона «{zone['name']}»"
                  + (f", {extra_km:g} км × {per_km:g} × 2" if extra_km else "") + ")", "amount": round(mob)})

    addons = 0.0
    if "rigger" in conditions:
        addons += p["addons"]["rigger"]; lines.append({"code": "rigger", "title": "Стропальщик", "amount": p["addons"]["rigger"]})
    if "soft_ground" in conditions:
        addons += p["addons"]["pads"]; lines.append({"code": "pads", "title": "Подкладки под опоры", "amount": p["addons"]["pads"]})
    if "road_closure" in conditions:
        addons += p["addons"]["road_closure"]; lines.append({"code": "permit", "title": "Оформление разрешения на перекрытие", "amount": p["addons"]["road_closure"]})
    if "night" in conditions:
        addons += p["addons"]["night_light"]; lines.append({"code": "light", "title": "Осветительная установка", "amount": p["addons"]["night_light"]})

    ku = urgency_factor(p, start)
    subtotal = base * kt * ks * kc + mob + addons
    if ku != 1.0:
        u = (base * kt * ks * kc + mob) * (ku - 1)
        subtotal += u
        lines.append({"code": "urgent", "title": f"Срочность × {ku}", "amount": round(u)})

    d = p["discounts"]
    requested = []
    if flexible:
        requested.append(("d_flex", "Скидка за гибкую дату", d["flexible_date"]))
    if first_online:
        requested.append(("d_first", "Скидка за первый онлайн-заказ", d["first_online"]))
    if partner_discount:
        requested.append(("d_partner", "Договорная скидка партнёра", partner_discount))

    raw = sum(x[2] for x in requested)
    disc = min(raw, d["max_total"])
    # при срабатывании потолка доли уменьшаются пропорционально, чтобы сумма строк
    # в точности совпадала с фактически применённой скидкой
    scale = (disc / raw) if raw > d["max_total"] else 1.0
    for code, title, rate in requested:
        applied = rate * scale
        note = "" if scale == 1.0 else f" (ограничено потолком {round(d['max_total'] * 100)} %)"
        lines.append({"code": code, "title": f"{title} −{round(applied * 100, 1):g} %{note}",
                      "amount": -round(subtotal * applied)})
    net = subtotal * (1 - disc)
    vat = net * (tenant.vat_rate or 0) / 100
    total = round((net + vat) / 10) * 10
    lines.append({"code": "vat", "title": f"НДС {tenant.vat_rate:g} %", "amount": round(vat)})
    width = p["range_width"]
    return {
        "lines": lines,
        "net": round(net), "vat": round(vat), "total": total,
        "min": round(total / 10) * 10,
        "max": round(total * (1 + width) / 10) * 10,
        "zone": zone["code"], "currency": cur,
        "included": ["оператор", "топливо", "подача и возврат", "страхование ГО"],
        "excluded": ["простой по вине заказчика", "часы сверх заказанных", "разрешения (если не заказаны)"],
    }
