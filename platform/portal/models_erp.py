"""Модель данных управленческих модулей: проекты, продажи, закупки, счета, таблицы, документы.

Набор повторяет функции, которыми застройщик пользуется в Odoo (Project, Sales, Purchase,
Invoicing, Spreadsheet, Documents), но описан в терминах компании, сдающей технику и
выполняющей работы: объект — проект, смета — коммерческое предложение, закупка — материалы
и услуги подрядчиков, счёт — основание оплаты.

Всё tenant-scoped: ни одна запись не живёт вне компании-арендатора.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.utcnow()


def token() -> str:
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------- Проекты

class Task(Base):
    """Работа по объекту. Поддерживает подзадачи, зависимости, вехи и повторение."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    depends_on_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    stage: Mapped[str] = mapped_column(String(16), default="todo", index=True)  # todo/doing/review/done/cancelled
    priority: Mapped[int] = mapped_column(Integer, default=0)                   # 0 обычная, 1 важная, 2 срочная
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    planned_hours: Mapped[float] = mapped_column(Float, default=0)
    starts_on: Mapped[Optional[date]] = mapped_column(Date)
    due_on: Mapped[Optional[date]] = mapped_column(Date)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False)
    milestone_amount: Mapped[float] = mapped_column(Float, default=0)   # сумма этапа для поэтапного счёта
    invoiced: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[str] = mapped_column(String(200), default="")
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict)        # {"every": 7, "unit": "day", "until": "..."}
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    parent: Mapped[Optional["Task"]] = relationship(remote_side=[id], foreign_keys=[parent_id],
                                                    back_populates="subtasks")
    subtasks: Mapped[list["Task"]] = relationship(back_populates="parent", foreign_keys=[parent_id],
                                                  cascade="all, delete-orphan")
    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_tasks_project_stage", "project_id", "stage"),)


class Timesheet(Base):
    """Отметка рабочего времени: основание для себестоимости и для счёта по факту."""
    __tablename__ = "timesheets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    work_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    hours: Mapped[float] = mapped_column(Float, default=0)
    cost_rate: Mapped[float] = mapped_column(Float, default=0)      # себестоимость часа
    bill_rate: Mapped[float] = mapped_column(Float, default=0)      # ставка для счёта
    billable: Mapped[bool] = mapped_column(Boolean, default=True)
    invoiced: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    task: Mapped[Optional[Task]] = relationship(back_populates="timesheets")


# ---------------------------------------------------------------- Продажи

class SalesTemplate(Base):
    """Шаблон коммерческого предложения: набор строк, который подставляется одним действием."""
    __tablename__ = "sales_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    note: Mapped[str] = mapped_column(Text, default="")
    valid_days: Mapped[int] = mapped_column(Integer, default=14)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SalesOrder(Base):
    """Коммерческое предложение и заказ — одна запись, разница в статусе."""
    __tablename__ = "sales_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"))
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales_templates.id", ondelete="SET NULL"))
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    # draft → sent → accepted → confirmed → invoiced | cancelled
    currency: Mapped[str] = mapped_column(String(8), default="MDL")
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    vat_pct: Mapped[float] = mapped_column(Float, default=20)
    amount_net: Mapped[float] = mapped_column(Float, default=0)
    amount_vat: Mapped[float] = mapped_column(Float, default=0)
    amount_total: Mapped[float] = mapped_column(Float, default=0)
    amount_optional: Mapped[float] = mapped_column(Float, default=0)   # сумма необязательных допработ
    note: Mapped[str] = mapped_column(Text, default="")
    terms: Mapped[str] = mapped_column(Text, default="")
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    accept_token: Mapped[str] = mapped_column(String(48), default=token, index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    accepted_by: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    lines: Mapped[list["SalesLine"]] = relationship(back_populates="so", cascade="all, delete-orphan",
                                                    order_by="SalesLine.sequence")


class SalesLine(Base):
    __tablename__ = "sales_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    so_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="text")   # equipment/service/product/text
    ref_id: Mapped[Optional[int]] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(16), default="шт")
    price: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)           # плановая себестоимость строки
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    so: Mapped[SalesOrder] = relationship(back_populates="lines")

    @property
    def amount(self) -> float:
        return round(self.qty * self.price * (1 - (self.discount_pct or 0) / 100), 2)


# ---------------------------------------------------------------- Закупки

