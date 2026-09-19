"""Подключение к БД: MySQL как основной режим, SQLite как автоматический fallback."""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


SessionLocal = scoped_session(sessionmaker(autoflush=False, expire_on_commit=False))
engine = None
active_db = "none"


def _try_engine(url: str):
    kwargs = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_recycle=280, pool_size=10, max_overflow=20)
    eng = create_engine(url, **kwargs)
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    return eng


def init_engine(app):
    """Пробуем DATABASE_URL (MySQL); при недоступности — SQLite."""
    global engine, active_db
    primary = app.config["DATABASE_URL"]
    try:
        engine = _try_engine(primary)
        active_db = "mysql" if primary.startswith("mysql") else primary.split(":")[0]
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("Основная БД недоступна (%s). Переключаюсь на SQLite.", str(exc)[:160])
        engine = _try_engine(app.config["SQLITE_FALLBACK_URL"])
        active_db = "sqlite (fallback)"

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

    SessionLocal.configure(bind=engine)
    app.config["ACTIVE_DB"] = active_db
    return engine


def create_all():
    from . import models  # noqa: F401  (регистрация моделей)
    Base.metadata.create_all(engine)


def mysql_ddl() -> str:
    """Экспорт DDL под MySQL — для развёртывания на реальном сервере."""
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateTable
    from . import models  # noqa: F401

    out = []
    for table in Base.metadata.sorted_tables:
        out.append(str(CreateTable(table).compile(dialect=mysql.dialect())).strip() + ";")
    return "\n\n".join(out)


def first_or_404(query):
    from flask import abort
    obj = query.first()
    if obj is None:
        abort(404)
    return obj
