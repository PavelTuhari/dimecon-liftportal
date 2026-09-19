"""Страницы модуля: сводка, заявки, парк. Источник данных — REST API LiftPortal."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime

from flask import render_template_string, request

from . import blueprint

BASE = os.getenv("LIFTPORTAL_BASE", "http://127.0.0.1:8090")
KEY = os.getenv("LIFTPORTAL_API_KEY", "")
TIMEOUT = int(os.getenv("LIFTPORTAL_TIMEOUT", "15"))


def api(path: str):
    """Чтение LiftPortal. Ошибка связи не роняет страницу — она показывается как предупреждение."""
    req = urllib.request.Request(f"{BASE}/api/v1{path}", headers={"X-API-Key": KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace")), ""
    except urllib.error.HTTPError as exc:
        return None, f"LiftPortal ответил HTTP {exc.code}: проверьте LIFTPORTAL_API_KEY"
    except Exception as exc:  # noqa: BLE001
        return None, f"нет связи с LiftPortal ({BASE}): {exc}"


PAGE = """<!doctype html><html lang=ru><meta charset=utf-8><title>{{ title }}</title>
<style>
body{font-family:Manrope,system-ui,sans-serif;margin:0;padding:22px;color:#14181B;background:#F5F6F7}
h1{font-size:22px;margin:0 0 4px}.sub{color:#5A646B;font-size:13px;margin-bottom:18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:18px}
.kpi{background:#fff;border:1px solid #DDE1E4;border-radius:10px;padding:14px 16px}
.kpi b{display:block;font-size:26px;font-weight:800}.kpi span{font-size:12px;color:#5A646B}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #DDE1E4;border-radius:10px;overflow:hidden;font-size:13px}
th,td{padding:8px 11px;text-align:left;border-bottom:1px solid #EDEFF1}th{background:#1F3A52;color:#fff;font-size:12px}
.warn{background:#FCEFD9;border:1px solid #F3D6A1;color:#7A4E00;padding:11px 14px;border-radius:8px;margin-bottom:16px;font-size:13px}
a.btn{display:inline-block;background:#F5A623;color:#14181B;text-decoration:none;font-weight:700;padding:8px 14px;border-radius:8px;font-size:13px}
nav a{margin-right:12px;font-size:13px;color:#1F3A52}
</style>
<nav><a href="../liftportal">Сводка</a><a href="../liftportal/orders">Заявки</a><a href="../liftportal/fleet">Парк</a>
<a href="{{ base }}" target="_blank">Открыть LiftPortal ↗</a></nav>
<h1>{{ title }}</h1><div class=sub>{{ sub }}</div>
{% if warn %}<div class=warn>{{ warn }}</div>{% endif %}
{% if kpis %}<div class=kpis>{% for k, v in kpis %}<div class=kpi><b>{{ v }}</b><span>{{ k }}</span></div>{% endfor %}</div>{% endif %}
{% if rows %}<table><thead><tr>{% for h in heads %}<th>{{ h }}</th>{% endfor %}</tr></thead>
<tbody>{% for r in rows %}<tr>{% for c in r %}<td>{{ c }}</td>{% endfor %}</tr>{% endfor %}</tbody></table>{% endif %}
</html>"""


def page(title, sub, *, kpis=None, heads=None, rows=None, warn=""):
    return render_template_string(PAGE, title=title, sub=sub, kpis=kpis or [], heads=heads or [],
                                  rows=rows or [], warn=warn, base=BASE)


@blueprint.route("/")
def index():
    orders, err1 = api("/orders")
    fleet, err2 = api("/equipment")
    warn = err1 or err2
    kpis = []
    if orders is not None and fleet is not None:
        active = [o for o in orders if o.get("status") not in ("completed", "paid", "cancelled")]
        today = [o for o in orders if (o.get("starts_at") or "")[:10] == datetime.now().strftime("%Y-%m-%d")]
        kpis = [("заявок всего", len(orders)), ("в работе", len(active)),
                ("подач сегодня", len(today)), ("единиц техники", len(fleet))]
    rows = [[o.get("number"), (o.get("starts_at") or "")[:16].replace("T", " "), o.get("status"),
             o.get("address", "")[:44], o.get("price_max") or o.get("price_min") or ""]
            for o in (orders or [])[:10]]
    return page("Спецтехника и аренда кранов", "Витрина платформы LiftPortal в портале Artgranit",
                kpis=kpis, heads=["Заявка", "Подача", "Статус", "Объект", "Сумма"], rows=rows, warn=warn)


@blueprint.route("/orders")
def orders():
    data, warn = api("/orders")
    rows = [[o.get("number"), (o.get("starts_at") or "")[:16].replace("T", " "), o.get("stage"),
             o.get("status"), o.get("address", "")[:48], o.get("price_final") or o.get("price_max") or ""]
            for o in (data or [])]
    return page("Заявки и сделки", f"Получено записей: {len(rows)}",
                heads=["Заявка", "Подача", "Этап", "Статус", "Объект", "Сумма"], rows=rows, warn=warn)


@blueprint.route("/fleet")
def fleet():
    data, warn = api("/equipment")
    rows = [[e.get("brand"), e.get("model"), e.get("category"), e.get("capacity_t"),
             e.get("radius_m"), e.get("height_m"), e.get("hourly_rate"), len(e.get("load_chart") or [])]
            for e in (data or [])]
    return page("Парк техники", f"Единиц в каталоге: {len(rows)}",
                heads=["Бренд", "Модель", "Категория", "Г/П, т", "Вылет, м", "Высота, м", "Ставка/ч", "Строк таблицы"],
                rows=rows, warn=warn)


@blueprint.route("/docs")
def docs():
    return page("Документация модуля",
                "Комплект ТЗ, акты испытаний и документация платформы — в docs/LiftPortal портала, "
                "полный хаб — в репозитории проекта (index.html).")