class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    idno: Mapped[str] = mapped_column(String(32), default="")
    contact_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    payment_days: Mapped[int] = mapped_column(Integer, default=14)
    lead_days: Mapped[int] = mapped_column(Integer, default=3)      # обычный срок поставки
    rating: Mapped[float] = mapped_column(Float, default=0)         # средняя оценка поставок 0–5
    status: Mapped[str] = mapped_column(String(16), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PurchaseAgreement(Base):
    """Рамочное соглашение или тендер: условия, по которым потом оформляются заказы."""
    __tablename__ = "purchase_agreements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16), default="blanket")   # blanket — рамочное, tender — тендер
    valid_from: Mapped[Optional[date]] = mapped_column(Date)
    valid_to: Mapped[Optional[date]] = mapped_column(Date)
    terms: Mapped[dict] = mapped_column(JSON, default=dict)            # {"discount_pct": 5, "payment_days": 30}
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PurchaseOrder(Base):
    """Запрос цены → заказ поставщику → приёмка → счёт поставщика."""
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(32), index=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    agreement_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_agreements.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(16), default="rfq", index=True)
    # rfq → sent → confirmed → received (частично/полностью) → billed | cancelled
    currency: Mapped[str] = mapped_column(String(8), default="MDL")
    vat_pct: Mapped[float] = mapped_column(Float, default=20)
    amount_net: Mapped[float] = mapped_column(Float, default=0)
    amount_vat: Mapped[float] = mapped_column(Float, default=0)
    amount_total: Mapped[float] = mapped_column(Float, default=0)
    billed_amount: Mapped[float] = mapped_column(Float, default=0)
    expected_on: Mapped[Optional[date]] = mapped_column(Date)
    received_on: Mapped[Optional[date]] = mapped_column(Date)
    bill_due_on: Mapped[Optional[date]] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    lines: Mapped[list["PurchaseLine"]] = relationship(back_populates="po", cascade="all, delete-orphan",
                                                       order_by="PurchaseLine.sequence")


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit: Mapped[str] = mapped_column(String(16), default="шт")
    price: Mapped[float] = mapped_column(Float, default=0)
    received_qty: Mapped[float] = mapped_column(Float, default=0)
    sequence: Mapped[int] = mapped_column(Integer, default=0)

    po: Mapped[PurchaseOrder] = relationship(back_populates="lines")

    @property
    def amount(self) -> float:
        return round(self.qty * self.price, 2)


class ReorderRule(Base):
    """Правило пополнения: когда остаток ниже минимума — готовим запрос цены поставщику."""
    __tablename__ = "reorder_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vendors.id", ondelete="SET NULL"))
    min_qty: Mapped[float] = mapped_column(Float, default=0)
    max_qty: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ---------------------------------------------------------------- Счета и платежи

class Payment(Base):
    """Оплата по счёту. Сумма оплат определяет статус документа."""
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(8), default="in")   # in — от клиента, out — поставщику
    amount: Mapped[float] = mapped_column(Float, default=0)
    paid_on: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    method: Mapped[str] = mapped_column(String(16), default="bank")   # bank/cash/card/offset
    reference: Mapped[str] = mapped_column(String(80), default="")
    note: Mapped[str] = mapped_column(String(255), default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RecurringPlan(Base):
    """Повторяющийся счёт: абонемент, обслуживание, аренда помесячно."""
    __tablename__ = "recurring_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"))
    amount: Mapped[float] = mapped_column(Float, default=0)
    vat_pct: Mapped[float] = mapped_column(Float, default=20)
    period: Mapped[str] = mapped_column(String(12), default="month")   # month/quarter/year
    day_of_month: Mapped[int] = mapped_column(Integer, default=1)
    next_run: Mapped[Optional[date]] = mapped_column(Date, index=True)
    last_run: Mapped[Optional[date]] = mapped_column(Date)
    issued_count: Mapped[int] = mapped_column(Integer, default=0)
    payment_days: Mapped[int] = mapped_column(Integer, default=10)
    lines: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------------------------------------------------------- Таблицы

class Sheet(Base):
    """Живая таблица: формулы и функции, читающие данные компании прямо из базы."""
    __tablename__ = "sheets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16), default="sheet")   # sheet | template
    cells: Mapped[dict] = mapped_column(JSON, default=dict)          # {"A1": "Заголовок", "B2": "=СУММА(B3:B9)"}
    rows: Mapped[int] = mapped_column(Integer, default=30)
    cols: Mapped[int] = mapped_column(Integer, default=8)
    formats: Mapped[dict] = mapped_column(JSON, default=dict)        # условное форматирование и стили
    charts: Mapped[list] = mapped_column(JSON, default=list)         # [{"kind":"bar","labels":"A2:A8","values":"B2:B8"}]
    share_token: Mapped[str] = mapped_column(String(48), default=token, index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------------------------------------------------------- Документы

class DocFolder(Base):
    """Рабочее пространство документов: договоры, чертежи, паспорта ГПМ, акты."""
    __tablename__ = "doc_folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("doc_folders.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    access: Mapped[str] = mapped_column(String(16), default="internal")   # internal/partner/link
    color: Mapped[str] = mapped_column(String(16), default="")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class DocRequest(Base):
    """Запрос недостающего документа: ссылка с токеном, срок и отслеживание."""
    __tablename__ = "doc_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    folder_id: Mapped[Optional[int]] = mapped_column(ForeignKey("doc_folders.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    to_email: Mapped[str] = mapped_column(String(160), default="")
    to_name: Mapped[str] = mapped_column(String(160), default="")
    due_on: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending")   # pending/received/cancelled
    request_token: Mapped[str] = mapped_column(String(48), default=token, index=True)
    media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media.id", ondelete="SET NULL"))
    entity: Mapped[str] = mapped_column(String(24), default="")
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class DocRule(Base):
    """Правило автообработки: по тегу или типу файла выполнить действие."""
    __tablename__ = "doc_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    match_tag: Mapped[str] = mapped_column(String(80), default="")
    match_mime: Mapped[str] = mapped_column(String(80), default="")
    action: Mapped[str] = mapped_column(String(24), default="move")   # move/tag/task/notify
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    runs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
