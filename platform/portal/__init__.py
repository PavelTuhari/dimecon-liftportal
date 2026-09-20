"""Application factory."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, g, has_request_context, render_template, request, send_from_directory, session

from config import Config
from . import auth, hosting, i18n, richtext
from .db import SessionLocal, create_all, init_engine
from .tenancy import DomainRewriteMiddleware, resolve_tenant, tenant_url_defaults


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

    init_engine(app)
    create_all()
    from .seed import ensure_seed
    ensure_seed(app)

    app.wsgi_app = DomainRewriteMiddleware(app.wsgi_app, app.config["PLATFORM_HOST"])

    if app.config.get("BEHIND_PROXY"):
        # за nginx: схему и адрес клиента берём из заголовков, иначе ссылки уйдут на http
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    if app.config.get("URL_PREFIX"):
        app.config["APPLICATION_ROOT"] = app.config["URL_PREFIX"]
        app.config["SESSION_COOKIE_PATH"] = app.config["URL_PREFIX"] + "/"
        app.wsgi_app = hosting.PrefixMiddleware(app.wsgi_app, app.config["URL_PREFIX"])

    from .blueprints.platform import bp as platform_bp
    from .blueprints.site import bp as site_bp
    from .blueprints.account import bp as account_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.partner import bp as partner_bp
    from .blueprints.erp import bp as erp_bp
    from .blueprints.setup import bp as setup_bp
    from .blueprints.api import bp as api_bp
    from .blueprints.docs_export import bp as export_bp
    app.register_blueprint(platform_bp)
    app.register_blueprint(export_bp, url_prefix="/s/<tenant_slug>/export")
    app.register_blueprint(site_bp, url_prefix="/s/<tenant_slug>")
    app.register_blueprint(account_bp, url_prefix="/s/<tenant_slug>/account")
    app.register_blueprint(admin_bp, url_prefix="/s/<tenant_slug>/admin")
    app.register_blueprint(erp_bp, url_prefix="/s/<tenant_slug>/admin")
    app.register_blueprint(setup_bp, url_prefix="/s/<tenant_slug>/admin")
    app.register_blueprint(partner_bp, url_prefix="/s/<tenant_slug>/partner")
    app.register_blueprint(api_bp, url_prefix="/api")

    app.url_defaults(tenant_url_defaults)

    @app.before_request
    def _before():
        resolve_tenant()
        auth.load_current_user()
        if request.args.get("lang") in i18n.LANGS:
            session["lang"] = request.args["lang"]
        g.lang = None
        i18n.current_lang()
        return auth.check_csrf()  # вернёт redirect, если форма входа устарела

    @app.teardown_appcontext
    def _teardown(exc):
        SessionLocal.remove()

    @app.route("/media/<tenant_slug>/<path:filename>")
    def media_file(tenant_slug, filename):
        root = Path(app.config["UPLOAD_DIR"]) / tenant_slug
        if not root.exists():
            abort(404)
        return send_from_directory(root, filename)

    if app.config.get("DOCS_DIR"):
        docs_root = Path(app.config["DOCS_DIR"]).resolve()

        @app.route("/docs/", defaults={"filename": "index.html"})
        @app.route("/docs/<path:filename>")
        def docs_file(filename):
            """Статическая документация проекта: хаб, акты, презентация, снимки."""
            if not docs_root.exists():
                abort(404)
            target = (docs_root / filename).resolve()
            if not str(target).startswith(str(docs_root)):  # выход за каталог запрещён
                abort(404)
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                abort(404)
            return send_from_directory(docs_root, target.relative_to(docs_root).as_posix())

    @app.context_processor
    def _ctx():
        return {
            "t": i18n.t, "tr": i18n.tr, "lang": i18n.current_lang(), "LANGS": i18n.LANGS,
            "LANG_NAMES": i18n.LANG_NAMES, "tenant": getattr(g, "tenant", None), "user": g.user,
            "membership": getattr(g, "membership", None), "is_staff": auth.is_staff(), "is_owner": auth.is_owner(),
            "csrf_token": auth.csrf_token, "platform_name": app.config["PLATFORM_NAME"],
            "platform_host": app.config["PLATFORM_HOST"], "now": datetime.utcnow(),
            "active_db": app.config["ACTIVE_DB"],
        }

    @app.template_filter("money")
    def money(v, cur=None):
        try:
            s = f"{float(v):,.0f}".replace(",", " ")
        except (TypeError, ValueError):
            return v
        return f"{s} {cur}" if cur else s

    @app.template_filter("asset")
    def asset(url):
        """Ссылка на файл, записанная в базе (/media/…, /static/…), с префиксом размещения.

        В базе адреса хранятся от корня сайта. Когда приложение живёт в подкаталоге
        чужого домена (https://host/TehnCons/), такой адрес ведёт мимо слота — картинки
        не грузятся. Здесь подставляется SCRIPT_NAME текущего запроса; внешние ссылки
        (http://…, data:…) остаются как есть.
        """
        if not url:
            return ""
        u = str(url)
        if not u.startswith(("/media/", "/static/", "/uploads/")):
            return u
        root = request.script_root if has_request_context() else app.config.get("URL_PREFIX", "")
        return f"{root}{u}" if root else u

    @app.template_filter("richtext")
    def richtext_filter(v):
        return richtext.richtext(v)

    @app.template_filter("plain")
    def plain_filter(v, limit=0):
        return richtext.plain(v, limit)

    @app.template_filter("dt")
    def dt(v, fmt="%d.%m.%Y %H:%M"):
        return v.strftime(fmt) if v else "—"

    @app.template_filter("tojson_pretty")
    def tojson_pretty(v):
        return json.dumps(v or {}, ensure_ascii=False, indent=2)

    @app.errorhandler(403)
    def _403(e):
        return render_template("error.html", code=403, message="Недостаточно прав"), 403

    @app.errorhandler(404)
    def _404(e):
        return render_template("error.html", code=404, message=getattr(e, "description", "Страница не найдена")), 404

    return app
