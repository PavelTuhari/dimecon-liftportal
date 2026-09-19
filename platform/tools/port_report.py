"""Сводка по перенесённому содержимому заказчика — цифры для акта."""
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import text  # noqa: E402

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import CaseStudy, Equipment, LoadChart, Media, Page, Product, Service, Tenant  # noqa: E402

SRC = json.load(open("../docs/dimecon_source/content.json", encoding="utf-8"))
app = create_app()
with app.app_context():
    t = db.query(Tenant).filter_by(slug="dimecon").one()
    eq = db.query(Equipment).filter_by(tenant_id=t.id).all()
    charts = db.execute(text("SELECT COUNT(*) FROM load_charts lc JOIN equipment e ON e.id=lc.equipment_id "
                             "WHERE e.tenant_id=:t"), {"t": t.id}).scalar()
    print("=" * 76)
    print("ПЕРЕНЕСЕНО С dimecon.md")
    print("=" * 76)
    print(f"  техника ................ {len(eq)}")
    print(f"  строк грузовых таблиц .. {charts} (ориентировочные, конфигурация 'approx')")
    print(f"  услуги ................. {db.query(Service).filter_by(tenant_id=t.id).count()}")
    print(f"  товары ................. {db.query(Product).filter_by(tenant_id=t.id).count()}")
    print(f"  страницы ............... {db.query(Page).filter_by(tenant_id=t.id).count()}")
    print(f"  кейсы .................. {db.query(CaseStudy).filter_by(tenant_id=t.id).count()}")
    print(f"  файлы в медиатеке ...... {db.query(Media).filter_by(tenant_id=t.id).count()}")
    print(f"  контакты ............... {t.phone} / {t.phone2} / {t.email}, основана {t.founded_year}")

    print("\nПО КАТЕГОРИЯМ")
    for c in sorted({e.category.code for e in eq if e.category}):
        rows = [e for e in eq if e.category and e.category.code == c]
        name = rows[0].category.name.get("ru")
        print(f"  {name:<22} {len(rows):>2}: " + ", ".join(f"{e.brand} {e.model}".strip() for e in rows))

    print("\nПОЛНОТА ДАННЫХ")
    no_spec = [e for e in eq if not (e.capacity_t or e.payload_kg)]
    no_photo = [e for e in eq if not e.photo_url]
    print(f"  без ТТХ на сайте-источнике: {len(no_spec)} — " + ", ".join(f"{e.brand} {e.model}".strip() for e in no_spec))
    print(f"  без фотографии ...........: {len(no_photo)}")
    for lang in ("ru", "ro", "en"):
        filled = sum(1 for e in eq if (e.title or {}).get(lang))
        print(f"  названий на «{lang}» ........: {filled} из {len(eq)}")

    print("\nРАССИНХРОН ЯЗЫКОВ НА ИСХОДНОМ САЙТЕ (карточек в разделе)")
    for tip in ("auto", "turn", "senile", "transport", "servicii", "vinzari", "noutati"):
        n = {lang: len(SRC["tips"][tip][lang]) for lang in ("ru", "ro", "en")}
        flag = "  <-- расходится" if len(set(n.values())) > 1 else ""
        print(f"  {tip:<10} RU={n['ru']:>2}  RO={n['ro']:>2}  EN={n['en']:>2}{flag}")
