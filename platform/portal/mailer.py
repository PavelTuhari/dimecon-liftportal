"""Почта: сначала SMTP компании, затем SMTP платформы, иначе — в журнал Outbox."""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import current_app

from .db import SessionLocal
from .models import Outbox, Tenant


def _smtp_config(tenant: Tenant | None) -> tuple[dict | None, str]:
    if tenant and (tenant.smtp or {}).get("host"):
        return tenant.smtp, f"tenant-smtp:{tenant.smtp.get('host')}"
    cfg = current_app.config
    if cfg.get("SMTP_HOST"):
        return {"host": cfg["SMTP_HOST"], "port": cfg["SMTP_PORT"], "user": cfg["SMTP_USER"],
                "password": cfg["SMTP_PASSWORD"], "tls": cfg["SMTP_TLS"], "from_email": cfg["SMTP_FROM"],
                "from_name": cfg["PLATFORM_NAME"]}, f"platform-smtp:{cfg['SMTP_HOST']}"
    return None, ""


def _send_via(cfg: dict, to: str, subject: str, body: str, html: str | None = None):
    msg = EmailMessage()
    from_name = cfg.get("from_name") or ""
    from_email = cfg.get("from_email") or cfg.get("user") or "noreply@localhost"
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
    port = int(cfg.get("port") or 587)
    use_ssl = str(cfg.get("ssl", "")).lower() in ("1", "true", "on") or port == 465
    use_tls = str(cfg.get("tls", "1")).lower() in ("1", "true", "on")
    if use_ssl:
        server = smtplib.SMTP_SSL(cfg["host"], port, timeout=15)
    else:
        server = smtplib.SMTP(cfg["host"], port, timeout=15)
    with server:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if cfg.get("user"):
            server.login(cfg["user"], cfg.get("password") or "")
        server.send_message(msg)


def send_mail(tenant: Tenant | None, to: str, subject: str, body: str, html: str | None = None) -> Outbox:
    """Никогда не бросает исключение наружу: результат фиксируется в Outbox."""
    cfg, transport = _smtp_config(tenant)
    rec = Outbox(tenant_id=tenant.id if tenant else None, to_email=to, subject=subject, body=body,
                 transport=transport or "none")
    if not cfg:
        rec.status = "queued"
        rec.error = "SMTP не настроен: письмо сохранено в журнале"
    else:
        try:
            _send_via(cfg, to, subject, body, html)
            rec.status = "sent"
        except Exception as exc:  # noqa: BLE001
            rec.status = "failed"
            rec.error = str(exc)[:900]
    SessionLocal.add(rec)
    SessionLocal.commit()
    return rec


def test_smtp(tenant: Tenant, to: str) -> tuple[bool, str]:
    cfg = tenant.smtp or {}
    if not cfg.get("host"):
        return False, "Укажите хост SMTP"
    try:
        _send_via(cfg, to, f"[{tenant.name}] Проверка SMTP", "Если вы читаете это письмо — почтовый сервер компании настроен верно.")
        return True, f"Письмо отправлено на {to}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]
