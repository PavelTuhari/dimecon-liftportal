"""Сквозной smoke-тест: публичные страницы, роли, изоляция компаний, визард до заявки."""
import re, sys
sys.path.insert(0, ".")
from portal import create_app

app = create_app()
c = app.test_client()
bad = []


def csrf():
    with c.session_transaction() as s:
        return s.get("csrf")


def login(email):
    c.get("/logout")
    r = c.get("/login")
    tok = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True)).group(1)
    return c.post("/login", data={"email": email, "password": "demo1234", "_csrf": tok})


def chk(u, expect=200):
    r = c.get(u, follow_redirects=True)
    mark = "ok " if r.status_code == expect else "BAD"
    if r.status_code != expect:
        bad.append((u, r.status_code))
    print(mark, r.status_code, u)
    return r


print("DB:", app.config["ACTIVE_DB"])

# идентификаторы берём из базы: после переноса контента заказчика фиксированные id недопустимы
with app.app_context():
    from portal.db import SessionLocal as _db
    from portal.models import CaseStudy, Equipment, Order, Page, Service
    EQ = _db.query(Equipment).filter_by(tenant_id=1).order_by(Equipment.id).first()
    SVC = _db.query(Service).filter_by(tenant_id=1).order_by(Service.id).first()
    CASE = _db.query(CaseStudy).filter_by(tenant_id=1).order_by(CaseStudy.id).first()
    PAGE = _db.query(Page).filter_by(tenant_id=1).order_by(Page.id).first()
    ORDER = _db.query(Order).filter_by(tenant_id=1).order_by(Order.id).first()
    EQ_ID, EQ_SLUG = EQ.id, EQ.slug
    SVC_ID, SVC_SLUG = SVC.id, SVC.slug
    CASE_ID, PAGE_ID, ORDER_ID = CASE.id, PAGE.id, ORDER.id
    print(f"тестовые объекты: техника #{EQ_ID} «{EQ_SLUG}», услуга #{SVC_ID}, заявка #{ORDER_ID}")
for u in ["/", "/login", "/register", "/pricing", "/s/dimecon/", "/s/dimecon/equipment", f"/s/dimecon/equipment/{EQ_SLUG}",
          "/s/dimecon/services", f"/s/dimecon/services/{SVC_SLUG}", "/s/dimecon/products", "/s/dimecon/cases", "/s/dimecon/about",
          "/s/dimecon/contacts", "/s/dimecon/partners", "/s/dimecon/p/terms", "/s/dimecon/calculator", "/s/dimecon/account/login",
          "/s/dimecon/account/register", "/s/dimecon/partner/apply", "/s/macara-nord/", "/s/sudlift/?lang=ro", "/s/sudlift/equipment?lang=en", "/api/v1/health"]:
    chk(u)

print("--- owner ---", login("owner@dimecon.md").status_code)
for u in ["/s/dimecon/admin/", "/s/dimecon/admin/orders", "/s/dimecon/admin/orders?view=list&kind=b2b", f"/s/dimecon/admin/orders/{ORDER_ID}",
          "/s/dimecon/admin/contacts", "/s/dimecon/admin/contacts/1", "/s/dimecon/admin/tasks", "/s/dimecon/admin/fleet", "/s/dimecon/admin/fleet/new",
          f"/s/dimecon/admin/fleet/{EQ_ID}", "/s/dimecon/admin/content/services", f"/s/dimecon/admin/content/services/{SVC_ID}", "/s/dimecon/admin/content/products",
          "/s/dimecon/admin/content/products/new", f"/s/dimecon/admin/content/cases/{CASE_ID}", f"/s/dimecon/admin/content/pages/{PAGE_ID}", "/s/dimecon/admin/reviews",
          "/s/dimecon/admin/media", "/s/dimecon/admin/partners", "/s/dimecon/admin/shifts", "/s/dimecon/admin/settings/branding",
          "/s/dimecon/admin/settings/mail", "/s/dimecon/admin/settings/storage", "/s/dimecon/admin/settings/pricing", "/s/dimecon/admin/settings/team",
          "/s/dimecon/admin/integrations", "/s/dimecon/admin/audit", "/s/dimecon/partner/?partner_id=1", "/s/dimecon/partner/projects/1?partner_id=1",
          "/s/dimecon/partner/schedule?partner_id=1", "/s/dimecon/partner/documents?partner_id=1"]:
    chk(u)
chk("/s/macara-nord/admin/", 403)
# смена статуса заказа + выпуск КП
r = c.post(f"/s/dimecon/admin/orders/{ORDER_ID}", data={"_csrf": csrf(), "action": "status", "status": "under_review", "note": "smoke"}, follow_redirects=True)
print("status change", r.status_code, "under_review" in r.get_data(as_text=True))
r = c.post(f"/s/dimecon/admin/orders/{ORDER_ID}", data={"_csrf": csrf(), "action": "document", "doc_type": "quote", "amount": "9000", "send": "1"}, follow_redirects=True)
print("issue quote", r.status_code, "KP-" in r.get_data(as_text=True))
r = c.post(f"/s/dimecon/admin/orders/{ORDER_ID}/stage", data={"stage": "won"}, headers={"X-CSRF": csrf()})
print("kanban drag", r.status_code, r.get_json())

