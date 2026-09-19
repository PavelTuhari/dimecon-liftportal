"""Проверка адаптера Oracle ERP OfficePlus.

Живой базы здесь нет, поэтому проверяется то, что можно проверить честно:
построение SQL по схеме исходного проекта, пагинация в стиле Oracle 11g,
разбор строк и перенос контрагентов в контакты через общий конвейер импорта.
Подключение имитируется подставным курсором — драйвер и сеть не задействованы.
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal.services import oracle_source as osrc  # noqa: E402

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  {'OK  ' if ok else 'ОШИБКА'} {name}" + (f" — {detail}" if detail else ""))


def norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


# ----------------------------------------------------------------- подставное соединение

# названия намеренно уникальны: в базе платформы уже есть свои компании,
# и тест не должен зависеть от совпадений с ними
COUNTERPARTIES = [
    {"COD": 9001, "NAME": "Alfa Lift Test SRL", "NAMERUS": "Альфа Лифт Тест",
     "GR1": "CLIENTI", "ADRESS": "mun. Chișinău, str. Uzinelor 21", "BANK": "MAIB", "CODFISCAL": "1003600099001"},
    {"COD": 9002, "NAME": "Beta Macara Test SRL", "NAMERUS": "", "GR1": "CLIENTI",
     "ADRESS": "Chișinău, bd. Dacia 47", "BANK": "Victoriabank", "CODFISCAL": "1012600099002"},
    {"COD": 9003, "NAME": "", "NAMERUS": "Гамма Тест Без Названия", "GR1": "", "ADRESS": "", "BANK": "",
     "CODFISCAL": ""},
]
REVENUE = [{"COD": 9001, "DENUMIREA": "Alfa Lift Test SRL", "TOTAL": 125000.0, "DOCS": 14},
           {"COD": 9002, "DENUMIREA": "Beta Macara Test SRL", "TOTAL": 64000.0, "DOCS": 7}]
# отдельная выборка: контрагент, который в платформе уже заведён как партнёр
KNOWN = [{"COD": 9100, "NAME": "Rezidential Grup SRL", "NAMERUS": "", "GR1": "CLIENTI",
          "ADRESS": "Chișinău", "BANK": "MAIB", "CODFISCAL": "1012600012345"}]


class FakeCursor:
    def __init__(self, log):
        self.log = log
        self.description = []
        self._rows = []

    def execute(self, sql, params=None):
        self.log.append((norm(sql), dict(params or {})))
        s = norm(sql).upper()
        if "V$VERSION" in s:
            data, cols = [("Oracle Database 11g Enterprise Edition Release 11.2.0.4.0",)], ["BANNER"]
        elif "COUNT(*) C FROM" in s:
            data, cols = [(1,)], ["C"]
        elif "VMDB_ST201D" in s:
            cols = ["COD", "DENUMIREA", "TOTAL", "DOCS"]
            data = [tuple(r[c] for c in cols) for r in REVENUE]
        elif "PAPI_PARTNER" in s:
            cols = ["ID", "EMAIL", "NAME", "UNIVERS_COD", "ENABLED", "CLIENT_NAME"]
            data = [(1, "b2b@partner.md", "Rezidential", 1002, "1", "Rezidential Grup SRL")]
        else:
            cols = ["COD", "NAME", "NAMERUS", "GR1", "ADRESS", "BANK", "CODFISCAL"]
            rows = COUNTERPARTIES
            m = re.search(r"ROWNUM <= (\d+)\) WHERE RN > (\d+)", s)
            if m:
                hi, lo = int(m.group(1)), int(m.group(2))
                rows = rows[lo:hi]
            data = [tuple(r[c] for c in cols) for r in rows]
        self.description = [(c,) for c in cols]
        self._rows = data

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self):
        self.log = []
        self.closed = False

    def cursor(self):
        return FakeCursor(self.log)

    def close(self):
        self.closed = True


cfg = osrc.OracleConfig(dsn="host:1521/ERP", user="liftportal", password="secret", mode="thick")

print("=== 1. Построение SQL по схеме исходного проекта ===")
sql, params = osrc.sql_counterparties(cfg)
check("контрагенты: TMS_ORG + TMS_UNIVERS с TIP='O'",
      "FROM TMS_ORG o" in sql and "TMS_UNIVERS u ON u.COD = o.COD AND u.TIP = 'O'" in sql, norm(sql)[:110])
check("выбираются название, IDNO, адрес, банк",
      all(c in sql for c in ("u.DENUMIREA AS NAME", "o.CODFISCAL", "o.ADRESS", "o.BANK")))
sql_s, params_s = osrc.sql_counterparties(cfg, search="Grup")
check("поиск по названию и фискальному коду", ":s" in sql_s and params_s["s"] == "%Grup%")

rev, rp = osrc.sql_revenue(cfg, days=180)
check("оборот: продажи отбираются по SYSFID 12280", rp["sysfid"] == 12280 and rp["days"] == 180)
check("оборот считается по VMDB_ST201D и TMDB_DOCS",
      "VMDB_ST201D" in rev and "TMDB_DOCS" in rev and "SUM(l.SUMA)" in rev)
check("архивные контрагенты исключены", "NVL(u.ISARHIV, '0') <> '2'" in rev)

pa, _ = osrc.sql_partner_accounts(cfg)
check("учётные записи Partner API", "PAPI_PARTNER" in pa and "UNIVERS_COD" in pa)

print("\n=== 2. Пагинация Oracle 11g ===")
paged = osrc.page_sql("SELECT 1 FROM DUAL", limit=50, offset=100)
check("используется ROWNUM, без OFFSET/FETCH",
      "ROWNUM <= 150" in paged and "rn > 100" in paged and "OFFSET" not in paged.upper(), norm(paged)[:90])

print("\n=== 3. Префикс схемы ===")
cfg_schema = osrc.OracleConfig(dsn="d", user="u", password="p", schema="OFFICEPLUS")
sql_p, _ = osrc.sql_counterparties(cfg_schema)
check("схема подставляется в имена таблиц",
      "OFFICEPLUS.TMS_ORG" in sql_p and "OFFICEPLUS.TMS_UNIVERS" in sql_p)

print("\n=== 4. Свой SQL вместо штатного ===")
cfg_custom = osrc.OracleConfig(dsn="d", user="u", password="p",
                               sql_counterparties="SELECT COD, DENUMIREA AS NAME FROM MY_VIEW;")
sql_c, _ = osrc.sql_counterparties(cfg_custom)
check("пользовательский запрос принят без точки с запятой", sql_c.endswith("MY_VIEW"), sql_c)

print("\n=== 5. Проверка подключения ===")
conn = FakeConn()
osrc.connect = lambda c: conn          # подменяем только установку соединения
ok, msg = osrc.test_connection(cfg)
check("определяется версия и доступные таблицы", ok and "11g" in msg and "TMS_ORG" in msg, msg[:120])
check("соединение закрывается", conn.closed)

print("\n=== 6. Разбор строк ===")
headers, table = osrc.rows_to_table([{k.lower(): v for k, v in r.items()} for r in COUNTERPARTIES])
check("заголовки и строки собраны", len(headers) == 7 and len(table) == 3, ", ".join(headers))
check("название берётся из DENUMIREA", table[0][0] == "Alfa Lift Test SRL", table[0][0])
check("при пустом DENUMIREA подставляется NAMERUS", table[2][0] == "Гамма Тест Без Названия", table[2][0])
check("IDNO и адрес на своих местах", table[0][1] == "1003600099001" and "Uzinelor" in table[0][2])

print("\n=== 7. Перенос контрагентов в контакты ===")
from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import Contact, Tenant  # noqa: E402

app = create_app()
with app.app_context():
    tenant = db.query(Tenant).filter_by(slug="dimecon").one()
    before = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    conn2 = FakeConn()

    rep = osrc.import_counterparties(tenant, cfg, dry_run=True, limit=10, conn=conn2)
    check("пробное чтение не пишет в базу",
          db.query(Contact).filter_by(tenant_id=tenant.id).count() == before, rep.line())
    check("запрос ушёл с пагинацией", any("ROWNUM" in s for s, _ in conn2.log))

    conn3 = FakeConn()
    rep2 = osrc.import_counterparties(tenant, cfg, dry_run=False, limit=10, with_revenue=True, conn=conn3)
    after = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("контрагенты созданы", rep2.created == 3 and after == before + 3, rep2.line())
    check("запрошен и оборот", any("VMDB_ST201D" in s for s, _ in conn3.log))

    imported = db.query(Contact).filter_by(tenant_id=tenant.id, source="officeplus-oracle").all()
    one = next((c for c in imported if "Alfa Lift" in (c.company or "")), None)
    check("компания и тип B2B", bool(one) and one.kind == "b2b", f"{one.company} / {one.kind}" if one else "")
    check("IDNO сохранён в заметках", bool(one) and "1003600099001" in (one.notes or ""),
          (one.notes or "").replace("\n", " · ")[:80] if one else "")
    check("оборот перенесён", bool(one) and one.revenue == 125000, str(one.revenue) if one else "")
    check("код ERP сохранён для связи", bool(one) and "ID в CRM: 9001" in (one.notes or ""))

    conn4 = FakeConn()
    rep3 = osrc.import_counterparties(tenant, cfg, dry_run=False, limit=10, conn=conn4)
    after2 = db.query(Contact).filter_by(tenant_id=tenant.id).count()
    check("повторный импорт не плодит дубликаты", after2 == after and rep3.updated == 3, rep3.line())

    print("\n=== 8. Контрагент, уже заведённый в платформе ===")
    headers_k, table_k = osrc.rows_to_table([{k.lower(): v for k, v in r.items()} for r in KNOWN])
    from portal.services import crm_import as ci
    rep4 = ci.import_contacts(tenant, headers_k, table_k, dict(osrc.MAPPING), dry_run=False,
                              source_label="officeplus-oracle-known")
    check("опознан по названию компании, новый контакт не создан",
          rep4.updated == 1 and rep4.created == 0, rep4.line())
    check("количество контактов не изменилось",
          db.query(Contact).filter_by(tenant_id=tenant.id).count() == after, str(after))

    db.query(Contact).filter(Contact.tenant_id == tenant.id,
                             Contact.source.in_(["officeplus-oracle", "officeplus-oracle-known"])
                             ).delete(synchronize_session=False)
    db.commit()
    check("тестовые контакты удалены",
          db.query(Contact).filter_by(tenant_id=tenant.id).count() == before,
          f"{db.query(Contact).filter_by(tenant_id=tenant.id).count()} (было {before})")

print(f"\nИТОГО: пройдено {len(passed)}, ошибок {len(failed)}")
for f in failed:
    print("  НЕ ПРОЙДЕНО:", f)
print("\nПримечание: живая база Oracle в этом прогоне не использовалась — проверены построение")
print("запросов, пагинация, разбор строк и перенос. Реальное подключение проверяется кнопкой")
print("«Проверить подключение» в кабинете после ввода пароля.")
sys.exit(1 if failed else 0)
