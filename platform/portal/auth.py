"""Аутентификация на сессиях, CSRF, декораторы ролей."""
from __future__ import annotations

import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import SessionLocal
from .models import Membership, User


def hash_password(pw: str) -> str:
    # чистим так же, как при проверке, иначе пароль с пробелом на конце нельзя будет ввести
    return generate_password_hash(clean_password(pw))


def verify_password(user: User, pw: str) -> bool:
    return bool(user and user.password_hash and check_password_hash(user.password_hash, clean_password(pw)))


# Невидимые символы, которые приезжают при копировании из PDF, писем и подсказок на странице.
INVISIBLE = "​‌‍⁠﻿ "


def clean_email(value: str) -> str:
    """Почта из формы: пробелы, невидимые символы и приклеившиеся разделители убираем.

    Подсказку с демо-доступами копируют целиком — вместе с «·», запятой или точкой,
    и вход отклонялся как «неверный e-mail», хотя пользователь всё сделал правильно.
    """
    v = (value or "")
    for ch in INVISIBLE:
        v = v.replace(ch, "")
    return v.strip().strip("·•,;:<>()[]\"'").strip().lower()


def clean_password(value: str) -> str:
    """Пароль: убираем невидимые символы и обрамляющие пробелы, середину не трогаем."""
    v = (value or "")
    for ch in INVISIBLE:
        v = v.replace(ch, "")
    return v.strip(" \t\r\n")


def login_user(user: User):
    session.clear()
    session.permanent = True
    session["uid"] = user.id
    session["csrf"] = secrets.token_urlsafe(24)


def logout_user():
    session.clear()


def load_current_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = SessionLocal.get(User, uid)
        if g.user and not g.user.is_active:
            g.user = None
    # членство в текущей компании
    g.membership = None
    if g.user and getattr(g, "tenant", None):
        g.membership = (SessionLocal.query(Membership)
                        .filter_by(tenant_id=g.tenant.id, user_id=g.user.id).first())


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if request.path.startswith("/api/"):
            return
        token = request.form.get("_csrf") or request.headers.get("X-CSRF")
        if not token or token != session.get("csrf"):
            # на форме входа устаревшая вкладка — частый и безобидный случай:
            # не пугаем кодом 400, а просто просим повторить на свежей странице
            if request.path.endswith("/login"):
                flash("Страница входа устарела — сессия началась заново. Введите данные ещё раз.", "warning")
                return redirect(request.path)
            abort(400, "CSRF token invalid")


def is_staff() -> bool:
    if g.user and g.user.is_platform_admin:
        return True
    return bool(g.membership and g.membership.role in Membership.STAFF_ROLES)


def is_owner() -> bool:
    if g.user and g.user.is_platform_admin:
        return True
    return bool(g.membership and g.membership.role in ("owner", "manager"))


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            flash("Войдите, чтобы продолжить", "warning")
            nxt = request.full_path if request.method == "GET" else None
            if getattr(g, "tenant", None):
                return redirect(url_for("account.login", tenant_slug=g.tenant.slug, next=nxt))
            return redirect(url_for("platform.login", next=nxt))
        return fn(*a, **kw)
    return wrapper


def staff_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if not is_staff():
            abort(403)
        return fn(*a, **kw)
    return wrapper


def owner_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if not is_owner():
            abort(403)
        return fn(*a, **kw)
    return wrapper


def platform_admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if not g.user.is_platform_admin:
            abort(403)
        return fn(*a, **kw)
    return wrapper


def partner_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if is_staff():
            return fn(*a, **kw)
        if not (g.membership and g.membership.role == "partner" and g.membership.partner_id):
            abort(403)
        return fn(*a, **kw)
    return wrapper
