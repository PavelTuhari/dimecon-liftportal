"""Точка входа. Запуск: python run.py  (production-сервер waitress)."""
import os
import sys

from portal import create_app

app = create_app()

if __name__ == "__main__":
    port = app.config["PORT"]
    if "--dev" in sys.argv:
        app.run(host="0.0.0.0", port=port, debug=True)
    else:
        from waitress import serve
        # слушаем обе стеки: иначе localhost резолвится в ::1 и клиент ждёт таймаут IPv6 (~2 с).
        # За обратным прокси задаём LISTEN=127.0.0.1:порт — наружу порт не выставляется.
        listen = os.getenv("LISTEN", f"0.0.0.0:{port} [::]:{port}")
        prefix = app.config.get("URL_PREFIX", "")
        print(f"[{app.config['PLATFORM_NAME']}] {listen}{prefix}/  (db: {app.config['ACTIVE_DB']})")
        serve(app, listen=listen, threads=8)