print("--- partner ---", login("partner@example.com").status_code)
for u in ["/s/dimecon/partner/", "/s/dimecon/partner/projects/1", "/s/dimecon/partner/schedule", "/s/dimecon/partner/documents"]:
    chk(u)
chk("/s/dimecon/admin/", 403)
r = c.post("/s/dimecon/partner/projects/1/request", data={"_csrf": csrf(), "equipment_id": str(EQ_ID), "start": "2026-10-06T08:00", "hours": "8",
                                                        "cargo": "smoke", "weight": "2", "repeat_weeks": "2", "distance": "10", "cond": ["rigger"]}, follow_redirects=True)
print("partner request x2", r.status_code, "Создано заявок: 2" in r.get_data(as_text=True))

print("--- client ---", login("client@example.com").status_code)
for u in ["/s/dimecon/account/", f"/s/dimecon/account/orders/{ORDER_ID}", "/s/dimecon/account/profile"]:
    chk(u)
r = c.post(f"/s/dimecon/account/orders/{ORDER_ID}/repeat", data={"_csrf": csrf()}, follow_redirects=True)
print("repeat order -> wizard step6", r.status_code, "Когда и где" in r.get_data(as_text=True))

print("--- platform admin ---", login("admin@platform.local").status_code)
for u in ["/admin", "/admin/mail", "/admin/ddl", "/s/sudlift/admin/", "/s/macara-nord/admin/fleet"]:
    chk(u)

print("--- exports (PDF/XLSX) ---")
for u in ["/s/dimecon/export/orders.xlsx", "/s/dimecon/export/fleet.xlsx", "/s/dimecon/export/pricelist.xlsx",
          "/s/dimecon/export/shifts.xlsx", "/s/dimecon/export/documents.xlsx", "/s/dimecon/export/contacts.xlsx",
          f"/s/dimecon/export/orders/{ORDER_ID}/confirmation.pdf"]:
    chk(u)

print("--- wizard e2e (anonymous) ---")
c.get("/logout"); c.get("/s/dimecon/calculator/reset")


def post(step, data):
    data["_csrf"] = csrf()
    return c.post(f"/s/dimecon/calculator?step={step}", data=data, follow_redirects=True)


post(1, {"task": "place"}); post(2, {"preset": "cabin6", "weight": "3", "qty": "1"}); post(3, {"height": "3"})
post(4, {"radius_code": "fence"}); post(5, {"cond": ["rigger"]})
r = post(6, {"start": "2026-10-01T09:00", "hours": "4", "address": "Chisinau, str. Test 1", "distance": "12", "flex": "1"})
html = r.get_data(as_text=True)
print("result", r.status_code, "offers:", html.count('class="offer '), "escalated:", "Нужен инженер" in html)
m = re.search(r'name="equipment_id" id="eqid" value="(\d+)"', html)
r = c.post("/s/dimecon/calculator/submit", data={"_csrf": csrf(), "equipment_id": m.group(1) if m else "", "name": "Тест Клиент",
                                                "phone": "069 123 456", "email": "test@example.com", "comment": "e2e"}, follow_redirects=True)
num = re.search(r"DIM-\d{4}-\d{5}", r.get_data(as_text=True))
print("submit", r.status_code, num.group(0) if num else "NO NUMBER")
if num:
    chk(f"/s/dimecon/track/{num.group(0)}")
# эскалация: 42 т + ЛЭП
c.get("/s/dimecon/calculator/reset")
post(1, {"task": "lift_height"}); post(2, {"preset": "custom", "weight": "42"}); post(3, {"height": "12"}); post(4, {"radius_code": "far"}); post(5, {"cond": ["power_line"]})
r = post(6, {"start": "2026-10-02T09:00", "hours": "8", "address": "x", "distance": "5"})
print("escalation case:", "Нужен инженер" in r.get_data(as_text=True))
# API
r = c.get("/api/v1/equipment", headers={"X-API-Key": "demo-dimecon-key"}); print("api equipment", r.status_code, len(r.get_json()))
r = c.post("/api/v1/quotes", json={"equipment_id": EQ_ID, "start": "2026-10-01T09:00", "hours": 4, "distance_km": 12}, headers={"X-API-Key": "demo-dimecon-key"})
print("api quote", r.status_code, r.get_json().get("total") if r.status_code == 200 else r.get_data(as_text=True)[:200])
print("api no key", c.get("/api/v1/orders").status_code)
print("\nFAILURES:", bad or "none")
