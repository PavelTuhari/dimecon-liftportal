"""Определение компании (tenant) по домену, поддомену или префиксу /s/<slug>."""
from __future__ import annotations

from flask import abort, current_app, g, request

from .db import SessionLocal
from .models import Domain, Tenant

TENANT_BLUEPRINTS = ("site", "account", "admin", "partner", "export", "erp")


class DomainRewriteMiddleware:
    """Если хост — собственный домен компании, внутренне переписываем путь на /s/<slug>/…
    Так одна кодовая база отдаёт и white-label-домены, и путь-адреса без DNS."""

    def __init__(self, wsgi_app, platform_host: str):
        self.wsgi_app = wsgi_app
        self.platform_host = platform_host.lower()

    def __call__(self, environ, start_response):
        host = (environ.get("HTTP_HOST") or "").lower().split(":")[0]
        phost = self.platform_host.split(":")[0]
        path = environ.get("PATH_INFO", "/")
        slug = None
        if host and host != phost and host not in ("localhost", "127.0.0.1"):
            if host.endswith("." + phost):            # поддомен slug.platform
                slug = host[: -len(phost) - 1]
            else:                                     # собственный домен
                slug = _slug_for_domain(host)
        if slug and not path.startswith("/s/") and not path.startswith("/static/") and not path.startswith("/media/"):
            environ["PATH_INFO"] = f"/s/{slug}{path}"
            environ["liftportal.domain_mode"] = "1"
        return self.wsgi_app(environ, start_response)


def _slug_for_domain(host: str):
    db = SessionLocal()
    try:
        d = db.query(Domain).filter_by(host=host).first()
        if d:
            return db.get(Tenant, d.tenant_id).slug
        tnt = db.query(Tenant).filter_by(custom_domain=host).first()
        return tnt.slug if tnt else None
    finally:
        db.remove()


def resolve_tenant():
    """before_request: заполняет g.tenant для tenant-blueprint'ов."""
    g.tenant = None
    bp = (request.blueprint or "").split(".")[0]
    slug = request.view_args.get("tenant_slug") if request.view_args else None
    if bp in TENANT_BLUEPRINTS and slug:
        tenant = SessionLocal.query(Tenant).filter_by(slug=slug).first()
        if not tenant:
            abort(404, "Компания не найдена")
        if tenant.status == "suspended" and bp in ("site", "account", "partner"):
            abort(403, "Сайт компании временно приостановлен")
        g.tenant = tenant


def tenant_url_defaults(endpoint, values):
    """url_for внутри tenant-контекста автоматически подставляет slug."""
    if "tenant_slug" in values or not getattr(g, "tenant", None):
        return
    if current_app.url_map.is_endpoint_expecting(endpoint, "tenant_slug"):
        values["tenant_slug"] = g.tenant.slug


def tenant_url_value_preprocessor(endpoint, values):
    if values:
        values.pop("_", None)
