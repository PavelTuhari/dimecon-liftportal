"""Хранилища файлов. У каждой компании — своё: локальный диск платформы, произвольный URL,
S3-совместимое хранилище (MinIO/R2/AWS). Централизована только запись Media в БД."""
from __future__ import annotations

import mimetypes
import re
import secrets
from pathlib import Path

from flask import current_app, url_for

from .models import Media, Tenant

SAFE = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_MIME_PREFIX = ("image/", "application/pdf")


def _safe_name(name: str) -> str:
    base = Path(name).name
    base = SAFE.sub("-", base).strip("-") or "file"
    return f"{secrets.token_hex(4)}-{base}"[:120]


def backend_for(tenant: Tenant) -> str:
    return (tenant.storage or {}).get("backend") or "local"


def save_upload(tenant: Tenant, file_storage) -> Media:
    """Принять загруженный файл в хранилище компании и вернуть Media."""
    mime = file_storage.mimetype or mimetypes.guess_type(file_storage.filename or "")[0] or ""
    if not mime.startswith(ALLOWED_MIME_PREFIX):
        raise ValueError("Разрешены изображения и PDF")
    name = _safe_name(file_storage.filename or "file")
    backend = backend_for(tenant)
    data = file_storage.read()
    if backend == "s3":
        url, key = _s3_put(tenant, name, data, mime)
    else:  # local (и для backend=url загрузки тоже кладём локально)
        url, key = _local_put(tenant, name, data)
        backend = "local"
    return Media(tenant_id=tenant.id, backend=backend, key=key, url=url,
                 filename=file_storage.filename or name, mime=mime, size=len(data))


def add_by_url(tenant: Tenant, url: str, filename: str = "") -> Media:
    """Файл уже лежит где угодно (CDN, Drive-ссылка, свой сервер) — просто регистрируем."""
    if not re.match(r"^https?://", url):
        raise ValueError("Нужен абсолютный URL (http/https)")
    mime = mimetypes.guess_type(url)[0] or ""
    return Media(tenant_id=tenant.id, backend="url", key="", url=url,
                 filename=filename or url.rsplit("/", 1)[-1][:200], mime=mime, size=0)


def delete_media(tenant: Tenant, media: Media):
    if media.backend == "local" and media.key:
        p = _local_root(tenant) / media.key
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    elif media.backend == "s3" and media.key:
        try:
            _s3_client(tenant).delete_object(Bucket=tenant.storage.get("bucket"), Key=media.key)
        except Exception:  # noqa: BLE001
            pass


# ---- local -------------------------------------------------------------------

def _local_root(tenant: Tenant) -> Path:
    root = Path(current_app.config["UPLOAD_DIR"]) / tenant.slug
    root.mkdir(parents=True, exist_ok=True)
    return root


def _local_put(tenant: Tenant, name: str, data: bytes):
    p = _local_root(tenant) / name
    p.write_bytes(data)
    url = url_for("media_file", tenant_slug=tenant.slug, filename=name)
    return url, name


# ---- s3 ----------------------------------------------------------------------

def _s3_client(tenant: Tenant):
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Для S3 установите пакет boto3: pip install boto3") from exc
    cfg = tenant.storage or {}
    return boto3.client(
        "s3",
        endpoint_url=cfg.get("endpoint") or None,
        aws_access_key_id=cfg.get("access_key"),
        aws_secret_access_key=cfg.get("secret_key"),
        region_name=cfg.get("region") or "auto",
    )


def _s3_put(tenant: Tenant, name: str, data: bytes, mime: str):
    cfg = tenant.storage or {}
    bucket = cfg.get("bucket")
    if not bucket:
        raise RuntimeError("Не указан bucket в настройках хранилища")
    key = f"{cfg.get('prefix', '').strip('/')}/{name}".strip("/")
    _s3_client(tenant).put_object(Bucket=bucket, Key=key, Body=data, ContentType=mime, ACL="public-read")
    base = (cfg.get("public_base_url") or "").rstrip("/")
    url = f"{base}/{key}" if base else f"{cfg.get('endpoint', '').rstrip('/')}/{bucket}/{key}"
    return url, key


def test_storage(tenant: Tenant) -> tuple[bool, str]:
    b = backend_for(tenant)
    if b == "local":
        root = _local_root(tenant)
        return True, f"Локальный диск платформы: {root}"
    if b == "url":
        return True, "Режим «внешние ссылки»: файлы регистрируются по URL, загрузка идёт на локальный диск."
    if b == "s3":
        try:
            c = _s3_client(tenant)
            c.head_bucket(Bucket=tenant.storage.get("bucket"))
            return True, "S3: bucket доступен"
        except Exception as exc:  # noqa: BLE001
            return False, f"S3: {exc}"
    return False, "Неизвестный тип хранилища"
