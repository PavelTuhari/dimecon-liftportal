import io

p = "tools/smoke.py"
s = io.open(p, encoding="utf-8").read()
rep = [
    ('"/s/dimecon/equipment/grove-gmk-5100"', 'f"/s/dimecon/equipment/{EQ_SLUG}"'),
    ('"/s/dimecon/services/crane-services"', 'f"/s/dimecon/services/{SVC_SLUG}"'),
    ('"/s/dimecon/admin/orders/1"', 'f"/s/dimecon/admin/orders/{ORDER_ID}"'),
    ('"/s/dimecon/admin/fleet/3"', 'f"/s/dimecon/admin/fleet/{EQ_ID}"'),
    ('"/s/dimecon/admin/content/services/1"', 'f"/s/dimecon/admin/content/services/{SVC_ID}"'),
    ('"/s/dimecon/admin/content/cases/1"', 'f"/s/dimecon/admin/content/cases/{CASE_ID}"'),
    ('"/s/dimecon/admin/content/pages/1"', 'f"/s/dimecon/admin/content/pages/{PAGE_ID}"'),
    ('"/s/dimecon/admin/orders/1/stage"', 'f"/s/dimecon/admin/orders/{ORDER_ID}/stage"'),
    ('"/s/dimecon/account/orders/1"', 'f"/s/dimecon/account/orders/{ORDER_ID}"'),
    ('"/s/dimecon/account/orders/1/repeat"', 'f"/s/dimecon/account/orders/{ORDER_ID}/repeat"'),
    ('"equipment_id": "3"', '"equipment_id": str(EQ_ID)'),
    ('{"equipment_id": 3,', '{"equipment_id": EQ_ID,'),
]
for a, b in rep:
    s = s.replace(a, b)

marker = 'print("--- wizard e2e (anonymous) ---")'
exports = '''print("--- exports (PDF/XLSX) ---")
for u in ["/s/dimecon/export/orders.xlsx", "/s/dimecon/export/fleet.xlsx", "/s/dimecon/export/pricelist.xlsx",
          "/s/dimecon/export/shifts.xlsx", "/s/dimecon/export/documents.xlsx", "/s/dimecon/export/contacts.xlsx",
          f"/s/dimecon/export/orders/{ORDER_ID}/confirmation.pdf"]:
    chk(u)

''' + marker
if "exports (PDF/XLSX)" not in s:
    s = s.replace(marker, exports)
io.open(p, "w", encoding="utf-8").write(s)
print("patched smoke.py")
