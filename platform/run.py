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
        print(f"[{app.config['PLATFORM_NAME']}] http://localhost:{port}  (db: {app.config['ACTIVE_DB']})")
        # слушаем обе стеки: иначе localhost резолвится в ::1 и клиент ждёт таймаут IPv6 (~2 с)
        serve(app, listen=f"0.0.0.0:{port} [::]:{port}", threads=8)
