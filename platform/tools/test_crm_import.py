"""Проверка импорта из внешней CRM: распознавание колонок, кодировки, дедупликация, идемпотентность."""
from __future__ import annotations

import io
import re
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from openpyxl import Workbook  # noqa: E402

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Contact, Tenant  # noqa: E402
from portal.services import crm_import as ci  # noqa: E402

app = create_app()
passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  {'OK  ' if ok else 'ОШИБКА'} {name}" + (f" — {detail}" if detail else ""))


# телефоны и адреса намеренно уникальны, чтобы тест не цеплялся за реальные контакты базы
CSV_RU = """Имя;Компания;Телефон;E-mail;Оборот;Теги;Менеджер
Ион Плэмэдялэ;Constructor Grup SRL;069900101;ion@crmtest.md;125000;vip, стройка;Петров
Мария Урсу;;069900102;maria@crmtest.md;18500;частник;Иванов
Sergiu Rusu;Rusu Trans SRL;+373 79 900 103;office@crmtest.md;64000;;Петров
"""

CSV_EN = """Contact,Company,Phone,Email,Revenue,City
John Doe,BuildCo,069900101,ion@crmtest.md,5000,Chisinau
New Client,NewCo SRL,069900104,new@crmtest.md,9000,Balti
"""

print("=== 1. Разбор файлов ===")
h, rows = ci.read_table(CSV_RU.encode("utf-8"), "crm.csv")
check("CSV utf-8 с разделителем ;", len(h) == 7 and len(rows) == 3, f"{len(h)} колонок, {len(rows)} строк")
h_cp, rows_cp = ci.read_table(CSV_RU.encode("cp1251"), "crm_win.csv")
check("CSV в кодировке cp1251", h_cp[0] == "Имя" and len(rows_cp) == 3, f"первый заголовок: {h_cp[0]}")
h_en, rows_en = ci.read_table(CSV_EN.encode("utf-8"), "crm_en.csv")
check("CSV с разделителем ,", len(h_en) == 6 and len(rows_en) == 2, f"{len(h_en)} колонок")

wb = Workbook()
ws = wb.active
ws.append(["ФИО", "Организация", "Мобильный", "Почта", "Сумма сделок"])
ws.append(["Виктор Чеботарь", "Cebotari SRL", "069900105", "v@crmtest.md", "43 500,50"])
buf = io.BytesIO()
wb.save(buf)
h_x, rows_x = ci.read_table(buf.getvalue(), "crm.xlsx")
check("Excel XLSX", len(h_x) == 5 and rows_x[0][0] == "Виктор Чеботарь", f"{len(rows_x)} строк")

print("\n=== 2. Распознавание колонок ===")
m = ci.detect_mapping(h)
check("русские заголовки распознаны", set(m.values()) >= {"name", "company", "phone", "email", "amount"},
      ", ".join(f"{h[i]}→{v}" for i, v in sorted(m.items())))
m_en = ci.detect_mapping(h_en)
check("английские заголовки распознаны", set(m_en.values()) >= {"name", "company", "phone", "email"},
      ", ".join(f"{h_en[i]}→{v}" for i, v in sorted(m_en.items())))
m_x = ci.detect_mapping(h_x)
check("синонимы (ФИО, Организация, Мобильный, Почта)", set(m_x.values()) >= {"name", "company", "phone", "email"},
      ", ".join(f"{h_x[i]}→{v}" for i, v in sorted(m_x.items())))

print("\n=== 3. Разбор сумм ===")
for raw, expect in [("125000", 125000.0), ("43 500,50", 43500.5), ("1 234.56", 1234.56),
                    ("12 000 MDL", 12000.0), ("", 0.0)]:
    got = ci.parse_amount(raw)
    check(f"сумма «{raw}» -> {expect}", abs(got - expect) < 0.01, str(got))

with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    before = db.query(Contact).filter_by(tenant_id=tenant.id).count()

    print("\n=== 4. Пробный прогон (данные не пишутся) ===")
    rep = ci.import_contacts(tenant, h, rows, m, dry_run=True, source_label="crm-test")
    after_dry = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("строки обработаны", rep.total == 3, rep.line())
    check("база не изменилась", after_dry == before, f"{before} -> {after_dry}")

    print("\n=== 5. Импорт ===")
    rep1 = ci.import_contacts(tenant, h, rows, m, dry_run=False, source_label="crm-test")
    after = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("контакты созданы", rep1.created == 3, rep1.line())
    imported = db.query(Contact).filter_by(tenant_id=tenant.id, source="crm-test").all()
    ion = next((c for c in imported if "Ион" in c.name), None)
    check("телефон нормализован в E.164", bool(ion) and ion.phone.startswith("+373"), ion.phone if ion else "не найден")
    check("компания и тип B2B определены", bool(ion) and ion.kind == "b2b" and "Constructor" in ion.company,
          f"{ion.kind}, {ion.company}" if ion else "")
    check("оборот перенесён", bool(ion) and ion.revenue == 125000, str(ion.revenue) if ion else "")
    check("менеджер CRM сохранён в заметках", bool(ion) and "Петров" in (ion.notes or ""), (ion.notes or "")[:60] if ion else "")

    print("\n=== 6. Повторный импорт того же файла ===")
    rep2 = ci.import_contacts(tenant, h, rows, m, dry_run=False, source_label="crm-test")
    after2 = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("дубликаты не созданы", after2 == after, f"{after} -> {after2}, обновлено {rep2.updated}")

    print("\n=== 7. Дедупликация по e-mail из другой CRM ===")
    rep3 = ci.import_contacts(tenant, h_en, rows_en, m_en, dry_run=False, source_label="crm-en")
    after3 = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("совпадение по e-mail найдено (John Doe = Ион Плэмэдялэ)", rep3.updated >= 1,
          f"создано {rep3.created}, обновлено {rep3.updated}")
    check("новый контакт добавлен", after3 == after2 + 1, f"{after2} -> {after3}")

    print("\n=== 8. Импорт истории сделок ===")
    from portal.models import Order
    orders_before = db.query(Order).filter_by(tenant_id=tenant.id).count()
    rep4 = ci.import_contacts(tenant, h_x, rows_x, m_x, dry_run=False, source_label="crm-hist", create_orders=True)
    orders_after = db.query(Order).filter_by(tenant_id=tenant.id).count()
    check("заявка создана из оборота", orders_after == orders_before + 1 and rep4.orders == 1,
          f"{orders_before} -> {orders_after}")

    print("\n=== 9. Очистка тестовых данных ===")
    n = db.query(Contact).filter(Contact.tenant_id == tenant.id,
                                 Contact.source.in_(["crm-test", "crm-en", "crm-hist"])).count()
    db.query(Order).filter(Order.tenant_id == tenant.id, Order.source.in_(["crm-hist"])).delete(synchronize_session=False)
    db.query(Contact).filter(Contact.tenant_id == tenant.id,
                             Contact.source.in_(["crm-test", "crm-en", "crm-hist"])).delete(synchronize_session=False)
    db.commit()
    final = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("тестовые записи удалены", final == before, f"{n} удалено, осталось {final} (было {before})")

print(f"\nИТОГО: пройдено {len(passed)}, ошибок {len(failed)}")
for f in failed:
    print("  НЕ ПРОЙДЕНО:", f)
sys.exit(1 if failed else 0)
