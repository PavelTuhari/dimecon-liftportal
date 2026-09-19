"""Перенос сайта dimecon.md в платформу: парк, услуги, товары, страницы, контакты, фотографии.

Источник — docs/dimecon_source/content.json (tools/scrape_dimecon.py).

Важная особенность исходного сайта: языковые версии рассинхронизированы — в RU-версии
каталога автокранов 3 машины, в RO — 5, в EN — 4. Перенос объединяет версии по модели,
поэтому в платформу попадает полный парк, а недостающие переводы видны в кабинете.

Скрипт идемпотентный: контент компании dimecon пересобирается целиком,
пользователи, партнёры, контакты и заявки не затрагиваются.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from portal import create_app  # noqa: E402
from portal.db import SessionLocal as db  # noqa: E402
from portal.models import (CaseStudy, Equipment, EquipmentCategory, LoadChart, Media, Page,  # noqa: E402
                           Product, Service, Tenant, i18n)

SRC = json.load(open("../docs/dimecon_source/content.json", encoding="utf-8"))
UPLOADS = Path("uploads/dimecon")
UPLOADS.mkdir(parents=True, exist_ok=True)
LANGS = ("ru", "ro", "en")
downloaded: dict[str, str] = {}
stats = {"photos": 0, "photo_errors": 0}

# ------------------------------------------------------------------ фото

def dl(url: str) -> str:
    """Скачать изображение исходного сайта в хранилище компании, вернуть локальный URL."""
    if not url:
        return ""
    if url in downloaded:
        return downloaded[url]
    parts = urllib.parse.urlsplit(url)
    safe = urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(parts.path), "", ""))
    name = urllib.parse.unquote(parts.path.rsplit("/", 1)[-1])
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")[:80] or "file.jpg"
    path = UPLOADS / name
    if not path.exists():
        try:
            req = urllib.request.Request(safe, headers={"User-Agent": "content-migration/1.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 700:
                raise ValueError(f"слишком маленький файл ({len(data)} Б)")
            path.write_bytes(data)
            stats["photos"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["photo_errors"] += 1
            print(f"   !! фото: {name} — {exc}")
            downloaded[url] = ""
            return ""
    else:
        stats["photos"] += 1
    downloaded[url] = f"/media/dimecon/{name}"
    return downloaded[url]


# ------------------------------------------------------------------ нормализация

CAT_WORDS = re.compile(
    r"(?i)^(автокран|башенный\s+кран|гусеничный\s+кран|кран\s+на\s+рельсовом\s+ходу|полуприцеп|самосвал|"
    r"macara\s+auto|macara\s+turn|macara\s+pe\s+[şs]enile|semiremorc[ăa]|smiremorc[ăa]|autobasculant[ăa]|"
    r"mobile\s+crane|tower\s+crane|crawler\s+crane|semitrailer|dump\s+truck|tipper)\s*")
LOOKALIKE = str.maketrans({"К": "K", "Б": "B", "С": "C", "М": "M", "А": "A", "Т": "T", "Р": "P", "Е": "E",
                           "О": "O", "Х": "H", "Н": "H", "В": "B", "У": "Y", "І": "I", "Ѕ": "S",
                           "Л": "L", "Д": "D", "З": "Z", "Г": "G", "И": "I", "П": "P", "Ф": "F", "Ш": "S"})


def model_key(title: str) -> str:
    """Ключ модели, одинаковый для RU/RO/EN: «Автокран КС-3577» и «Mobile crane KC-3577» -> KC3577."""
    t = CAT_WORDS.sub("", (title or "").strip())
    t = t.split(",")[0].split("/")[0]
    t = t.translate(LOOKALIKE).upper()
    t = re.sub(r"[^A-Z0-9]", "", t)
    return t[:18]


def unify_keys(merged: dict, order: list) -> tuple[dict, list]:
    """Схлопывание записей, где ключ одного языка — часть ключа другого
    («555102» из RU и «MAZ555102» из RO/EN — одна и та же машина)."""
    keys = sorted(order, key=len, reverse=True)
    alias: dict[str, str] = {}
    for short in order:
        for long in keys:
            if short != long and len(short) >= 5 and short in long and long not in alias:
                alias[short] = long
                break
    if not alias:
        return merged, order
    for short, long in alias.items():
        src, dst = merged.pop(short), merged[long]
        for lang, title in src["titles"].items():
            dst["titles"].setdefault(lang, title)
            dst["summaries"].setdefault(lang, src["summaries"].get(lang, ""))
            dst["bodies"].setdefault(lang, src["bodies"].get(lang))
        if len(src["specs"]) > len(dst["specs"]):
            dst["specs"] = src["specs"]
        for img in src["images"]:
            if img not in dst["images"]:
                dst["images"].append(img)
    return merged, [k for k in order if k not in alias]


QRH = {
    "Q": re.compile(r"Q\s*=\s*([\d.,]+)"),
    "R": re.compile(r"R\s*=\s*([\d.,]+)"),
    "H": re.compile(r"H\s*=\s*([\d.,]+)"),
}


def qrh(summary: str) -> dict[str, float]:
    out = {}
    for key, rx in QRH.items():
        m = rx.search(summary or "")
        if m:
            try:
                out[key] = float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return out


def num(text: str):
    nums = [float(x) for x in re.findall(r"\d+(?:[.,]\d+)?", (text or "").replace(",", "."))]
    return max(nums) if nums else None


PAYLOAD_RE = re.compile(r"(?i)(?:грузоподъемность|грузоподъёмность|sarcin[ăa]|capacit\w*)\D{0,24}?(\d[\d\s]{3,7})\s*(?:кг|kg)")


def payload_from_summary(rec: dict) -> float:
    """Грузоподъёмность транспорта из сводки раздела («Грузоподъемность 45000 кг»)."""
    for lang in LANGS:
        m = PAYLOAD_RE.search(rec["summaries"].get(lang) or "")
        if m:
            return float(m.group(1).replace(" ", ""))
    return 0.0


def spec_value(specs, *keywords):
    for row in specs:
        label = " ".join(row[:-1]).lower()
        if all(k in label for k in keywords):
            v = num(row[-1])
            if v:
                return v
    return None


# ------------------------------------------------------------------ объединение языков

def merge_section(tip: str) -> list[dict]:
    """Одна запись на модель, с текстами всех языков, в которых она есть."""
    merged: dict[str, dict] = {}
    order: list[str] = []
    for lang in LANGS:
        for row in SRC["tips"][tip][lang]:
            title = row["title"] or row["list_title"]
            if not title:
                continue
            key = model_key(title)
            if not key:
                continue
            if key not in merged:
                merged[key] = {"key": key, "titles": {}, "summaries": {}, "specs": [], "images": [], "bodies": {}}
                order.append(key)
            rec = merged[key]
            rec["titles"][lang] = title
            rec["summaries"][lang] = row.get("summary", "")
            rec["bodies"][lang] = row
            if len(row["specs"]) > len(rec["specs"]):
                rec["specs"] = row["specs"]
            for img in row["images"]:
                if img not in rec["images"] and re.search(r"\.(jpe?g|png|gif)$", img, re.I):
                    rec["images"].append(img)
    merged, order = unify_keys(merged, order)
    return [merged[k] for k in order]


def merge_by_titles(tip: str, groups: list[dict]) -> list[dict]:
    """Объединение языковых версий по смыслу карточки, а не по её позиции в списке.

    В разделе «Продажи» английская версия сайта заказчика короче русской на одну карточку
    («аренда помещений» по-английски не опубликована). Позиционное объединение из-за этого
    смещало весь английский текст на позицию вверх: у «аренды помещений» оказывалось
    английское название и таблица стальных канатов. Поэтому каждая языковая карточка
    сопоставляется с группой по названию.
    """
    recs = {g["key"]: {"key": f"{tip}-{g['key']}", "group": g, "titles": {}, "summaries": {},
                       "specs": [], "images": [], "bodies": {}} for g in groups}
    order = [g["key"] for g in groups]
    for lang in LANGS:
        for row in SRC["tips"][tip][lang]:
            title = row["title"] or row["list_title"] or ""
            hit = next((g for g in groups if g.get(lang) and re.search(g[lang], title, re.I)), None)
            if hit is None:
                key = f"other-{slugify(title)[:40] or len(recs)}"
                hit = {"key": key, "cat": "В продаже"}
                recs.setdefault(key, {"key": f"{tip}-{key}", "group": hit, "titles": {}, "summaries": {},
                                      "specs": [], "images": [], "bodies": {}})
                if key not in order:
                    order.append(key)
                    print(f"   ! карточка «{title[:50]}» ({lang}) не опознана — вынесена отдельно")
            rec = recs[hit["key"]]
            rec["titles"][lang] = title
            rec["summaries"][lang] = row.get("summary", "")
            rec["bodies"][lang] = row
            if len(row["specs"]) > len(rec["specs"]):
                rec["specs"] = row["specs"]
            for img in row["images"]:
                if img not in rec["images"] and re.search(r"\.(jpe?g|png|gif)$", img, re.I):
                    rec["images"].append(img)
    return [recs[k] for k in order if recs[k]["titles"]]


def merge_by_index(tip: str) -> list[dict]:
    """Для услуг и товаров модель-ключа нет: языковые версии идут одним порядком,
    поэтому сопоставляем по позиции в списке."""
    lengths = {lang: len(SRC["tips"][tip][lang]) for lang in LANGS}
    count = max(lengths.values())
    out = []
    for idx in range(count):
        rec = {"key": f"{tip}-{idx}", "titles": {}, "summaries": {}, "specs": [], "images": [], "bodies": {}}
        for lang in LANGS:
            rows = SRC["tips"][tip][lang]
            if idx >= len(rows):
                continue
            row = rows[idx]
            rec["titles"][lang] = row["title"] or row["list_title"]
            rec["summaries"][lang] = row.get("summary", "")
            rec["bodies"][lang] = row
            if len(row["specs"]) > len(rec["specs"]):
                rec["specs"] = row["specs"]
            for img in row["images"]:
                if img not in rec["images"] and re.search(r"\.(jpe?g|png|gif)$", img, re.I):
                    rec["images"].append(img)
        out.append(rec)
    return out


DRAWING = re.compile(r"(?i)(curbe|grafic|diagram|schem|passport|revista)")
NAMED_PHOTO = re.compile(r"(?i)/\d+[_\- ]")


def rank_images(rec: dict) -> list[str]:
    """Сначала фотографии, затем чертежи и графики.

    На исходном сайте фотографии названы по модели («15_ KS-3577.jpg»), а кривые
    грузоподъёмности и габаритные чертежи выгружены редактором как «image064.jpg».
    """
    def score(url: str) -> tuple:
        name = url.rsplit("/", 1)[-1]
        return (0 if NAMED_PHOTO.search(url) and not DRAWING.search(name) else
                2 if DRAWING.search(name) or re.match(r"(?i)image\d+", name) else 1,)
    return sorted(rec["images"], key=score)


def title_map(rec: dict) -> dict:
    base = rec["titles"].get("ru") or rec["titles"].get("ro") or rec["titles"].get("en") or rec["key"]
    return {lang: rec["titles"].get(lang) or base for lang in LANGS}


def body_map(rec: dict) -> dict:
    """Описание + таблица ТТХ исходного сайта в HTML."""
    out = {}
    for lang in LANGS:
        row = rec["bodies"].get(lang)
        parts = []
        summary = rec["summaries"].get(lang) or rec["summaries"].get("ru") or ""
        if summary:
            parts.append(f"<p><strong>{summary}</strong></p>")
        if row:
            text = [x.strip() for x in row["text"].split("\n") if len(x.strip()) > 45]
            for p in text[:3]:
                if not re.match(r"^[\d\s,./-]+$", p):
                    parts.append(f"<p>{p}</p>")
        specs = (row or {}).get("specs") or rec["specs"]
        if specs:
            parts.append('<table class="specs-table"><tbody>')
            for srow in specs[:24]:
                cells = "".join(f"<td>{c.replace(chr(10), '<br>')}</td>" for c in srow)
                parts.append(f"<tr>{cells}</tr>")
            parts.append("</tbody></table>")
        out[lang] = "\n".join(parts)
    return out


# Бренды, у которых модель отделяется пробелом. Заводские индексы (КС-3577, КБ-408, A-441)
# остаются целиком в поле «модель», чтобы написание совпадало с сайтом заказчика.
BRANDS = ["GROVE GMK", "GROVE", "POTAIN", "COMANSA", "Irmaos Tavares", "FAYMONVILLE", "CMZAP", "RDK",
          "MAZ", "МАЗ", "МАZ", "MAN", "LIEBHERR", "TEREX"]


def split_model(title: str) -> tuple[str, str]:
    t = CAT_WORDS.sub("", (title or "").strip())
    for b in BRANDS:
        if t.upper().startswith(b.upper()):
            rest = t[len(b):].strip(" -–")
            if rest:
                return b, rest
    return "", t


TRANSLIT = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
                          "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
                          "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh",
                          "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
                          "ă": "a", "â": "a", "î": "i", "ș": "s", "ț": "t", "ş": "s", "ţ": "t"})


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower().translate(TRANSLIT)).strip("-")[:110]


# ------------------------------------------------------------------ грузовые характеристики

def approx_chart(cap: float, r_max: float, h_max: float, tower: bool):
    """Ориентировочная кривая до загрузки паспортных таблиц.

    Помечается конфигурацией 'approx': карточка техники и подборщик показывают предупреждение,
    что данные приблизительные. Строится консервативно — с занижением на 15 %.
    """
    if not (cap and r_max):
        return []
    r_min = max(2.5, round(r_max * (0.25 if tower else 0.08), 1))
    moment = cap * r_min * (0.95 if tower else 0.85)
    rows, steps = [], 8
    for i in range(steps + 1):
        r = round(r_min + (r_max - r_min) * i / steps, 1)
        q = round(min(cap, moment / r) * 0.85, 2)
        h = round(h_max if tower else h_max * (1 - 0.45 * (r / r_max) ** 2), 1) if h_max else 0
        rows.append((r, max(q, 0.25), h))
    return rows


CATS = [
    ("mobile_crane", "auto", "crane", 1, ("Автокраны", "Automacarale", "Mobile cranes")),
    ("tower_crane", "turn", "crane", 2, ("Башенные краны", "Macarale turn", "Tower cranes")),
    ("crawler_crane", "senile", "crane", 3, ("Гусеничные краны", "Macarale pe șenile", "Crawler cranes")),
    ("semitrailer", "transport", "transport", 4, ("Транспорт и тралы", "Transport și trailere", "Transport & lowbeds")),
]

RATE_BY_CAP = [(80, 4500, 8, 4000), (40, 2600, 4, 3000), (20, 1600, 4, 2000), (0, 900, 4, 1200)]


def rate_for(cap: float):
    for threshold, rate, minh, mob in RATE_BY_CAP:
        if cap >= threshold:
            return rate, minh, mob
    return 900, 4, 1200


def port_equipment(tenant, cats) -> tuple[int, int, list]:
    total, approx, report = 0, 0, []
    for code, tip, kind, _s, _n in CATS:
        for idx, rec in enumerate(merge_section(tip)):
            titles = title_map(rec)
            brand, model = split_model(titles.get("ru") or titles.get("ro") or titles.get("en"))
            values = {}
            for lang in LANGS:
                values.update({k: v for k, v in qrh(rec["summaries"].get(lang, "")).items() if k not in values})
            eq = Equipment(
                tenant_id=tenant.id, category_id=cats[code].id,
                slug=slugify(f"{brand}-{model}") or f"{code}-{idx}",
                inventory_no=f"{code[:2].upper()}-{idx + 1:02d}", brand=brand, model=model,
                title=titles, description=body_map(rec), is_published=True, sort=idx)
            specs = rec["specs"]
            if kind == "crane":
                eq.capacity_t = values.get("Q") or spec_value(specs, "грузоподъемность", "максимальная") or 0
                eq.radius_m = values.get("R") or spec_value(specs, "вылет", "максимальный") or 0
                eq.height_m = values.get("H") or spec_value(specs, "высота подъема") or 0
                eq.outrigger_half_m = (4.05 if eq.capacity_t >= 80 else 3.6 if eq.capacity_t >= 40
                                       else 3.0 if eq.capacity_t >= 20 else 2.8)
                if code == "tower_crane":
                    eq.hourly_rate, eq.min_hours, eq.mobilization_fee = 0, 0, 45000
                    eq.spec = {"monthly_rate": 95000, "note": "аренда помесячно, монтаж и демонтаж отдельно"}
                else:
                    eq.hourly_rate, eq.min_hours, eq.mobilization_fee = rate_for(eq.capacity_t)
            else:
                payload = (spec_value(specs, "грузоподъемность") or payload_from_summary(rec)
                           or values.get("Q", 0) * 1000)
                eq.payload_kg = payload or 0
                eq.platform_l_mm = spec_value(specs, "длина платформы") or 0
                eq.platform_w_mm = spec_value(specs, "ширина платформы") or 0
                eq.per_km_rate = 45 if payload >= 40000 else 35 if payload >= 20000 else 25
                eq.mobilization_fee = 3000 if payload >= 40000 else 2000
            eq.spec = {**(eq.spec or {}), "source": "dimecon.md", "source_specs": specs[:24],
                       "langs_on_source": sorted(rec["titles"].keys())}
            photos = [p for p in (dl(u) for u in rank_images(rec)[:8]) if p]
            eq.photo_url = photos[0] if photos else ""
            eq.gallery = photos[1:6]
            db.add(eq)
            db.flush()
            for p in photos:
                db.add(Media(tenant_id=tenant.id, backend="local", key=p.rsplit("/", 1)[-1], url=p,
                             filename=p.rsplit("/", 1)[-1], mime="image/jpeg", tags=f"{code},перенос"))
            charts = 0
            if kind == "crane" and eq.capacity_t and eq.radius_m:
                for r, q, h in approx_chart(eq.capacity_t, eq.radius_m, eq.height_m, code == "tower_crane"):
                    db.add(LoadChart(equipment_id=eq.id, configuration="approx", radius_m=r, capacity_t=q, height_m=h))
                    charts += 1
                approx += 1
            total += 1
            report.append({"категория": code, "техника": f"{brand} {model}", "Q_т": eq.capacity_t,
                           "R_м": eq.radius_m, "H_м": eq.height_m, "грузоподъёмность_кг": eq.payload_kg,
                           "фото": len(photos), "строк_ТТХ": len(specs), "кривая": charts,
                           "языки_на_сайте": ",".join(sorted(rec["titles"]))})
            print(f"   + {code:<13} {brand} {model:<26} Q={eq.capacity_t:g} R={eq.radius_m:g} H={eq.height_m:g} "
                  f"кг={eq.payload_kg:g} фото={len(photos)} ТТХ={len(specs)} языки={''.join(sorted(rec['titles']))}")
    return total, approx, report


SERVICE_META = [("🏗", "hourly", 1200), ("🛣", "per_km", 45), ("🔧", "per_object", 15000), ("📅", "shift", 95000),
                ("🏢", "per_object", 8000), ("🔍", "per_object", 4000), ("⚖", "per_object", 6000),
                ("🛠", "hourly", 800), ("💧", "per_object", 2500), ("⚡", "per_object", 1800),
                ("🛤", "per_object", 12000), ("⛓", "per_object", 500), ("📐", "on_request", 0), ("🧰", "on_request", 0)]


def port_services(tenant) -> int:
    rows = merge_by_index("servicii")
    for idx, rec in enumerate(rows):
        titles = title_map(rec)
        icon, model, price = SERVICE_META[idx] if idx < len(SERVICE_META) else ("🏗", "on_request", 0)
        body = body_map(rec)
        short = {lang: (rec["summaries"].get(lang) or re.sub(r"<[^>]+>", " ", body.get(lang, ""))[:170]).strip()
                 for lang in LANGS}
        photos = [p for p in (dl(u) for u in rank_images(rec)[:3]) if p]
        db.add(Service(tenant_id=tenant.id, slug=f"{slugify(titles['ru'])[:70]}-{idx + 1}".strip("-"),
                       code=f"svc{idx + 1:02d}", icon=icon, title=titles, short=short, body=body,
                       price_from=price, pricing_model=model, is_published=True, sort=idx,
                       image_url=photos[0] if photos else ""))
    return len(rows)


# Раздел «Продажи»: соответствие карточек между языковыми версиями сайта заказчика.
# Ключ группы -> как карточка называется в каждой языковой версии (регулярное выражение).
PRODUCT_GROUPS = [
    {"key": "arenda", "cat": "Аренда помещений", "unit": "м²",
     "ru": r"аренд\w*\s+помещ", "ro": r"arend\w*\s+incaperi", "en": r"lease|rent|premis"},
    {"key": "canaty", "cat": "Стальные канаты", "unit": "м",
     "ru": r"стальн\w*\s+канат", "ro": r"cablu\s+de\s+o", "en": r"steel\s*wire\s*rope"},
    {"key": "stropy", "cat": "Грузозахватные приспособления и аксессуары", "unit": "шт",
     "ru": r"грузозахватн", "ro": r"dispozitive\s+pentru\s+ag", "en": r"devices\s+for\s+hanging"},
    {"key": "oborudovanie", "cat": "Оборудование", "unit": "шт",
     "ru": r"^оборудование", "ro": r"^utilaje", "en": r"^equipment"},
    {"key": "zapchasti", "cat": "Запчасти для грузоподъёмных кранов", "unit": "шт",
     "ru": r"запчаст\w*\s+для", "ro": r"piese\s+de\s+schimb", "en": r"spare\s+parts"},
]


def image_size(local_url: str) -> tuple[int, int]:
    """Размер уже скачанного файла; 0×0, если прочитать не удалось."""
    path = UPLOADS.parent / local_url.replace("/media/", "")
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


# Обложкой карточки годится только настоящая фотография. На сайте заказчика в разделе
# «Продажи» лежат иконки 86×92 и 49×337 — в обложке они растягивались в мутное пятно,
# поэтому мелкие изображения показываем миниатюрами рядом с описанием.
COVER_MIN = (320, 240)


def port_products(tenant) -> int:
    rows = merge_by_titles("vinzari", PRODUCT_GROUPS)
    for idx, rec in enumerate(rows):
        grp = rec["group"]
        titles = title_map(rec)
        body = body_map(rec)
        photos = [p for p in (dl(u) for u in rank_images(rec)[:4]) if p]
        covers, thumbs = [], []
        for u in photos:
            w, h = image_size(u)
            (covers if w >= COVER_MIN[0] and h >= COVER_MIN[1] else thumbs).append(u)
        langs = sorted(rec["titles"])
        db.add(Product(tenant_id=tenant.id, sku=f"VZ-{idx + 1:02d}", slug=f"vinzari-{grp['key']}",
                       category=grp["cat"], title=titles, description=body,
                       unit=grp.get("unit", "шт"), price=0, made_to_order=True,
                       is_published=True, image_url=covers[0] if covers else "",
                       attributes={"source": "dimecon.md", "price_note": "цена по запросу",
                                   "langs_on_source": langs,
                                   "photos": covers, "thumbs": thumbs[:4]}))
        missing = [l for l in LANGS if l not in langs]
        print(f"   + VZ-{idx + 1:02d} {grp['cat']:<44} языки={''.join(langs)}"
              + (f"  (нет на сайте: {','.join(missing)})" if missing else ""))
    return len(rows)


def clean_page(html: str) -> str:
    html = re.sub(r"(?is)<a[^>]*>.*?</a>", " ", html)
    lines = [ln.strip() for ln in re.split(r"\n|<br\s*/?>", html) if len(ln.strip()) > 25]
    keep = [ln for ln in lines
            if not re.search(r"(?i)(flash player|swfobject|flashid|javascript|new york|chicago|london|"
                             r"timezone|menu|română|русский|english|\(\-?\+?\d+\)$)", ln)]
    return "\n".join(f"<p>{re.sub(r'<[^>]+>', ' ', ln).strip()}</p>" for ln in keep[:16])


def port_pages(tenant) -> int:
    about = {lang: clean_page(SRC["pages"]["about"][lang]["html"]) for lang in LANGS}
    contacts_txt = {lang: SRC["pages"]["contacts"][lang]["text"] for lang in LANGS}
    tenant.about = about
    db.add(Page(tenant_id=tenant.id, slug="despre-noi", is_published=True, in_menu=False,
                title=i18n("О компании", "Despre noi", "About us"), body=about))
    db.add(Page(tenant_id=tenant.id, slug="contacte", is_published=True, in_menu=False,
                title=i18n("Контакты", "Contacte", "Contacts"),
                body={lang: "<p>" + re.sub(r"\n+", "<br>", contacts_txt[lang].strip()) + "</p>" for lang in LANGS}))
    db.add(Page(tenant_id=tenant.id, slug="terms", is_published=True, in_menu=True,
                title=i18n("Условия аренды", "Condiții de închiriere", "Rental terms"),
                body=i18n("<p>Минимальная смена — 4 часа. Отмена более чем за 24 часа — бесплатно; за 6–24 часа — "
                          "30 % минимальной смены; менее 6 часов — полная минимальная смена и подача. В стоимость "
                          "входят оператор, топливо, подача и возврат техники, страхование гражданской "
                          "ответственности.</p>",
                          "<p>Schimbul minim — 4 ore. Anulare cu peste 24 de ore înainte — gratuit.</p>",
                          "<p>Minimum shift — 4 hours. Cancellation more than 24 hours in advance is free.</p>")))
    return 3


def port_cases(tenant) -> int:
    db.add(CaseStudy(tenant_id=tenant.id, slug="grove-gmk-5100", is_published=True, year=2025, location="Chișinău",
                     title=i18n("Автокран GROVE GMK 5100 — 100 тонн на объекте",
                                "Automacaraua GROVE GMK 5100 — 100 tone pe șantier",
                                "GROVE GMK 5100 — 100 tonnes on site"),
                     body=i18n("<p>Самая мощная машина парка: грузоподъёмность 100 т, вылет выдвинутой стрелы до 46 м, "
                               "высота подъёма до 68 м, гусёк 18 м.</p>"),
                     metrics={"weight_t": 100, "height_m": 68, "hours": 8},
                     image_url=downloaded.get("http://dimecon.md/files/images/image078.jpg", "")))
    db.add(CaseStudy(tenant_id=tenant.id, slug="potain-mc-85b", is_published=True, year=2026, location="Chișinău",
                     title=i18n("Башенный кран POTAIN MC-85B: монтаж и обслуживание",
                                "Macara turn POTAIN MC-85B: montaj și mentenanță",
                                "Tower crane POTAIN MC-85B: assembly and maintenance"),
                     body=i18n("<p>Монтаж, обслуживание и демонтаж башенного крана силами собственной службы "
                               "механизации: подкрановые пути, элементы связи со зданием, освидетельствование.</p>"),
                     metrics={"weight_t": 5, "height_m": 94.5, "hours": 16}))
    return 2


def port_profile(tenant):
    txt = SRC["pages"]["contacts"]["ru"]["text"] + " " + SRC["pages"]["contacts"]["ro"]["text"]
    phones = [re.sub(r"\s+", " ", p).strip() for p in re.findall(r"\+?\s?373[\s\d]{6,14}", txt)]
    emails = re.findall(r"[\w.-]+@[\w.-]+\.\w+", txt)
    seen = []
    for p in phones:
        norm = re.sub(r"\D", "", p)
        if norm not in [re.sub(r"\D", "", x) for x in seen]:
            seen.append(p)
    tenant.phone = seen[0] if seen else tenant.phone
    tenant.phone2 = seen[1] if len(seen) > 1 else ""
    tenant.email = emails[0] if emails else tenant.email
    tenant.settings = {**(tenant.settings or {}), "phones": seen, "source_site": "dimecon.md"}
    tenant.founded_year = 1968
    tenant.legal_name = 'SA «Dimecon 11»'
    tenant.website = "dimecon.md"
    tenant.city = "Chișinău"
    tenant.country = "Moldova"
    tenant.tagline = i18n("Краны до 100 тонн, негабаритные перевозки и обслуживание грузоподъёмных механизмов с 1968 года",
                          "Macarale până la 100 tone, transport agabaritic și mentenanța mașinilor de ridicat din 1968",
                          "Cranes up to 100 tonnes, oversize transport and lifting-equipment maintenance since 1968")
    tenant.hero = {
        "title": i18n("Услуги кранами и негабаритные перевозки по Молдове",
                      "Servicii cu macarale și transport agabaritic în Moldova",
                      "Crane services and oversize transport across Moldova"),
        "subtitle": i18n("Башенные, автомобильные и гусеничные краны, полуприцепы и тралы, монтаж, диагностика и "
                         "освидетельствование грузоподъёмных механизмов. Рассчитайте стоимость онлайн.",
                         "Macarale turn, auto și pe șenile, semiremorci și trailere, montaj, diagnosticare și "
                         "verificarea mașinilor de ridicat. Calculați costul online.",
                         "Tower, mobile and crawler cranes, semitrailers and lowbeds, assembly, diagnostics and "
                         "inspection of lifting machines. Get an online quote."),
    }
    tenant.faq = [
        {"q": i18n("Какую технику вы предоставляете?", "Ce utilaje oferiți?", "What equipment do you offer?"),
         "a": i18n("Башенные краны и краны на рельсовом ходу до 25 т, автокраны до 100 т, гусеничный кран, "
                   "полуприцепы и тралы до 63 т.",
                   "Macarale turn și pe șine până la 25 t, automacarale până la 100 t, macara pe șenile, "
                   "semiremorci și trailere până la 63 t.",
                   "Tower and rail cranes up to 25 t, mobile cranes up to 100 t, a crawler crane, semitrailers "
                   "and lowbeds up to 63 t.")},
        {"q": i18n("Обслуживаете ли вы технику заказчика?", "Deserviți utilajele clientului?",
                   "Do you service customer-owned equipment?"),
         "a": i18n("Да: монтаж и демонтаж, ремонт, диагностика, периодические испытания контрольными грузами, "
                   "техническое освидетельствование, ремонт подкрановых путей и гидрооборудования.",
                   "Da: montaj și demontaj, reparații, diagnosticare, testări periodice, verificare tehnică, "
                   "repararea căilor de rulare și a echipamentului hidraulic.",
                   "Yes: assembly and dismantling, repair, diagnostics, periodic load testing, technical "
                   "inspection, crane runway and hydraulics repair.")},
        {"q": i18n("Что можно купить?", "Ce se poate procura?", "What can be purchased?"),
         "a": i18n("Стальные канаты, грузозахватные приспособления и аксессуары, оборудование, запчасти для "
                   "кранов; изготовление грузозахватных приспособлений под заказ. Также сдаём помещения.",
                   "Cabluri de oțel, dispozitive de prindere și accesorii, echipamente, piese de schimb; "
                   "confecționarea dispozitivelor la comandă. De asemenea, închiriem încăperi.",
                   "Steel ropes, rigging gear and accessories, equipment, crane spare parts; custom-made rigging. "
                   "We also rent out premises.")},
    ]
    tenant.theme = {**(tenant.theme or {}), "accent": "#F5A623", "navy": "#1F3A52"}


def purge(tenant):
    ids = [e.id for e in db.query(Equipment).filter_by(tenant_id=tenant.id).all()]
    if ids:
        db.query(LoadChart).filter(LoadChart.equipment_id.in_(ids)).delete(synchronize_session=False)
    for model in (Equipment, EquipmentCategory, Service, Product, CaseStudy, Page, Media):
        db.query(model).filter_by(tenant_id=tenant.id).delete(synchronize_session=False)
    db.flush()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        tenant = db.query(Tenant).filter_by(slug="dimecon").one()
        print(f"Компания: {tenant.name} (id={tenant.id}), источник: dimecon.md\n")
        # заявки ссылаются на технику — очищаем ссылку, чтобы не потерять историю
        db.execute(__import__("sqlalchemy").text(
            "UPDATE orders SET equipment_id=NULL WHERE tenant_id=:t"), {"t": tenant.id})
        db.execute(__import__("sqlalchemy").text("DELETE FROM bookings WHERE tenant_id=:t"), {"t": tenant.id})
        purge(tenant)
        cats = {}
        for code, _tip, kind, sort, (ru, ro, en) in CATS:
            c = EquipmentCategory(tenant_id=tenant.id, code=code, kind=kind, sort=sort, name=i18n(ru, ro, en))
            db.add(c)
            db.flush()
            cats[code] = c
        print("Техника:")
        eq_total, approx, report = port_equipment(tenant, cats)
        n_services = port_services(tenant)
        n_products = port_products(tenant)
        n_pages = port_pages(tenant)
        n_cases = port_cases(tenant)
        port_profile(tenant)
        db.commit()
        Path("../docs/dimecon_source/ported.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nУслуги: {n_services}\nТовары: {n_products}\nСтраницы: {n_pages}\nКейсы: {n_cases}")
        print(f"Техника: {eq_total} (ориентировочных кривых: {approx})")
        print(f"Фотографии: загружено {stats['photos']}, ошибок {stats['photo_errors']}")
        print(f"Контакты: {tenant.phone} / {tenant.phone2} / {tenant.email}, основана {tenant.founded_year}")
