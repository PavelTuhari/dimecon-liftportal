"""Реквизиты компании и почта из командной строки.

    python tools/company_tool.py show                    [--tenant dimecon]
    python tools/company_tool.py set bank_iban=MD00... director_name="Ион Попеску"
    python tools/company_tool.py smtp host=mail.dimecon.md port=587 user=office@dimecon.md password=...
    python tools/company_tool.py mail-test office@dimecon.md
    python tools/company_tool.py invoice-preview          — счёт с текущими реквизитами в PDF
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.mailer import send_mail, test_smtp  # noqa: E402
from portal.models import Document, Order, Tenant  # noqa: E402

FIELDS = ["legal_name", "idno", "vat_code", "bank_name", "bank_iban", "bank_swift",
          "legal_address", "director_name", "accountant_name", "invoice_due_days", "vat_rate"]
TITLES = {"legal_name": "юр. название", "idno": "IDNO", "vat_code": "код НДС", "bank_name": "банк",
          "bank_iban": "IBAN", "bank_swift": "SWIFT", "legal_address": "юр. адрес",
          "director_name": "руководитель", "accountant_name": "бухгалтер",
          "invoice_due_days": "срок оплаты, дн.", "vat_rate": "НДС, %"}


def arg(name: str, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


command = sys.argv[1] if len(sys.argv) > 1 else "show"
slug = arg("--tenant", "dimecon")
pairs = [a for a in sys.argv[2:] if "=" in a and not a.startswith("--")]

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug=slug).first()
    if not tenant:
        raise SystemExit(f"компания «{slug}» не найдена")

    if command == "show":
        print(f"Реквизиты компании {tenant.name} ({tenant.slug})")
        missing = []
        for field in FIELDS:
            value = getattr(tenant, field, "")
            mark = "" if value not in ("", None, 0) else "  ← не заполнено"
            if mark:
                missing.append(field)
            print(f"  {TITLES[field]:<18} {value or '—'}{mark}")
        smtp = tenant.smtp or {}
        print(f"\nПочта: {smtp.get('host') or 'не настроена'}"
              + (f":{smtp.get('port')} от {smtp.get('from_email')}" if smtp.get("host") else ""))
        print(f"Префиксы документов: {tenant.doc_prefixes or {'invoice': 'СЧ', 'act': 'АКТ'}}")
        sys.exit(1 if missing else 0)

    if command == "set":
        if not pairs:
            raise SystemExit("укажите пары вида bank_iban=MD00...")
        for pair in pairs:
            key, _, value = pair.partition("=")
            if key not in FIELDS:
                print(f"  пропущено: {key} — такого поля нет")
                continue
            if key in ("invoice_due_days",):
                setattr(tenant, key, int(value or 0))
            elif key in ("vat_rate",):
                setattr(tenant, key, float(str(value).replace(",", ".") or 0))
            else:
                setattr(tenant, key, value)
            print(f"  {TITLES[key]} → {value}")
        db.commit()
        print("Сохранено. Новые счета и акты печатаются с этими реквизитами.")

    elif command == "smtp":
        smtp = dict(tenant.smtp or {})
        for pair in pairs:
            key, _, value = pair.partition("=")
            smtp[key] = int(value) if key == "port" else (value.lower() in ("1", "true", "yes") if key == "tls" else value)
        tenant.smtp = smtp
        db.commit()
        ok, message = test_smtp(tenant)
        print(f"Почта сохранена. Проверка соединения: {message}")
        sys.exit(0 if ok else 1)

    elif command == "mail-test":
        to = sys.argv[2] if len(sys.argv) > 2 else ""
        if not to or "=" in to:
            raise SystemExit("укажите адрес: python tools/company_tool.py mail-test office@dimecon.md")
        rec = send_mail(tenant, to, f"Проверка почты {tenant.name}",
                        "Это проверочное письмо из кабинета компании.")
        print(f"Письмо на {to}: статус «{rec.status}», транспорт «{rec.transport}»"
              + (f", ошибка: {rec.error}" if rec.error else ""))
        sys.exit(0 if rec.status == "sent" else 1)

    elif command == "invoice-preview":
        from portal.services.documents import invoice_pdf
        doc = (db.query(Document).filter_by(tenant_id=tenant.id, type="invoice")
               .order_by(Document.id.desc()).first())
        if not doc:
            raise SystemExit("в компании ещё нет ни одного счёта")
        order = db.get(Order, doc.order_id) if doc.order_id else None
        if order is None:
            order = db.query(Order).filter_by(tenant_id=tenant.id).order_by(Order.id.desc()).first()
        out = Path("../docs/generated") / f"invoice_preview_{tenant.slug}.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(invoice_pdf(tenant, order, doc))
        print(f"Счёт {doc.number} с текущими реквизитами: {out} ({out.stat().st_size} Б)")

    else:
        raise SystemExit(__doc__)
