import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Contact  # noqa: E402

app = create_app()
with app.app_context():
    rows = db.query(Contact).filter_by(tenant_id=1).order_by(Contact.id).all()
    print(f"контактов: {len(rows)}")
    for c in rows:
        print(f"{c.id:>3} | {(c.name or '')[:26]:<26} | {(c.company or '')[:28]:<28} | {(c.phone or ''):<15} | {c.source}")
