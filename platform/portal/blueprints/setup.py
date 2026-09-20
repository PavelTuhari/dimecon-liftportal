"""Запуск компании: пять настроек, без которых платформа работает на демо-данных.

Грузовые таблицы, прайс, реквизиты и почта, доступы к ERP, собственный домен.
Каждая страница не только хранит значения, но и применяет их: подбор начинает считать
по паспорту, счёт печатается с реквизитами, письма уходят с вашего адреса.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from flask import Blueprint, Response, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func

from ..auth import owner_required, staff_required
from ..db import SessionLocal as db, first_or_404
from ..mailer import send_mail, test_smtp
from ..models import AuditLog, Domain, Equipment, LoadChart, Media, Tenant
from ..services import domains as dom, loadcharts as lc, setup_state
from ..services.pricing import DEFAULT_PRICING, pricing_from_form, pricing_of, pricing_problems
from ..storage import save_upload

bp = Blueprint("setup", __name__)
PREVIEW_KEY = "lc_preview"


def T() -> Tenant:
    return g.tenant


def log(action, entity="", entity_id=None, **details):
    db.add(AuditLog(tenant_id=T().id, user_id=g.user.id, action=action, entity=entity,
                    entity_id=entity_id, details=details))


def _num(name, default=0.0):
    raw = (request.form.get(name) or "").replace(",", ".").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


# ------------------------------------------------------------------ сводка

@bp.route("/setup")
@staff_required
def index(tenant_slug):
    return render_template("setup/index.html", state=setup_state.progress(T()),
                           levels=setup_state.LEVELS)


# ------------------------------------------------------------------ 1. грузовые таблицы

@bp.route("/setup/load-charts", methods=["GET", "POST"])
@staff_required
def load_charts(tenant_slug):
    tnt = T()
    preview = None
    if request.method == "POST":
        action = request.form.get("action", "preview")
        try:
            if action in ("preview", "import"):
                preview = _charts_from_file(action == "import")
            elif action == "manual":
                eq = first_or_404(db.query(Equipment).filter_by(
                    id=request.form.get("equipment_id", type=int), tenant_id=tnt.id))
                db.add(LoadChart(equipment_id=eq.id, configuration=request.form.get("configuration", "main")[:80],
                                 radius_m=_num("radius_m"), capacity_t=_num("capacity_t"),
                                 height_m=_num("height_m"), boom_m=_num("boom_m"),
                                 counterweight_t=_num("counterweight_t"), source="passport",
                                 updated_at=datetime.utcnow()))
                db.commit()
                flash(f"Строка добавлена в паспортную таблицу {eq.brand} {eq.model}", "success")
            elif action == "drop_approx":
                eq = first_or_404(db.query(Equipment).filter_by(
                    id=request.form.get("equipment_id", type=int), tenant_id=tnt.id))
                rows = db.query(LoadChart).filter_by(equipment_id=eq.id).all()
                approx = [r for r in rows if (r.source or "manual") != "passport"]
                for r in approx:
                    db.delete(r)
                db.commit()
                flash(f"Удалено ориентировочных строк: {len(approx)}", "success")
            elif action == "clear":
                eq = first_or_404(db.query(Equipment).filter_by(
                    id=request.form.get("equipment_id", type=int), tenant_id=tnt.id))
                n = db.query(LoadChart).filter_by(equipment_id=eq.id).delete()
                db.commit()
                flash(f"Таблица {eq.model} очищена ({n} строк)", "warning")
        except Exception as exc:  # noqa: BLE001 — показываем причину прямо на странице
            flash(f"Не выполнено: {exc}", "danger")
        if action != "preview":
            return redirect(url_for("setup.load_charts"))

    return render_template("setup/load_charts.html", rows=lc.coverage(tnt), summary=lc.summary(tnt),
                           preview=preview, fields=lc.COLUMNS.keys(),
                           fleet=db.query(Equipment).filter_by(tenant_id=tnt.id).all())


def _charts_from_file(apply_now: bool):
    """Разбор загруженного файла: сначала показываем, что распознали, и только потом пишем."""
    up = request.files.get("file")
    if not up or not up.filename:
        raise ValueError("выберите файл с грузовой таблицей (CSV или XLSX)")
    data = up.read()
    headers, rows = lc.read_table(data, up.filename)
    if not headers:
        raise ValueError("файл пуст или не распознан")
    mapping = {}
    for idx in range(len(headers)):
        chosen = request.form.get(f"col{idx}")
        if chosen:
            mapping[idx] = chosen
    if not mapping:
        mapping = lc.detect_mapping(headers)

    default_eq = None
    eq_id = request.form.get("equipment_id", type=int)
    if eq_id:
        default_eq = first_or_404(db.query(Equipment).filter_by(id=eq_id, tenant_id=T().id))

    parsed, report = lc.parse(T(), headers, rows, mapping, default_equipment=default_eq)
    problems = lc.validate(parsed)
    result = {"headers": headers, "mapping": mapping, "report": report, "problems": problems,
              "sample": parsed[:12], "count": len(parsed), "filename": up.filename}
    if apply_now:
        if not parsed:
            raise ValueError("в файле не нашлось ни одной строки с вылетом и нагрузкой")
        media_id = None
        if request.form.get("keep_file") == "1":
            up.stream.seek(0)
            media = save_upload(T(), up)
            media.note = f"Грузовая таблица, загружена {date.today():%d.%m.%Y}"[:255]
            media.tags = "паспорт, грузовая таблица"
            db.commit()
            media_id = media.id
        applied = lc.apply(T(), parsed, replace=request.form.get("replace") != "0", doc_media_id=media_id)
        log("loadcharts.import", details={"file": up.filename, "rows": applied.imported,
                                          "machines": list(applied.machines)})
        db.commit()
        flash(f"Загрузка выполнена: {applied.line()}", "success")
        result["applied"] = applied
    return result


@bp.route("/setup/load-charts/template.csv")
@staff_required
def load_charts_template(tenant_slug):
    return Response(lc.template_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="load-chart-template.csv"'})


# ------------------------------------------------------------------ 2. прайс

@bp.route("/setup/pricing", methods=["GET", "POST"])
@owner_required
def pricing(tenant_slug):
    tnt = T()
    if request.method == "POST":
        action = request.form.get("action", "form")
        if action == "json":
            try:
                tnt.pricing = json.loads(request.form["pricing_json"])
                log("tenant.pricing", details={"mode": "json"})
                db.commit()
                flash("Прайс сохранён", "success")
            except ValueError as exc:
                flash(f"Некорректный JSON: {exc}", "danger")
        elif action == "rates":
            changed = 0
            for eq in db.query(Equipment).filter_by(tenant_id=tnt.id).all():
                rate = request.form.get(f"rate_{eq.id}")
                if rate is None:
                    continue
                new_rate = _num(f"rate_{eq.id}", eq.hourly_rate or 0)
                new_min = _num(f"min_{eq.id}", eq.min_hours or 0)
                new_mob = _num(f"mob_{eq.id}", eq.mobilization_fee or 0)
                new_month = _num(f"month_{eq.id}", (eq.spec or {}).get("monthly_rate", 0))
                if (new_rate, new_min, new_mob) != (eq.hourly_rate, eq.min_hours, eq.mobilization_fee):
                    changed += 1
                eq.hourly_rate, eq.min_hours, eq.mobilization_fee = new_rate, new_min, new_mob
                if new_month:
                    spec = dict(eq.spec or {})
                    spec["monthly_rate"] = new_month
                    eq.spec = spec
            log("pricing.rates", details={"changed": changed})
            db.commit()
            flash(f"Ставки обновлены: изменено машин {changed}", "success")
        else:
            tnt.pricing = pricing_from_form(request.form, tnt.pricing)
            log("tenant.pricing", details={"mode": "form"})
            db.commit()
            flash("Коэффициенты, зоны и допуслуги сохранены", "success")
        return redirect(url_for("setup.pricing"))

    return render_template("setup/pricing.html", pricing=pricing_of(tnt), defaults=DEFAULT_PRICING,
                           problems=pricing_problems(tnt), custom=bool(tnt.pricing),
                           fleet=db.query(Equipment).filter_by(tenant_id=tnt.id)
                           .order_by(Equipment.capacity_t.desc()).all(),
                           pricing_json=json.dumps(pricing_of(tnt), ensure_ascii=False, indent=2))


# ------------------------------------------------------------------ 3. реквизиты и почта

@bp.route("/setup/company", methods=["GET", "POST"])
@owner_required
def company(tenant_slug):
    tnt = T()
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            f = request.form
            for field in ("legal_name", "idno", "vat_code", "bank_name", "bank_iban", "bank_swift",
                          "legal_address", "director_name", "accountant_name"):
                setattr(tnt, field, f.get(field, "").strip()[:255])
            tnt.invoice_due_days = f.get("invoice_due_days", type=int) or 10
            tnt.vat_rate = _num("vat_rate", tnt.vat_rate or 20)
            tnt.doc_prefixes = {"invoice": f.get("prefix_invoice", "СЧ")[:8],
                                "act": f.get("prefix_act", "АКТ")[:8],
                                "quote": f.get("prefix_quote", "КП")[:8]}
            log("tenant.requisites")
            db.commit()
            flash("Реквизиты сохранены — счета и акты будут печататься с ними", "success")
        elif action == "smtp":
            f = request.form
            smtp = dict(tnt.smtp or {})
            smtp.update({"host": f.get("host", "").strip(), "port": f.get("port", type=int) or 587,
                         "user": f.get("user", "").strip(), "tls": f.get("tls") == "1",
                         "from_email": f.get("from_email", "").strip(),
                         "from_name": f.get("from_name", "").strip() or tnt.name})
            if f.get("password"):
                smtp["password"] = f["password"]
            tnt.smtp = smtp
            log("tenant.smtp", details={"host": smtp.get("host")})
            db.commit()
            flash("Почтовый сервер сохранён", "success")
        elif action == "smtp_test":
            to = (tnt.smtp or {}).get("from_email") or tnt.email
            if not to:
                flash("Укажите адрес отправителя — на него уйдёт проверочное письмо", "danger")
            else:
                ok, message = test_smtp(tnt, to)
                flash(message, "success" if ok else "danger")
        elif action == "mail_test":
            to = request.form.get("to", "").strip()
            if not to:
                flash("Укажите адрес для проверки", "danger")
            else:
                rec = send_mail(tnt, to, f"Проверка почты {tnt.name}",
                                f"Это проверочное письмо из кабинета {tnt.name}.\n"
                                f"Если оно пришло — счета и уведомления клиентам тоже дойдут.")
                flash(f"Письмо на {to}: статус «{rec.status}», транспорт «{rec.transport}»",
                      "success" if rec.status == "sent" else "warning")
        return redirect(url_for("setup.company"))

    return render_template("setup/company.html", smtp=tnt.smtp or {},
                           prefixes=tnt.doc_prefixes or {"invoice": "СЧ", "act": "АКТ", "quote": "КП"},
                           state=setup_state.checklist(T())[2])


# ------------------------------------------------------------------ 5. домен

@bp.route("/setup/domain", methods=["GET", "POST"])
@owner_required
def domain(tenant_slug):
    tnt = T()
    platform_host = g.get("platform_host") if hasattr(g, "get") else None
    platform_host = platform_host or request.host
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            host = dom.normalize(request.form.get("host", ""))
            problem = dom.validate(host)
            exists = db.query(Domain).filter_by(host=host).first() if host else None
            if problem:
                flash(problem, "danger")
            elif exists:
                flash("Такой домен уже добавлен", "warning")
            else:
                d = Domain(tenant_id=tnt.id, host=host,
                           is_primary=not db.query(Domain).filter_by(tenant_id=tnt.id).count())
                db.add(d)
                db.commit()
                log("domain.added", "domain", d.id, host=host)
                db.commit()
                flash(f"Домен {host} добавлен. Пропишите записи DNS и нажмите «Проверить».", "success")
        elif action == "check":
            d = first_or_404(db.query(Domain).filter_by(id=request.form.get("id", type=int), tenant_id=tnt.id))
            dom.check(tnt, d, platform_host)
            flash(f"{d.host}: {d.check_note}", "success" if d.verified else "warning")
        elif action == "primary":
            d = first_or_404(db.query(Domain).filter_by(id=request.form.get("id", type=int), tenant_id=tnt.id))
            dom.set_primary(tnt, d)
            flash(f"{d.host} — основной адрес компании", "success")
        elif action == "delete":
            d = first_or_404(db.query(Domain).filter_by(id=request.form.get("id", type=int), tenant_id=tnt.id))
            if tnt.custom_domain == d.host:
                tnt.custom_domain = ""
            db.delete(d)
            db.commit()
            flash("Домен удалён", "warning")
        return redirect(url_for("setup.domain"))

    rows = db.query(Domain).filter_by(tenant_id=tnt.id).order_by(Domain.created_at).all()
    sample = rows[0].host if rows else f"{tnt.slug}.md"
    return render_template("setup/domain.html", rows=rows, platform_host=platform_host,
                           instructions=dom.instructions(tnt, sample, platform_host),
                           platform_ips=dom.platform_ips(platform_host))
