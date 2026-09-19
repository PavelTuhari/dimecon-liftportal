"""Чтение контрагентов и оборотов напрямую из Oracle ERP OfficePlus.

Схема взята из исходного проекта (models/biro26_oracle_store.py, modules/partner/store.py):

    TMS_UNIVERS   универсальный справочник с признаком TIP:
                  'P' — номенклатура, 'O' — организации. Поля: COD, CODVECHI,
                  DENUMIREA (название), NAMERUS (русское название), GR1, UM, ISARHIV
    TMS_ORG       реквизиты организаций: COD, GR1, ADRESS, BANK, CODFISCAL
    PAPI_PARTNER  учётные записи партнёров B2B: EMAIL, NAME, UNIVERS_COD, ENABLED
    VMDB_ST201D   строки документов продаж (SUMA, NRDOC, CTSC)
    TMDB_DOCS     документы; продажи отбираются по SYSFID = 12280

Важно про версию СУБД: ERP работает на Oracle 11g, а thin-режим python-oracledb
поддерживает только 12.1 и новее. Поэтому для 11g обязателен thick-режим
с Oracle Instant Client — путь к нему задаётся в настройках (lib_dir).
Пагинация тоже сделана по-11g: ROWNUM, без OFFSET/FETCH.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import oracledb
except ImportError:  # драйвер ставится опционально
    oracledb = None

SALES_SYSFID = 12280
_thick_initialized = False


class OracleSourceError(RuntimeError):
    pass


@dataclass
class OracleConfig:
    dsn: str = ""                 # host:port/service либо TNS-алиас
    user: str = ""
    password: str = ""
    mode: str = "thick"           # thick для 11g, thin для 12.1+ и Autonomous
    lib_dir: str = ""             # каталог Oracle Instant Client для thick
    wallet_dir: str = ""          # каталог кошелька для Autonomous Database
    schema: str = ""              # префикс схемы, если объекты не в схеме пользователя
    sql_counterparties: str = ""  # необязательная замена штатного запроса

    @classmethod
    def from_tenant(cls, tenant) -> "OracleConfig":
        cfg = (tenant.settings or {}).get("oracle") or {}
        return cls(**{k: cfg.get(k, getattr(cls, k, "")) for k in cls.__dataclass_fields__})

    @property
    def configured(self) -> bool:
        return bool(self.dsn and self.user and self.password)


@dataclass
class OracleReport:
    rows: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)
    dry_run: bool = True

    def line(self) -> str:
        mode = "пробное чтение" if self.dry_run else "импорт"
        return (f"{mode} из Oracle: получено {self.rows}, создано {self.created}, "
                f"обновлено {self.updated}, пропущено {self.skipped}")


# --------------------------------------------------------------------- подключение

def _prefix(cfg: OracleConfig, table: str) -> str:
    return f"{cfg.schema}.{table}" if cfg.schema else table


def connect(cfg: OracleConfig):
    if oracledb is None:
        raise OracleSourceError("не установлен драйвер: pip install oracledb")
    if not cfg.configured:
        raise OracleSourceError("не заданы строка подключения, пользователь или пароль")
    global _thick_initialized
    kwargs: dict[str, Any] = {"user": cfg.user, "password": cfg.password, "dsn": cfg.dsn}
    if cfg.wallet_dir:
        kwargs.update(config_dir=cfg.wallet_dir, wallet_location=cfg.wallet_dir,
                      wallet_password=cfg.password)
    if cfg.mode == "thick" and not _thick_initialized:
        try:
            oracledb.init_oracle_client(lib_dir=cfg.lib_dir or None)
            _thick_initialized = True
        except Exception as exc:  # noqa: BLE001
            raise OracleSourceError(
                "не удалось включить thick-режим (нужен Oracle Instant Client; "
                f"укажите путь в настройках): {exc}") from exc
    try:
        return oracledb.connect(**kwargs)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "DPY-3010" in msg or "not supported" in msg.lower():
            msg += " — похоже, это Oracle 11g: включите thick-режим и укажите Instant Client"
        raise OracleSourceError(msg) from exc


def query(conn, sql: str, params: dict | None = None) -> list[dict]:
    """Результат в виде списка словарей с колонками в нижнем регистре."""
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def page_sql(inner: str, limit: int, offset: int) -> str:
    """Пагинация Oracle 11g: ROWNUM, как в исходном проекте."""
    return (f"SELECT * FROM (SELECT a.*, ROWNUM rn FROM ({inner}) a "
            f"WHERE ROWNUM <= {int(offset) + int(limit)}) WHERE rn > {int(offset)}")


# --------------------------------------------------------------------- запросы

def sql_counterparties(cfg: OracleConfig, search: str = "") -> tuple[str, dict]:
    """Контрагенты: TMS_ORG + название из TMS_UNIVERS (TIP='O')."""
    if cfg.sql_counterparties.strip():
        return cfg.sql_counterparties.strip().rstrip(";"), ({"s": f"%{search}%"} if search else {})
    inner = (f"SELECT o.COD, u.DENUMIREA AS NAME, u.NAMERUS, o.GR1, o.ADRESS, o.BANK, o.CODFISCAL "
             f"FROM {_prefix(cfg, 'TMS_ORG')} o "
             f"LEFT JOIN {_prefix(cfg, 'TMS_UNIVERS')} u ON u.COD = o.COD AND u.TIP = 'O'")
    params: dict[str, Any] = {}
    if search:
        inner += " WHERE UPPER(u.DENUMIREA) LIKE UPPER(:s) OR o.CODFISCAL LIKE :s"
        params["s"] = f"%{search}%"
    inner += " ORDER BY u.DENUMIREA"
    return inner, params


def sql_revenue(cfg: OracleConfig, days: int = 365) -> tuple[str, dict]:
    """Оборот по контрагентам за период: продажи отбираются по SYSFID=12280."""
    sql = (f"SELECT u.COD, u.DENUMIREA, ROUND(SUM(l.SUMA), 2) TOTAL, COUNT(DISTINCT d.COD) DOCS "
           f"FROM {_prefix(cfg, 'VMDB_ST201D')} l "
           f"JOIN {_prefix(cfg, 'TMDB_DOCS')} d ON d.COD = l.NRDOC AND d.SYSFID = :sysfid "
           f"     AND d.DATAMANUAL >= TRUNC(SYSDATE) - :days "
           f"JOIN {_prefix(cfg, 'TMS_UNIVERS')} u ON u.COD = l.CTSC "
           f"WHERE NVL(u.ISARHIV, '0') <> '2' "
           f"GROUP BY u.COD, u.DENUMIREA ORDER BY SUM(l.SUMA) DESC NULLS LAST")
    return sql, {"sysfid": SALES_SYSFID, "days": int(days)}


def sql_partner_accounts(cfg: OracleConfig) -> tuple[str, dict]:
    """Учётные записи Partner B2B API и связанный клиент ERP."""
    sql = (f"SELECT p.ID, p.EMAIL, p.NAME, p.UNIVERS_COD, p.ENABLED, u.DENUMIREA CLIENT_NAME "
           f"FROM {_prefix(cfg, 'PAPI_PARTNER')} p "
           f"LEFT JOIN {_prefix(cfg, 'TMS_UNIVERS')} u ON u.COD = p.UNIVERS_COD "
           f"ORDER BY p.ID")
    return sql, {}


def test_connection(cfg: OracleConfig) -> tuple[bool, str]:
    """Проверка доступа и наличия нужных объектов — для кнопки в кабинете."""
    try:
        conn = connect(cfg)
    except OracleSourceError as exc:
        return False, str(exc)
    try:
        ver = query(conn, "SELECT banner FROM v$version WHERE ROWNUM = 1")
        # имя колонки не фиксируем: у разных версий и драйверов оно отличается
        banner = str(next(iter(ver[0].values()), "Oracle") if ver else "Oracle").strip()
        found = []
        for table in ("TMS_ORG", "TMS_UNIVERS", "PAPI_PARTNER"):
            try:
                query(conn, f"SELECT COUNT(*) c FROM {_prefix(cfg, table)} WHERE ROWNUM <= 1")
                found.append(table)
            except Exception:  # noqa: BLE001
                pass
        missing = {"TMS_ORG", "TMS_UNIVERS", "PAPI_PARTNER"} - set(found)
        note = f"; недоступны: {', '.join(sorted(missing))}" if missing else "; все ожидаемые таблицы на месте"
        return True, f"{banner}; режим {cfg.mode}; доступно: {', '.join(found) or 'ничего'}{note}"
    finally:
        conn.close()


# --------------------------------------------------------------------- перенос

def rows_to_table(rows: list[dict]) -> tuple[list[str], list[list[str]]]:
    """Строки Oracle -> заголовки и значения для общего конвейера импорта CRM."""
    headers = ["Компания", "IDNO", "Адрес", "Группа", "Банк", "Код ERP", "Название (рус)"]
    out = []
    for r in rows:
        out.append([
            str(r.get("name") or r.get("namerus") or ""),
            str(r.get("codfiscal") or ""),
            str(r.get("adress") or ""),
            str(r.get("gr1") or ""),
            str(r.get("bank") or ""),
            str(r.get("cod") or ""),
            str(r.get("namerus") or ""),
        ])
    return headers, out


MAPPING = {0: "company", 1: "idno", 2: "address", 3: "tags", 4: "notes", 5: "external_id", 6: "name"}


def import_counterparties(tenant, cfg: OracleConfig, *, dry_run: bool = True, limit: int = 500,
                          offset: int = 0, search: str = "", with_revenue: bool = False,
                          days: int = 365, conn=None) -> OracleReport:
    """Перенос контрагентов ERP в контакты платформы через общий конвейер импорта."""
    from . import crm_import as ci

    rep = OracleReport(dry_run=dry_run)
    own_conn = conn is None
    conn = conn or connect(cfg)
    try:
        inner, params = sql_counterparties(cfg, search)
        rows = query(conn, page_sql(inner, limit, offset), params)
        rep.rows = len(rows)
        revenue: dict[str, float] = {}
        if with_revenue:
            try:
                sql, p = sql_revenue(cfg, days)
                for r in query(conn, sql, p):
                    revenue[str(r.get("cod"))] = float(r.get("total") or 0)
            except Exception as exc:  # noqa: BLE001
                rep.errors.append(f"оборот не прочитан: {exc}")
        headers, table = rows_to_table(rows)
        if revenue:
            headers.append("Оборот")
            for line, src in zip(table, rows):
                line.append(str(revenue.get(str(src.get("cod")), "")))
        mapping = dict(MAPPING)
        if revenue:
            mapping[len(headers) - 1] = "amount"
        sub = ci.import_contacts(tenant, headers, table, mapping, dry_run=dry_run,
                                 source_label="officeplus-oracle")
        rep.created, rep.updated, rep.skipped = sub.created, sub.updated, sub.skipped
        rep.samples = sub.samples
        rep.errors += sub.errors
        return rep
    finally:
        if own_conn:
            conn.close()
