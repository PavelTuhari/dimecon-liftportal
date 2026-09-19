import re
import sys
import traceback

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from portal import create_app  # noqa: E402

app = create_app()
app.config["PROPAGATE_EXCEPTIONS"] = True
c = app.test_client()
r = c.get("/login")
tok = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
print("login:", c.post("/login", data={"email": "owner@dimecon.md", "password": "demo1234", "_csrf": tok}).status_code)

from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Document, Order, Shift  # noqa: E402

with app.app_context():
    doc = db.query(Document).filter_by(tenant_id=1).first()
    order = db.get(Order, doc.order_id) if doc else db.query(Order).filter_by(tenant_id=1).first()
    shift = db.query(Shift).filter_by(tenant_id=1).first()
    print("doc:", doc and (doc.id, doc.type, doc.order_id), "| order:", order and order.id, "| shift:", shift and shift.id)

for url in [f"/s/dimecon/export/orders/{order.id}/confirmation.pdf",
            f"/s/dimecon/export/documents/{doc.id}.pdf",
            f"/s/dimecon/export/shifts/{shift.id}.pdf" if shift else None,
            "/s/dimecon/export/documents.xlsx"]:
    if not url:
        continue
    try:
        resp = c.get(url)
        body = resp.get_data()
        print(f"\n{url}\n  HTTP {resp.status_code} {resp.headers.get('Content-Type')} {len(body)} Б")
        if body[:4] not in (b"%PDF", b"PK\x03\x04"):
            print("  BODY:", body[:400].decode("utf-8", "replace").replace("\n", " ")[:400])
    except Exception:
        print(f"\n{url}\n  ИСКЛЮЧЕНИЕ:")
        traceback.print_exc(limit=6)
