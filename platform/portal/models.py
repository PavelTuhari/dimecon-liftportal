"""Модель данных платформы. Shared-schema multi-tenancy: всё tenant-scoped помечено tenant_id."""
from __future__ import annotations

import secrets
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.utcnow()


def i18n(ru="", ro="", en=""):
    return {"ru": ru, "ro": ro or ru, "en": en or ru}


# ---------------------------------------------------------------- Платформа / арендаторы

class Tenant(Base):
    """Компания-арендатор. Одна запись = один white-label сайт + кабинет."""
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    legal_name: Mapped[str] = mapped_column(String(200), default="")
    tagline: Mapped[dict] = mapped_column(JSON, default=dict)          # i18n
    about: Mapped[dict] = mapped_column(JSON, default=dict)            # i18n, rich text
    city: Mapped[str] = mapped_column(String(80), default="Chișinău")
    country: Mapped[str] = mapped_column(String(80), default="Moldova")
    address: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    phone2: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    founded_year: Mapped[Optional[int]] = mapped_column(Integer)
    idno: Mapped[str] = mapped_column(String(32), default="")
    custom_domain: Mapped[str] = mapped_column(String(160), default="", index=True)
    default_locale: Mapped[str] = mapped_column(String(2), default="ru")
    locales: Mapped[list] = mapped_column(JSON, default=lambda: ["ru", "ro", "en"])
    currency: Mapped[str] = mapped_column(String(3), default="MDL")
    vat_rate: Mapped[float] = mapped_column(Float, default=20.0)
    plan: Mapped[str] = mapped_column(String(20), default="pro")         # base/pro/max
    status: Mapped[str] = mapped_column(String(20), default="active")    # pending/active/suspended
    is_listed: Mapped[bool] = mapped_column(Boolean, default=True)       # виден в маркетплейсе
    profile: Mapped[str] = mapped_column(String(40), default="cranes")   # cranes / transport / mixed
    # white-label: тема, логотип, герой
    theme: Mapped[dict] = mapped_column(JSON, default=dict)     # accent, navy, logo_url, hero_image_url, dark
    hero: Mapped[dict] = mapped_column(JSON, default=dict)      # title/subtitle i18n, stats
    faq: Mapped[list] = mapped_column(JSON, default=list)       # [{q:{..},a:{..}}]
    social: Mapped[dict] = mapped_column(JSON, default=dict)
    # инфраструктура компании
    smtp: Mapped[dict] = mapped_column(JSON, default=dict)      # host, port, user, password, tls, from_email, from_name
    storage: Mapped[dict] = mapped_column(JSON, default=dict)   # backend: local|url|s3, base_url, bucket, endpoint, keys
    pricing: Mapped[dict] = mapped_column(JSON, default=dict)   # коэффициенты, зоны, допуслуги
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    members: Mapped[list["Membership"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    def t(self, field: str, lang: str) -> str:
        v = getattr(self, field) or {}
        return v.get(lang) or v.get("ru") or v.get("ro") or v.get("en") or ""


class User(Base):
    """Глобальная личность. Роль в компании — через Membership."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    full_name: Mapped[str] = mapped_column(String(160), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(2), default="ru")
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    """Роль пользователя внутри компании: owner / manager / dispatcher / staff / customer / partner."""
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    tenant: Mapped[Tenant] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")

    STAFF_ROLES = ("owner", "manager", "dispatcher", "staff")


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20), default="staff")
    partner_id: Mapped[Optional[int]] = mapped_column(Integer)
    token: Mapped[str] = mapped_column(String(64), unique=True, default=lambda: secrets.token_urlsafe(24))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Domain(Base):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    host: Mapped[str] = mapped_column(String(160), unique=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- Медиа

class Media(Base):
    """Файл. url — абсолютный (любое хранилище) либо относительный к локальному диску."""
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    backend: Mapped[str] = mapped_column(String(16), default="local")   # local | url | s3
    key: Mapped[str] = mapped_column(String(400), default="")            # путь/ключ в хранилище
    url: Mapped[str] = mapped_column(String(600))                         # публичный URL
    filename: Mapped[str] = mapped_column(String(255), default="")
    mime: Mapped[str] = mapped_column(String(80), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    alt: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------------------------------------------------------- Парк техники

class EquipmentCategory(Base):
    __tablename__ = "equipment_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))      # mobile_crane, tower_crane, crawler_crane, semitrailer, lowbed, tipper
    name: Mapped[dict] = mapped_column(JSON, default=dict)
    kind: Mapped[str] = mapped_column(String(16), default="crane")  # crane | transport | other
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (Index("ix_eq_tenant_slug", "tenant_id", "slug"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment_categories.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(String(120))
    inventory_no: Mapped[str] = mapped_column(String(40), default="")
    brand: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(120))
    title: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")   # active/maintenance/repair/reserve
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # ключевые ТТХ (для кранов) / (для транспорта)
    capacity_t: Mapped[float] = mapped_column(Float, default=0)
    radius_m: Mapped[float] = mapped_column(Float, default=0)
    height_m: Mapped[float] = mapped_column(Float, default=0)
    outrigger_half_m: Mapped[float] = mapped_column(Float, default=3.5)
    payload_kg: Mapped[float] = mapped_column(Float, default=0)
    platform_l_mm: Mapped[float] = mapped_column(Float, default=0)
    platform_w_mm: Mapped[float] = mapped_column(Float, default=0)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    # тарифы единицы
    hourly_rate: Mapped[float] = mapped_column(Float, default=0)
    min_hours: Mapped[float] = mapped_column(Float, default=4)
    mobilization_fee: Mapped[float] = mapped_column(Float, default=0)
    per_km_rate: Mapped[float] = mapped_column(Float, default=0)
    photo_url: Mapped[str] = mapped_column(String(600), default="")
    gallery: Mapped[list] = mapped_column(JSON, default=list)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    category: Mapped[Optional[EquipmentCategory]] = relationship()
    load_charts: Mapped[list["LoadChart"]] = relationship(cascade="all, delete-orphan", order_by="LoadChart.radius_m")

    @property
    def is_crane(self) -> bool:
        return not self.category or self.category.kind == "crane"


class LoadChart(Base):
    """Грузовая характеристика: на вылете R в конфигурации C поднимает Q до высоты H."""
    __tablename__ = "load_charts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    configuration: Mapped[str] = mapped_column(String(80), default="main")
    outriggers: Mapped[str] = mapped_column(String(12), default="full")
    radius_m: Mapped[float] = mapped_column(Float)
    capacity_t: Mapped[float] = mapped_column(Float)
    height_m: Mapped[float] = mapped_column(Float, default=0)


class Booking(Base):
    """Занятость техники (жёсткая и мягкая бронь, ТО)."""
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(20), default="order")   # order/soft/maintenance
    order_id: Mapped[Optional[int]] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(200), default="")


# ---------------------------------------------------------------- Каталог: услуги, товары, кейсы, страницы

class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(40), default="")
    icon: Mapped[str] = mapped_column(String(8), default="🏗")
    title: Mapped[dict] = mapped_column(JSON, default=dict)
    short: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    price_from: Mapped[float] = mapped_column(Float, default=0)
    pricing_model: Mapped[str] = mapped_column(String(20), default="hourly")
    is_orderable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str] = mapped_column(String(600), default="")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(60), default="")
    slug: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(80), default="")
    title: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    unit: Mapped[str] = mapped_column(String(16), default="шт")
    price: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[float] = mapped_column(Float, default=0)
    made_to_order: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str] = mapped_column(String(600), default="")


class CaseStudy(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(120))
    title: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    client_name: Mapped[str] = mapped_column(String(160), default="")
    location: Mapped[str] = mapped_column(String(160), default="")
    year: Mapped[Optional[int]] = mapped_column(Integer)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)    # weight_t, height_m, hours
    image_url: Mapped[str] = mapped_column(String(600), default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Page(Base):
    __tablename__ = "pages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(120))
    title: Mapped[dict] = mapped_column(JSON, default=dict)
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    in_menu: Mapped[bool] = mapped_column(Boolean, default=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(Integer)
    author: Mapped[str] = mapped_column(String(120), default="")
    rating: Mapped[int] = mapped_column(Integer, default=5)
    body: Mapped[str] = mapped_column(Text, default="")
    reply: Mapped[str] = mapped_column(Text, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------------------------------------------------------- CRM

class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(10), default="b2c")     # b2c / b2b
    name: Mapped[str] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="", index=True)
    email: Mapped[str] = mapped_column(String(160), default="", index=True)
    source: Mapped[str] = mapped_column(String(40), default="site")
    tags: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


LEAD_STAGES = ["new", "contacted", "quoted", "won", "lost"]
ORDER_STATUSES = ["submitted", "under_review", "quoted", "confirmed", "scheduled", "in_progress",
                  "completed", "invoiced", "paid", "cancelled"]


class Order(Base):
    """Лид + заказ в одной сущности: stage — воронка CRM, status — исполнение."""
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(24), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"))
    partner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("partners.id", ondelete="SET NULL"))
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id", ondelete="SET NULL"))
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("services.id", ondelete="SET NULL"))
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(10), default="b2c")
    source: Mapped[str] = mapped_column(String(30), default="wizard")
    stage: Mapped[str] = mapped_column(String(16), default="new", index=True)
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    task_type: Mapped[str] = mapped_column(String(40), default="")
    cargo: Mapped[str] = mapped_column(String(200), default="")
    weight_t: Mapped[float] = mapped_column(Float, default=0)
    height_m: Mapped[float] = mapped_column(Float, default=0)
    radius_m: Mapped[float] = mapped_column(Float, default=0)
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    address: Mapped[str] = mapped_column(String(255), default="")
    zone: Mapped[str] = mapped_column(String(40), default="")
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    hours: Mapped[float] = mapped_column(Float, default=4)
    flexible_date: Mapped[bool] = mapped_column(Boolean, default=False)
    price_min: Mapped[float] = mapped_column(Float, default=0)
    price_max: Mapped[float] = mapped_column(Float, default=0)
    price_final: Mapped[float] = mapped_column(Float, default=0)
    breakdown: Mapped[list] = mapped_column(JSON, default=list)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reasons: Mapped[list] = mapped_column(JSON, default=list)
    selector_log: Mapped[dict] = mapped_column(JSON, default=dict)
    comment: Mapped[str] = mapped_column(Text, default="")
    internal_note: Mapped[str] = mapped_column(Text, default="")
    payment_status: Mapped[str] = mapped_column(String(16), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    contact: Mapped[Optional[Contact]] = relationship()
    equipment: Mapped[Optional[Equipment]] = relationship()
    service: Mapped[Optional[Service]] = relationship()
    assignee: Mapped[Optional[User]] = relationship(foreign_keys=[assignee_id])
    activities: Mapped[list["Activity"]] = relationship(cascade="all, delete-orphan", order_by="Activity.created_at.desc()")


class Activity(Base):
    """История по заказу/контакту: заметка, звонок, смена статуса, письмо."""
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16), default="note")   # note/call/status/email/task
    body: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    user: Mapped[Optional[User]] = relationship()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    partner_id: Mapped[Optional[int]] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(16))     # quote/act/invoice/confirmation
    number: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="issued")
    issued_at: Mapped[date] = mapped_column(Date, default=date.today)
    due_at: Mapped[Optional[date]] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


# ---------------------------------------------------------------- B2B: партнёры, проекты, смены

class Partner(Base):
    __tablename__ = "partners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    idno: Mapped[str] = mapped_column(String(32), default="")
    contact_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(160), default="")
    tier: Mapped[str] = mapped_column(String(16), default="base")   # base/bronze/silver/gold/platinum
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    credit_limit: Mapped[float] = mapped_column(Float, default=0)
    payment_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    turnover: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    starts_at: Mapped[Optional[date]] = mapped_column(Date)
    ends_at: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Shift(Base):
    """Сменный рапорт — основание для акта и счёта."""
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    equipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("equipment.id", ondelete="SET NULL"))
    work_date: Mapped[date] = mapped_column(Date, default=date.today)
    operator: Mapped[str] = mapped_column(String(120), default="")
    hours_worked: Mapped[float] = mapped_column(Float, default=0)
    hours_idle: Mapped[float] = mapped_column(Float, default=0)
    idle_fault: Mapped[str] = mapped_column(String(16), default="")
    lifts: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    photos: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="submitted")   # submitted/approved/disputed
    dispute_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------------------------------------------------------------- Служебное

class Outbox(Base):
    """Журнал писем: отправлено через SMTP компании/платформы либо сохранено, если SMTP не настроен."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    to_email: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued")   # sent/queued/failed
    transport: Mapped[str] = mapped_column(String(40), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
