import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    PLATFORM_NAME = os.getenv("PLATFORM_NAME", "LiftPortal")
    PLATFORM_HOST = os.getenv("PLATFORM_HOST", "localhost:8090")
    PORT = int(os.getenv("PORT", "8090"))

    # Размещение в подкаталоге чужого домена: https://host/TehnCons/.
    # Пустое значение — приложение живёт в корне, как при локальной работе.
    URL_PREFIX = "/" + os.getenv("URL_PREFIX", "").strip("/") if os.getenv("URL_PREFIX", "").strip("/") else ""
    BEHIND_PROXY = _bool(os.getenv("BEHIND_PROXY"), False)
    SESSION_COOKIE_SECURE = _bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    # Каталог со статической документацией (хаб, акты, презентация); отдаётся по /docs/
    DOCS_DIR = os.getenv("DOCS_DIR", "")

    DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://liftportal:secret@127.0.0.1:3306/liftportal?charset=utf8mb4")
    SQLITE_FALLBACK_URL = f"sqlite:///{(BASE_DIR / 'platform.db').as_posix()}"

    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_TLS = _bool(os.getenv("SMTP_TLS"), True)
    SMTP_FROM = os.getenv("SMTP_FROM", "noreply@example.com")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    JSON_AS_ASCII = False
