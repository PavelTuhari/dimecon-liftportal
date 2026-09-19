"""Управленческие модули кабинета: проекты, продажи, закупки, счета, таблицы, документы."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth import staff_required
from ..db import SessionLocal as db, first_or_404
from ..models import (AuditLog, Contact, DocFolder, DocRequest, DocRule, Document, Equipment, Media,
                      Partner, Payment, Product, Project, PurchaseAgreement, PurchaseLine, PurchaseOrder,
                      RecurringPlan, ReorderRule, SalesLine, SalesOrder, SalesTemplate, Service, Sheet,
                      Task, Timesheet, User, Vendor)
from ..services import docs_ws, invoicing, projects as prj, purchase as pur, sales as sls, sheets as sh
from ..storage import save_upload

bp = Blueprint("erp", __name__)


def T():
    return g.tenant


def log(action, entity="", entity_id=None, **details):
    db.add(AuditLog(tenant_id=T().id, user_id=g.user.id, action=action, entity=entity,
                    entity_id=entity_id, details=details))


def _f(name, default=0.0, cast=float):
    raw = (request.form.get(name) or "").replace(",", ".").strip()
    try:
        return cast(raw) if raw else default
    except (TypeError, ValueError):
        return default


def _d(name):
    raw = (request.form.get(name) or "").strip()
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _own(model, oid):
    return first_or_404(db.query(model).filter_by(id=oid, tenant_id=T().id))


def staff():
    return db.query(User).join(User.memberships).filter_by(tenant_id=T().id).all()


# ================================================================== ПРОЕКТЫ

@bp.route("/projects")
@staff_required
def projects(tenant_slug):
    board = prj.dashboard(T())
    templates = db.query(Project).filter_by(tenant_id=T().id, is_template=True).all()
    return render_template("erp/projects.html", board=board, templates=templates,
                           stages=prj.PROJECT_STAGES)


@bp.route("/projects/new", methods=["GET", "POST"])
@staff_required
def project_new(tenant_slug):
    if request.method == "POST":
        f = request.form
        tpl_id = f.get("template_id", type=int)
        if tpl_id:
            template = _own(Project, tpl_id)
            p = prj.from_template(T(), template, name=f["name"].strip(),
                                  partner_id=f.get("partner_id", type=int),
                                  contact_id=f.get("contact_id", type=int), starts_at=_d("starts_at"))
        else:
            p = Project(tenant_id=T().id, name=f["name"].strip(), code=f.get("code", "")[:24],
                        partner_id=f.get("partner_id", type=int), contact_id=f.get("contact_id", type=int),
                        manager_id=f.get("manager_id", type=int), address=f.get("address", ""),
                        budget_amount=_f("budget_amount"), planned_cost=_f("planned_cost"),
                        hour_cost=_f("hour_cost"), hour_rate=_f("hour_rate"),
                        starts_at=_d("starts_at"), ends_at=_d("ends_at"), notes=f.get("notes", ""),
                        is_template=f.get("is_template") == "1", stage="planning")
            db.add(p)
            db.commit()
        log("project.created", "project", p.id, name=p.name)
        db.commit()
        flash(f"Объект «{p.name}» создан", "success")
        return redirect(url_for("erp.project", pid=p.id))
    return render_template("erp/project_edit.html", p=None,
                           partners=db.query(Partner).filter_by(tenant_id=T().id).all(),
                           contacts=db.query(Contact).filter_by(tenant_id=T().id).limit(200).all(),
                           templates=db.query(Project).filter_by(tenant_id=T().id, is_template=True).all(),
                           users=staff())


@bp.route("/projects/<int:pid>", methods=["GET", "POST"])
@staff_required
def project(tenant_slug, pid):
    p = _own(Project, pid)
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            f = request.form
            for field in ("name", "address", "notes", "code"):
                if field in f:
                    setattr(p, field, f.get(field, ""))
            p.stage = f.get("stage", p.stage)
            p.status = f.get("status", p.status)
            p.budget_amount, p.planned_cost = _f("budget_amount"), _f("planned_cost")
            p.hour_cost, p.hour_rate = _f("hour_cost"), _f("hour_rate")
            p.starts_at, p.ends_at = _d("starts_at") or p.starts_at, _d("ends_at")
            p.manager_id = request.form.get("manager_id", type=int)
            db.commit()
            flash("Сохранено", "success")
        elif action == "task":
            task = prj.create_task(T(), p, title=request.form["title"].strip(),
                                   description=request.form.get("description", ""),
                                   assignee_id=request.form.get("assignee_id", type=int),
                                   parent_id=request.form.get("parent_id", type=int),
                                   depends_on_id=request.form.get("depends_on_id", type=int),
                                   priority=request.form.get("priority", type=int) or 0,
                                   planned_hours=_f("planned_hours"),
                                   starts_on=_d("starts_on"), due_on=_d("due_on"),
                                   is_milestone=request.form.get("is_milestone") == "1",
                                   milestone_amount=_f("milestone_amount"),
                                   tags=request.form.get("tags", "")[:200])
            every = request.form.get("recur_every", type=int)
            if every:
                task.recurrence = {"every": every, "unit": request.form.get("recur_unit", "week")}
            db.commit()
            flash(f"Задача «{task.title}» добавлена", "success")
        elif action == "time":
            prj.log_time(T(), p, hours=_f("hours"), user_id=g.user.id,
                         task_id=request.form.get("task_id", type=int),
                         work_date=_d("work_date"), note=request.form.get("note", "")[:255],
                         billable=request.form.get("billable") == "1")
            flash("Часы записаны", "success")
        elif action == "invoice_time":
            doc = invoicing.from_timesheets(T(), p)
            flash(f"Счёт {doc.number} на {doc.amount:,.2f} по отработанным часам".replace(",", " ")
                  if doc else "Неоплаченных часов со ставкой нет", "success" if doc else "warning")
        elif action == "template":
            p.is_template = True
            db.commit()
            flash("Объект сохранён как шаблон", "success")
        return redirect(url_for("erp.project", pid=p.id))

    return render_template("erp/project.html", p=p, tree=prj.task_tree(T(), p),
                           money=prj.profitability(T(), p), progress=prj.progress(T(), p),
                           milestones=prj.milestones(T(), p), times=timesheets_of(p),
                           totals=prj.timesheet_totals(p), timeline=prj.timeline(T(), p),
                           shifts=prj.shifts_of_project(T(), p), users=staff(),
                           stages=prj.STAGES, stage_names=prj.STAGE_NAMES,
                           project_stages=prj.PROJECT_STAGES,
                           sales=db.query(SalesOrder).filter_by(tenant_id=T().id, project_id=p.id).all(),
                           purchases=db.query(PurchaseOrder).filter_by(tenant_id=T().id, project_id=p.id).all(),
                           docs=db.query(Document).filter_by(tenant_id=T().id, project_id=p.id).all())


def timesheets_of(p: Project):
    return (db.query(Timesheet).filter_by(project_id=p.id)
            .order_by(Timesheet.work_date.desc()).limit(60).all())


@bp.route("/tasks/<int:tid>/stage", methods=["POST"])
@staff_required
def task_stage(tenant_slug, tid):
    task = _own(Task, tid)
    res = prj.move_task(task, request.form.get("stage", "todo"))
    if not res["ok"]:
        flash(res["reason"], "danger")
    elif res.get("spawned"):
        flash(f"Создана следующая повторяющаяся задача на {res['spawned'].due_on:%d.%m.%Y}", "success")
    if request.headers.get("X-Requested-With") == "fetch":
        return {"ok": res["ok"], "stage": task.stage}
    return redirect(request.referrer or url_for("erp.project", pid=task.project_id))


@bp.route("/tasks/<int:tid>/milestone/invoice", methods=["POST"])
@staff_required
def milestone_invoice(tenant_slug, tid):
    task = _own(Task, tid)
    if not task.is_milestone or not task.milestone_amount:
        flash("У этапа не задана сумма", "danger")
    else:
        doc = invoicing.from_milestone(T(), task)
        log("invoice.milestone", "document", doc.id, task=task.title)
        db.commit()
        flash(f"Счёт {doc.number} по этапу «{task.title}» выставлен", "success")
    return redirect(url_for("erp.project", pid=task.project_id))


@bp.route("/tasks")
@staff_required
def tasks_board(tenant_slug):
    """Канбан задач по всем объектам."""
    q = db.query(Task).filter_by(tenant_id=T().id)
    if request.args.get("assignee", type=int):
        q = q.filter(Task.assignee_id == request.args.get("assignee", type=int))
    rows = q.order_by(Task.priority.desc(), Task.due_on.is_(None), Task.due_on).all()
    by_stage = {s: [t for t in rows if t.stage == s] for s, _ in prj.STAGES}
    names = {p.id: p.name for p in db.query(Project).filter_by(tenant_id=T().id).all()}
    return render_template("erp/tasks.html", by_stage=by_stage, stages=prj.STAGES, names=names,
                           users=staff(), today=date.today())


# ================================================================== ПРОДАЖИ

@bp.route("/sales")
@staff_required
def sales(tenant_slug):
    q = db.query(SalesOrder).filter_by(tenant_id=T().id)
    status = request.args.get("status", "")
    if status:
        q = q.filter(SalesOrder.status == status)
    rows = q.order_by(SalesOrder.created_at.desc()).limit(300).all()
    return render_template("erp/sales.html", rows=rows, stats=sls.stats(T()), status=status,
                           statuses=sls.STATUSES, names=sls.STATUS_NAMES, expiring=sls.expiring(T()),
                           templates=db.query(SalesTemplate).filter_by(tenant_id=T().id, is_active=True).all(),
                           contacts={c.id: c for c in db.query(Contact).filter_by(tenant_id=T().id).all()},
                           partners={p.id: p for p in db.query(Partner).filter_by(tenant_id=T().id).all()})


@bp.route("/sales/new", methods=["POST"])
@staff_required
def sales_new(tenant_slug):
    tpl_id = request.form.get("template_id", type=int)
    template = db.query(SalesTemplate).filter_by(id=tpl_id, tenant_id=T().id).first() if tpl_id else None
    so = sls.create(T(), contact_id=request.form.get("contact_id", type=int),
                    partner_id=request.form.get("partner_id", type=int),
                    project_id=request.form.get("project_id", type=int),
                    assignee_id=g.user.id, template=template)
    log("sales.created", "sales_order", so.id, number=so.number)
    db.commit()
    return redirect(url_for("erp.sale", sid=so.id))


@bp.route("/sales/<int:sid>", methods=["GET", "POST"])
@staff_required
def sale(tenant_slug, sid):
    so = _own(SalesOrder, sid)
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            so.note = request.form.get("note", "")
            so.terms = request.form.get("terms", "")
            so.discount_pct = _f("discount_pct")
            so.vat_pct = _f("vat_pct", 20)
            so.valid_until = _d("valid_until")
            so.contact_id = request.form.get("contact_id", type=int)
            so.partner_id = request.form.get("partner_id", type=int)
            so.project_id = request.form.get("project_id", type=int)
            sls.recalc(so)
            db.commit()
            flash("Сохранено", "success")
        elif action == "line":
            kind = request.form.get("kind", "text")
            if kind in ("equipment", "service", "product") and request.form.get("ref_id", type=int):
                sls.add_from_catalog(so, kind, request.form.get("ref_id", type=int), _f("qty", 1))
            else:
                sls.add_line(so, name=request.form.get("name", "").strip() or "Позиция",
                             qty=_f("qty", 1), price=_f("price"), cost=_f("cost"),
                             unit=request.form.get("unit", "шт"),
                             discount_pct=_f("line_discount"),
                             is_optional=request.form.get("optional") == "1")
            sls.recalc(so)
            db.commit()
        elif action == "line_delete":
            line = db.query(SalesLine).filter_by(id=request.form.get("line_id", type=int), so_id=so.id).first()
            if line:
                db.delete(line)
                db.flush()
                sls.recalc(so)
                db.commit()
        elif action == "send":
            sls.send(so)
            contact = db.get(Contact, so.contact_id) if so.contact_id else None
            if contact and contact.email:
                from ..mailer import send_mail
                link = url_for("site.sales_accept", token=so.accept_token, _external=True)
                send_mail(T(), contact.email, f"Коммерческое предложение {so.number}",
                          f"Здравствуйте!\n\nПредложение {so.number} на сумму {so.amount_total:,.2f} "
                          f"{so.currency} готово.\nПосмотреть и принять: {link}\n\n{T().name}".replace(",", " "))
                flash(f"Предложение отправлено на {contact.email}", "success")
            else:
                flash("Статус «отправлено». Ссылка для клиента — в карточке", "success")
        elif action == "confirm":
            sls.confirm(so, create_project=request.form.get("create_project") == "1")
            flash("Предложение подтверждено", "success")
        elif action == "cancel":
            sls.cancel(so, request.form.get("reason", ""))
            flash("Предложение отменено", "warning")
        elif action == "invoice":
            doc = invoicing.from_sales(T(), so, advance_pct=_f("advance_pct"))
            log("invoice.sales", "document", doc.id, sales=so.number)
            db.commit()
            flash(f"Счёт {doc.number} на {doc.amount:,.2f} {doc.currency}".replace(",", " "), "success")
        elif action == "template":
            tpl = sls.save_as_template(so, request.form.get("template_name", so.number))
            flash(f"Шаблон «{tpl.name}» сохранён", "success")
        return redirect(url_for("erp.sale", sid=so.id))

    return render_template(
        "erp/sale.html", so=so, margin=sls.margin(so), names=sls.STATUS_NAMES,
        contacts=db.query(Contact).filter_by(tenant_id=T().id).limit(300).all(),
        partners=db.query(Partner).filter_by(tenant_id=T().id).all(),
        projects=db.query(Project).filter_by(tenant_id=T().id, is_template=False).all(),
        equipment=db.query(Equipment).filter_by(tenant_id=T().id, is_published=True).all(),
        services=db.query(Service).filter_by(tenant_id=T().id).all(),
        products=db.query(Product).filter_by(tenant_id=T().id).all(),
        docs=db.query(Document).filter_by(tenant_id=T().id, sales_id=so.id).all(),
        accept_url=url_for("site.sales_accept", token=so.accept_token, _external=True))


@bp.route("/sales/<int:sid>/pdf")
@staff_required
def sale_pdf(tenant_slug, sid):
    so = _own(SalesOrder, sid)
    from ..services.documents import sales_pdf
    pdf = sales_pdf(T(), so)
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{so.number}.pdf"'})


# ================================================================== ЗАКУПКИ

@bp.route("/purchase")
@staff_required
def purchase(tenant_slug):
    q = db.query(PurchaseOrder).filter_by(tenant_id=T().id)
    status = request.args.get("status", "")
    if status:
        q = q.filter(PurchaseOrder.status == status)
    rows = q.order_by(PurchaseOrder.created_at.desc()).limit(300).all()
    return render_template("erp/purchase.html", rows=rows, summary=pur.summary(T()), status=status,
                           statuses=pur.STATUSES, names=pur.STATUS_NAMES, to_pay=pur.to_pay(T()),
                           vendors={v.id: v for v in db.query(Vendor).filter_by(tenant_id=T().id).all()},
                           projects={p.id: p for p in db.query(Project).filter_by(tenant_id=T().id).all()})


@bp.route("/purchase/new", methods=["POST"])
@staff_required
def purchase_new(tenant_slug):
    po = pur.create(T(), vendor_id=request.form.get("vendor_id", type=int),
                    project_id=request.form.get("project_id", type=int),
                    agreement_id=request.form.get("agreement_id", type=int),
                    note=request.form.get("note", ""), created_by=g.user.id)
    log("purchase.created", "purchase_order", po.id, number=po.number)
    db.commit()
    return redirect(url_for("erp.purchase_order", poid=po.id))


@bp.route("/purchase/<int:poid>", methods=["GET", "POST"])
@staff_required
def purchase_order(tenant_slug, poid):
    po = _own(PurchaseOrder, poid)
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            po.note = request.form.get("note", "")
            po.vendor_id = request.form.get("vendor_id", type=int)
            po.project_id = request.form.get("project_id", type=int)
            po.agreement_id = request.form.get("agreement_id", type=int)
            po.vat_pct = _f("vat_pct", 20)
            po.expected_on = _d("expected_on")
            pur.recalc(po)
            db.commit()
            flash("Сохранено", "success")
        elif action == "line":
            pur.add_line(po, name=request.form.get("name", "").strip() or "Позиция", qty=_f("qty", 1),
                         price=_f("price"), unit=request.form.get("unit", "шт"),
                         product_id=request.form.get("product_id", type=int))
            db.commit()
        elif action == "line_delete":
            line = db.query(PurchaseLine).filter_by(id=request.form.get("line_id", type=int), po_id=po.id).first()
            if line:
                db.delete(line)
                db.flush()
                pur.recalc(po)
                db.commit()
        elif action == "send":
            pur.send(po)
            vendor = db.get(Vendor, po.vendor_id) if po.vendor_id else None
            if vendor and vendor.email:
                from ..mailer import send_mail
                lines = "\n".join(f"  {l.name} — {l.qty:g} {l.unit} × {l.price:,.2f}".replace(",", " ")
                                  for l in po.lines)
                send_mail(T(), vendor.email, f"Запрос цены {po.number}",
                          f"Здравствуйте!\n\nПросим предложить цену и срок поставки:\n{lines}\n\n{T().name}")
                flash(f"Запрос отправлен на {vendor.email}", "success")
            else:
                flash("Статус «отправлен»", "success")
        elif action == "confirm":
            pur.confirm(po)
            flash("Заказ подтверждён поставщиком", "success")
        elif action == "receive":
            qty = {int(k.split("_")[1]): float(v.replace(",", "."))
                   for k, v in request.form.items() if k.startswith("recv_") and v.strip()}
            res = pur.receive(po, qty or None)
            flash("Принято полностью" if res["full"] else f"Принято строк: {res['lines']}", "success")
        elif action == "bill":
            pur.bill(po, amount=_f("bill_amount", po.amount_total), due_on=_d("bill_due_on"))
            flash("Счёт поставщика проведён", "success")
        elif action == "pay":
            pur.pay(po, amount=_f("amount"), on=_d("paid_on"), method=request.form.get("method", "bank"),
                    reference=request.form.get("reference", ""), user_id=g.user.id)
            flash("Оплата записана", "success")
        return redirect(url_for("erp.purchase_order", poid=po.id))

    return render_template("erp/purchase_order.html", po=po, names=pur.STATUS_NAMES,
                           vendors=db.query(Vendor).filter_by(tenant_id=T().id).all(),
                           projects=db.query(Project).filter_by(tenant_id=T().id, is_template=False).all(),
                           agreements=db.query(PurchaseAgreement).filter_by(tenant_id=T().id).all(),
                           products=db.query(Product).filter_by(tenant_id=T().id).all(),
                           paid=pur.paid_amount(po),
                           payments=db.query(Payment).filter_by(purchase_id=po.id).all())


@bp.route("/vendors", methods=["GET", "POST"])
@staff_required
def vendors(tenant_slug):
    if request.method == "POST":
        vid = request.form.get("id", type=int)
        v = _own(Vendor, vid) if vid else Vendor(tenant_id=T().id)
        v.name = request.form["name"].strip()
        v.idno = request.form.get("idno", "")
        v.contact_name = request.form.get("contact_name", "")
        v.phone = request.form.get("phone", "")
        v.email = request.form.get("email", "").strip().lower()
        v.payment_days = request.form.get("payment_days", type=int) or 14
        v.lead_days = request.form.get("lead_days", type=int) or 3
        v.status = request.form.get("status", "active")
        v.notes = request.form.get("notes", "")
        db.add(v)
        db.commit()
        flash("Поставщик сохранён", "success")
        return redirect(url_for("erp.vendors"))
    return render_template("erp/vendors.html", stats=pur.vendor_stats(T()),
                           agreements=db.query(PurchaseAgreement).filter_by(tenant_id=T().id).all(),
                           vendors=db.query(Vendor).filter_by(tenant_id=T().id).order_by(Vendor.name).all())


@bp.route("/vendors/agreement", methods=["POST"])
@staff_required
def vendor_agreement(tenant_slug):
    a = PurchaseAgreement(tenant_id=T().id, vendor_id=request.form.get("vendor_id", type=int),
                          name=request.form["name"].strip(), kind=request.form.get("kind", "blanket"),
                          valid_from=_d("valid_from"), valid_to=_d("valid_to"),
                          terms={"discount_pct": _f("discount_pct"),
                                 "payment_days": request.form.get("payment_days", type=int) or 14})
    db.add(a)
    db.commit()
    flash(f"Соглашение «{a.name}» добавлено", "success")
    return redirect(url_for("erp.vendors"))


@bp.route("/purchase/reorder", methods=["GET", "POST"])
@staff_required
def reorder(tenant_slug):
    if request.method == "POST":
        action = request.form.get("action", "run")
        if action == "rule":
            rule = ReorderRule(tenant_id=T().id, product_id=request.form.get("product_id", type=int),
                               vendor_id=request.form.get("vendor_id", type=int),
                               min_qty=_f("min_qty"), max_qty=_f("max_qty"))
            db.add(rule)
            db.commit()
            flash("Правило пополнения добавлено", "success")
        elif action == "run":
            rows = pur.check_reorder(T(), create_rfq=True, user_id=g.user.id)
            created = len({r["po"].id for r in rows if r.get("po")})
            flash(f"Проверено правил: {len(rows)}; создано запросов цен: {created}"
                  if rows else "Все остатки выше минимума", "success")
        return redirect(url_for("erp.reorder"))
    rules = db.query(ReorderRule).filter_by(tenant_id=T().id).all()
    products = {p.id: p for p in db.query(Product).filter_by(tenant_id=T().id).all()}
    return render_template("erp/reorder.html", rules=rules, products=products,
                           preview=pur.check_reorder(T(), create_rfq=False),
                           vendors=db.query(Vendor).filter_by(tenant_id=T().id).all())


# ================================================================== СЧЕТА

@bp.route("/invoices")
@staff_required
def invoices(tenant_slug):
    q = db.query(Document).filter(Document.tenant_id == T().id,
                                  Document.type.in_(("invoice", "credit_note")))
    status = request.args.get("status", "")
    if status == "overdue":
        q = q.filter(Document.due_at < date.today(), Document.status.in_(("issued", "partial", "overdue")))
    elif status:
        q = q.filter(Document.status == status)
    rows = q.order_by(Document.issued_at.desc(), Document.id.desc()).limit(300).all()
    balances = {d.id: invoicing.balance(d) for d in rows}
    return render_template("erp/invoices.html", rows=rows, balances=balances, status=status,
                           summary=invoicing.summary(T()), aging=invoicing.aging(T()),
                           names=invoicing.STATUS_NAMES, type_names=invoicing.TYPE_NAMES,
                           contacts={c.id: c for c in db.query(Contact).filter_by(tenant_id=T().id).all()},
                           partners={p.id: p for p in db.query(Partner).filter_by(tenant_id=T().id).all()})


@bp.route("/invoices/<int:did>", methods=["GET", "POST"])
@staff_required
def invoice(tenant_slug, did):
    doc = _own(Document, did)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "pay":
            invoicing.register_payment(T(), doc, amount=_f("amount"), on=_d("paid_on"),
                                       method=request.form.get("method", "bank"),
                                       reference=request.form.get("reference", ""), user_id=g.user.id)
            flash("Оплата записана", "success")
        elif action == "credit":
            note = invoicing.credit_note(T(), doc, amount=_f("amount") or None,
                                         reason=request.form.get("reason", ""))
            flash(f"Кредит-нота {note.number} создана", "success")
        elif action == "remind":
            sent = invoicing.send_reminders(T(), min_days=0)
            flash(f"Напоминаний отправлено: {len(sent)}", "success" if sent else "warning")
        elif action == "cancel":
            doc.status = "cancelled"
            db.commit()
            flash("Счёт отменён", "warning")
        return redirect(url_for("erp.invoice", did=doc.id))
    return render_template("erp/invoice.html", doc=doc, paid=invoicing.paid_amount(doc),
                           balance=invoicing.balance(doc), names=invoicing.STATUS_NAMES,
                           type_names=invoicing.TYPE_NAMES,
                           payments=db.query(Payment).filter_by(document_id=doc.id)
                           .order_by(Payment.paid_on).all())


@bp.route("/invoices/actions", methods=["POST"])
@staff_required
def invoice_actions(tenant_slug):
    action = request.form.get("action")
    if action == "refresh":
        counts = invoicing.refresh_all(T())
        flash("Статусы пересчитаны: " + ", ".join(f"{invoicing.STATUS_NAMES.get(k, k)} — {v}"
                                                  for k, v in counts.items()), "success")
    elif action == "remind":
        sent = invoicing.send_reminders(T())
        flash(f"Напоминаний отправлено: {len(sent)}" if sent else "Просроченных счетов нет",
              "success" if sent else "warning")
    elif action == "run_plans":
        docs = invoicing.run_recurring(T())
        flash(f"Выставлено регулярных счетов: {len(docs)}" if docs else "Сегодня регулярных счетов нет",
              "success" if docs else "warning")
    return redirect(request.referrer or url_for("erp.invoices"))


@bp.route("/plans", methods=["GET", "POST"])
@staff_required
def plans(tenant_slug):
    if request.method == "POST":
        pid = request.form.get("id", type=int)
        plan = _own(RecurringPlan, pid) if pid else RecurringPlan(tenant_id=T().id)
        plan.name = request.form["name"].strip()
        plan.contact_id = request.form.get("contact_id", type=int)
        plan.partner_id = request.form.get("partner_id", type=int)
        plan.amount = _f("amount")
        plan.period = request.form.get("period", "month")
        plan.day_of_month = request.form.get("day_of_month", type=int) or 1
        plan.payment_days = request.form.get("payment_days", type=int) or 10
        plan.is_active = request.form.get("is_active") == "1"
        plan.next_run = _d("next_run") or invoicing.plan_next_date(plan)
        db.add(plan)
        db.commit()
        flash("План сохранён", "success")
        return redirect(url_for("erp.plans"))
    return render_template("erp/plans.html",
                           rows=db.query(RecurringPlan).filter_by(tenant_id=T().id).all(),
                           contacts=db.query(Contact).filter_by(tenant_id=T().id).limit(300).all(),
                           partners=db.query(Partner).filter_by(tenant_id=T().id).all())


# ================================================================== ТАБЛИЦЫ

@bp.route("/sheets")
@staff_required
def sheets(tenant_slug):
    rows = db.query(Sheet).filter_by(tenant_id=T().id).order_by(Sheet.updated_at.desc()).all()
    return render_template("erp/sheets.html", rows=rows, templates=sh.TEMPLATES.keys())


@bp.route("/sheets/new", methods=["POST"])
@staff_required
def sheet_new(tenant_slug):
    name = request.form.get("name", "").strip() or "Новая таблица"
    tpl = sh.TEMPLATES.get(request.form.get("template", ""))
    s = Sheet(tenant_id=T().id, name=name[:160], updated_by=g.user.id,
              cells=dict(tpl["cells"]) if tpl else {},
              charts=list(tpl.get("charts", [])) if tpl else [],
              formats=dict(tpl.get("formats", {})) if tpl else {})
    db.add(s)
    db.commit()
    return redirect(url_for("erp.sheet", shid=s.id))


@bp.route("/sheets/<int:shid>", methods=["GET", "POST"])
@staff_required
def sheet(tenant_slug, shid):
    s = _own(Sheet, shid)
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            cells = {}
            for key, value in request.form.items():
                if key.startswith("c_") and str(value).strip():
                    cells[key[2:].upper()] = value.strip()
            s.cells = cells
            s.name = request.form.get("name", s.name)[:160]
            s.rows = request.form.get("rows", type=int) or s.rows
            s.cols = request.form.get("cols", type=int) or s.cols
            s.updated_by = g.user.id
            s.updated_at = datetime.utcnow()
            db.commit()
            flash("Таблица пересчитана", "success")
        elif action == "pivot":
            rows = sh.pivot(T(), request.form.get("source", "orders"),
                            request.form.get("group", "stage"), request.form.get("measure", "count"))
            cells = dict(s.cells or {})
            cells.update(sh.pivot_to_cells(rows, title=request.form.get("title", "Срез"),
                                           at=request.form.get("at", "A1").upper()))
            s.cells = cells
            db.commit()
            flash(f"Срез вставлен: строк {len(rows)}", "success")
        elif action == "chart":
            charts = list(s.charts or [])
            charts.append({"title": request.form.get("title", "Диаграмма"),
                           "kind": request.form.get("kind", "bar"),
                           "labels": request.form.get("labels", "").upper(),
                           "values": request.form.get("values", "").upper()})
            s.charts = charts
            db.commit()
        elif action == "rule":
            formats = dict(s.formats or {})
            rules = list(formats.get("rules", []))
            rules.append({"range": request.form.get("range", "").upper(),
                          "op": request.form.get("op", ">"), "value": _f("value"),
                          "class": request.form.get("class", "ok")})
            formats["rules"] = rules
            s.formats = formats
            db.commit()
        elif action == "delete":
            db.delete(s)
            db.commit()
            return redirect(url_for("erp.sheets"))
        return redirect(url_for("erp.sheet", shid=s.id))

    calc = sh.compute(s, T())
    return render_template("erp/sheet.html", s=s, values=calc["values"], errors=calc["errors"],
                           marks=sh.conditional(s, calc["values"]), charts=sh.chart_series(s, calc["values"]),
                           col=sh.num_to_col, sources=sh.PIVOT_SOURCES)


@bp.route("/sheets/<int:shid>.xlsx")
@staff_required
def sheet_xlsx(tenant_slug, shid):
    s = _own(Sheet, shid)
    calc = sh.compute(s, T())
    data = sh.to_xlsx(s, calc["values"])
    name = (s.name or "sheet").replace('"', "")
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename*=UTF-8\'\'{name}.xlsx'})


# ================================================================== ДОКУМЕНТЫ

@bp.route("/docs", methods=["GET", "POST"])
@staff_required
def docs(tenant_slug):
    docs_ws.ensure_folders(T())
    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            uploaded = 0
            for fs in request.files.getlist("files"):
                if not fs or not fs.filename:
                    continue
                media = save_upload(T(), fs)
                media.folder_id = request.form.get("folder_id", type=int)
                media.owner_id = g.user.id
                media.note = request.form.get("note", "")[:255]
                media.entity = request.form.get("entity", "")
                media.entity_id = request.form.get("entity_id", type=int)
                media.expires_on = _d("expires_on")
                if request.form.get("tags"):
                    docs_ws.set_tags(media, request.form["tags"])
                db.commit()
                applied = docs_ws.apply_rules(T(), media)
                uploaded += 1
                if applied:
                    flash(f"{media.filename}: сработали правила — {', '.join(applied)}", "success")
            flash(f"Загружено файлов: {uploaded}", "success")
        elif action == "folder":
            f = DocFolder(tenant_id=T().id, name=request.form["name"].strip()[:160],
                          parent_id=request.form.get("parent_id", type=int),
                          access=request.form.get("access", "internal"),
                          sequence=(db.query(func.count(DocFolder.id)).filter_by(tenant_id=T().id).scalar() or 0) * 10 + 10)
            db.add(f)
            db.commit()
            flash(f"Пространство «{f.name}» создано", "success")
        elif action == "request":
            req = docs_ws.request_document(T(), name=request.form["name"].strip(),
                                           to_email=request.form.get("to_email", ""),
                                           to_name=request.form.get("to_name", ""),
                                           folder_id=request.form.get("folder_id", type=int),
                                           due_on=_d("due_on"))
            flash(f"Запрос «{req.name}» создан. Ссылка для загрузки — в списке запросов", "success")
        elif action == "rule":
            rule = DocRule(tenant_id=T().id, name=request.form["name"].strip()[:160],
                           match_tag=request.form.get("match_tag", "")[:80],
                           match_mime=request.form.get("match_mime", "")[:80],
                           action=request.form.get("rule_action", "move"),
                           params={"folder_id": request.form.get("to_folder_id", type=int),
                                   "tags": request.form.get("add_tags", ""),
                                   "title": request.form.get("task_title", ""),
                                   "email": request.form.get("notify_email", "")})
            db.add(rule)
            db.commit()
            flash("Правило добавлено", "success")
        return redirect(url_for("erp.docs", folder=request.form.get("folder_id", "")))

    folder_id = request.args.get("folder", type=int)
    rows = docs_ws.files(T(), folder_id=folder_id, tag=request.args.get("tag", ""),
                         query=request.args.get("q", ""))
    return render_template("erp/docs.html", tree=docs_ws.tree(T()), rows=rows, folder_id=folder_id,
                           tags=docs_ws.all_tags(T()), summary=docs_ws.summary(T()),
                           requests=docs_ws.pending_requests(T()), expiring=docs_ws.expiring(T()),
                           rules=db.query(DocRule).filter_by(tenant_id=T().id).all(),
                           access_names=docs_ws.ACCESS_NAMES,
                           q=request.args.get("q", ""), tag=request.args.get("tag", ""))


@bp.route("/docs/<int:mid>", methods=["POST"])
@staff_required
def doc_file(tenant_slug, mid):
    media = _own(Media, mid)
    action = request.form.get("action")
    if action == "tags":
        docs_ws.set_tags(media, request.form.get("tags", ""))
    elif action == "move":
        media.folder_id = request.form.get("folder_id", type=int)
        db.commit()
    elif action == "link":
        docs_ws.link_to(media, request.form.get("entity", ""), request.form.get("entity_id", type=int))
    elif action == "version":
        fs = request.files.get("file")
        if fs and fs.filename:
            new = save_upload(T(), fs)
            new.owner_id = g.user.id
            docs_ws.add_version(T(), media, new, note=request.form.get("note", ""))
            flash(f"Загружена версия {new.version}", "success")
    elif action == "approve":
        media.status = "approved"
        db.commit()
    elif action == "delete":
        from ..storage import delete_media
        delete_media(T(), media)
        flash("Файл удалён", "warning")
    return redirect(request.referrer or url_for("erp.docs"))


@bp.route("/docs/requests/<int:rid>/cancel", methods=["POST"])
@staff_required
def doc_request_cancel(tenant_slug, rid):
    req = _own(DocRequest, rid)
    req.status = "cancelled"
    db.commit()
    return redirect(url_for("erp.docs"))
