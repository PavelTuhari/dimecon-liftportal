"""Размещение приложения в подкаталоге чужого домена.

На демо-хостинге слот выдаётся не отдельным доменом, а префиксом пути:
https://eminescu.md/TehnCons/. nginx проксирует запрос вместе с префиксом,
поэтому приложение должно узнать себя по этому пути и строить все ссылки с ним.

Префикс снимается с PATH_INFO и переносится в SCRIPT_NAME — дальше Flask сам
подставляет его в url_for, в редиректы и в путь cookie. Код маршрутов не меняется,
а при пустом URL_PREFIX (локальная работа) обёртка вообще не ставится.
"""
from __future__ import annotations


class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix: str):
        self.wsgi_app = wsgi_app
        self.prefix = "/" + prefix.strip("/")

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            return self.wsgi_app(environ, start_response)
        if path == "/":
            # корень домена слоту не принадлежит, но переход по нему удобнее не терять
            start_response("302 Found", [("Location", self.prefix + "/"), ("Content-Length", "0")])
            return [b""]
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"Приложение отвечает по адресу {self.prefix}/".encode()]
