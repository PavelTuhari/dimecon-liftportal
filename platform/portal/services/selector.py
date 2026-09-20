"""Подбор техники по грузовым характеристикам (Том 1 §1.5) и правила эскалации (§1.6)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..db import SessionLocal
from ..models import Booking, Equipment, LoadChart

K_SAFETY = 1.10
RESERVE_MIN = 0.10
H_CLEAR = 2.0

# Пресеты груза: код -> (название i18n, типовая масса т, макс т, габарит м, высота груза м)
CARGO_PRESETS = [
    ("cabin6",   {"ru": "Бытовка 6 м", "ro": "Vagon 6 m", "en": "Site cabin 6 m"}, 3.0, 4.0, 6.0, 2.5),
    ("cabin12",  {"ru": "Бытовка 12 м", "ro": "Vagon 12 m", "en": "Site cabin 12 m"}, 5.5, 7.0, 12.0, 2.5),
    ("cont20",   {"ru": "Контейнер 20 фт (пустой)", "ro": "Container 20 ft (gol)", "en": "Container 20 ft (empty)"}, 2.3, 2.5, 6.1, 2.6),
    ("cont40",   {"ru": "Контейнер 40 фт (пустой)", "ro": "Container 40 ft (gol)", "en": "Container 40 ft (empty)"}, 3.8, 4.0, 12.2, 2.6),
    ("septic",   {"ru": "Септик / ёмкость", "ro": "Fosă septică / rezervor", "en": "Septic tank"}, 1.5, 2.5, 3.0, 2.0),
    ("pool",     {"ru": "Бассейн композитный", "ro": "Piscină compozit", "en": "Composite pool"}, 1.2, 2.5, 8.0, 1.5),
    ("pallet",   {"ru": "Поддон кирпича/блоков", "ro": "Palet cărămidă/blocuri", "en": "Pallet of bricks"}, 1.5, 1.8, 1.2, 1.2),
    ("slab",     {"ru": "Плита перекрытия", "ro": "Placă de planșeu", "en": "Floor slab"}, 2.5, 4.0, 6.0, 0.3),
    ("ring",     {"ru": "Ж/б кольцо", "ro": "Inel din beton", "en": "Concrete ring"}, 1.0, 2.0, 1.5, 1.0),
    ("truss",    {"ru": "Металлоферма", "ro": "Fermă metalică", "en": "Steel truss"}, 1.8, 4.0, 12.0, 1.5),
    ("hvac",     {"ru": "Кондиционер / чиллер", "ro": "Aer condiționat / chiller", "en": "HVAC unit"}, 0.6, 2.0, 2.0, 1.5),
    ("boiler",   {"ru": "Котёл / генератор", "ro": "Cazan / generator", "en": "Boiler / generator"}, 1.8, 6.0, 3.0, 2.0),
    ("machine",  {"ru": "Станок / оборудование", "ro": "Utilaj / echipament", "en": "Machine tool"}, 3.5, 15.0, 3.0, 2.0),
    ("car",      {"ru": "Автомобиль", "ro": "Automobil", "en": "Car"}, 1.5, 3.5, 4.5, 1.6),
    ("monument", {"ru": "Памятник", "ro": "Monument", "en": "Monument"}, 1.0, 3.0, 1.5, 2.0),
    ("garage",   {"ru": "Гараж металлический", "ro": "Garaj metalic", "en": "Metal garage"}, 1.5, 2.5, 6.0, 2.5),
    ("pole",     {"ru": "Опора / столб", "ro": "Stâlp", "en": "Pole"}, 1.2, 3.0, 9.0, 0.5),
    ("custom",   {"ru": "Знаю точный вес", "ro": "Știu greutatea exactă", "en": "I know the exact weight"}, 0, 0, 2.0, 1.5),
]
PRESET_MAP = {p[0]: p for p in CARGO_PRESETS}

TASK_TYPES = [
    ("lift_height", "⬆️", {"ru": "Поднять груз на высоту", "ro": "Ridicarea la înălțime", "en": "Lift to height"}),
    ("install", "❄️", {"ru": "Установить / снять оборудование", "ro": "Montare / demontare echipament", "en": "Install / remove equipment"}),
    ("unload", "🚚", {"ru": "Разгрузить / загрузить машину", "ro": "Descărcare / încărcare", "en": "Unload / load a truck"}),
    ("place", "🏠", {"ru": "Установить объект на место", "ro": "Amplasarea unui obiect", "en": "Place an object"}),
    ("move_heavy", "🛣", {"ru": "Перевезти тяжёлый груз", "ro": "Transport agabaritic", "en": "Move heavy cargo"}),
    ("construction", "🏗", {"ru": "Работы на стройке (надолго)", "ro": "Lucrări pe șantier", "en": "Long-term construction"}),
    ("other", "❓", {"ru": "Другое / не знаю", "ro": "Altceva / nu știu", "en": "Other / not sure"}),
]

RADIUS_OPTIONS = [
    ("adjacent", 5, {"ru": "Вплотную к месту работ", "ro": "Lângă locul lucrării", "en": "Right next to the spot"}),
    ("sidewalk", 10, {"ru": "Через тротуар / газон", "ro": "Peste trotuar / gazon", "en": "Across a sidewalk"}),
    ("fence", 16, {"ru": "Через забор / соседний участок", "ro": "Peste gard / lot vecin", "en": "Over a fence"}),
    ("building", 24, {"ru": "Через дом / строение", "ro": "Peste o clădire", "en": "Over a building"}),
    ("far", 32, {"ru": "Дальше 25 м", "ro": "Mai mult de 25 m", "en": "More than 25 m"}),
]

HEIGHT_OPTIONS = [(0, "на землю"), (3, "1 этаж"), (6, "2 этаж"), (9, "3 этаж"), (15, "5 этаж"), (28, "9 этаж"), (36, "12 этаж")]

CONDITIONS = [
    ("power_line", {"ru": "Рядом ЛЭП / провода", "ro": "Linii electrice în apropiere", "en": "Power lines nearby"}),
    ("night", {"ru": "Работа ночью", "ro": "Lucru pe timp de noapte", "en": "Night work"}),
    ("weekend", {"ru": "Выходной / праздник", "ro": "Weekend / sărbătoare", "en": "Weekend / holiday"}),
    ("rigger", {"ru": "Нужен стропальщик", "ro": "Este nevoie de legător", "en": "Rigger needed"}),
    ("road_closure", {"ru": "Перекрыть проезжую часть", "ro": "Blocarea drumului", "en": "Road closure needed"}),
    ("tight", {"ru": "Стеснённый двор / арка", "ro": "Curte strâmtă / arcă", "en": "Tight yard / arch"}),
    ("soft_ground", {"ru": "Мягкий грунт", "ro": "Sol moale", "en": "Soft ground"}),
    ("indoor", {"ru": "Работа внутри помещения", "ro": "Lucru în interior", "en": "Indoor work"}),
]


@dataclass
class Candidate:
    equipment: Equipment
    chart: LoadChart | None
    r_req: float
    reserve: float
    available: bool
    next_free: datetime | None = None
    score: float = 0.0
    label: str = ""
    why: str = ""


@dataclass
class Selection:
    m_calc: float
    h_req: float
    candidates: list[Candidate] = field(default_factory=list)
    escalated: bool = False
    reasons: list[str] = field(default_factory=list)


def is_free(eq_id: int, start: datetime, hours: float) -> tuple[bool, datetime | None]:
    end = start + timedelta(hours=hours)
    q = (SessionLocal.query(Booking)
         .filter(Booking.equipment_id == eq_id, Booking.starts_at < end, Booking.ends_at > start)
         .filter(Booking.reason != "soft").order_by(Booking.ends_at.desc()))
    b = q.first()
    return (b is None), (b.ends_at if b else None)


def best_chart(eq: Equipment, r_req: float, m_calc: float, h_req: float) -> LoadChart | None:
    """Ближайшая большая строка по вылету (консервативно), удовлетворяющая Q и H.

    Если у машины загружена паспортная таблица производителя, считаем только по ней:
    смешивать паспорт с ориентировочной кривой нельзя — оценка занижена на 15 %.
    """
    charts = list(eq.load_charts)
    passport = [c for c in charts if (c.source or "") == "passport"]
    rows = [c for c in (passport or charts) if c.radius_m >= r_req]
    ok = [c for c in rows if c.capacity_t >= m_calc and (c.height_m or eq.height_m) >= h_req]
    if not ok:
        return None
    ok.sort(key=lambda c: (c.radius_m, -c.capacity_t))
    return ok[0]


def chart_is_approx(eq: Equipment) -> bool:
    """Подбор по этой машине идёт по оценке, а не по паспорту — повод предупредить клиента."""
    charts = list(eq.load_charts)
    return bool(charts) and not any((c.source or "") == "passport" for c in charts)


def select_equipment(tenant_id: int, *, weight_t: float, height_m: float, offset_m: float, cargo_dim_m: float,
                     cargo_h_m: float, start: datetime, hours: float, conditions: list[str],
                     task_type: str) -> Selection:
    m_rig = max(0.05, 0.10 * weight_t)
    m_calc = round((weight_t + m_rig) * K_SAFETY, 2)
    h_sling = max(1.5, 0.5 * cargo_dim_m)
    h_req = round(height_m + cargo_h_m + h_sling + H_CLEAR, 1)
    sel = Selection(m_calc=m_calc, h_req=h_req)

    fleet = (SessionLocal.query(Equipment)
             .filter_by(tenant_id=tenant_id, is_published=True, status="active").all())
    cranes = [e for e in fleet if e.is_crane]
    fleet_max = max([e.capacity_t for e in cranes], default=0)

    # эскалации
    r = sel.reasons
    if fleet_max and m_calc > 0.6 * fleet_max:
        r.append("Масса груза превышает 60 % возможностей парка — требуется инженерный расчёт")
    if "power_line" in conditions:
        r.append("Работа вблизи ЛЭП: требуется наряд-допуск и согласование")
    if h_req > 40:
        r.append("Высота более 40 м: ветровые нагрузки, требуется схема производства работ")
    if "tight" in conditions or "indoor" in conditions:
        r.append("Стеснённые условия: нужен выезд инженера на осмотр")
    if "road_closure" in conditions:
        r.append("Перекрытие проезжей части: оформление разрешения")
    if "soft_ground" in conditions and m_calc > 20:
        r.append("Мягкий грунт при массе более 20 т: проверка несущей способности основания")
    if "night" in conditions and m_calc > 10:
        r.append("Ночные работы с тяжёлым грузом")
    if task_type in ("other", "construction", "move_heavy"):
        r.append("Задача требует индивидуального расчёта менеджером")
    if weight_t <= 0:
        r.append("Масса груза не определена")

    for eq in cranes:
        r_req = round(offset_m + 0.5 * cargo_dim_m + (eq.outrigger_half_m or 3.5), 1)
        chart = best_chart(eq, r_req, m_calc, h_req) if eq.load_charts else None
        if chart is None:
            # без таблиц — только грубая проверка паспортных максимумов; отдаём с пометкой
            if not eq.load_charts and eq.capacity_t >= m_calc * 1.5 and eq.radius_m >= r_req and eq.height_m >= h_req:
                cap = eq.capacity_t * 0.5
            else:
                continue
        else:
            cap = chart.capacity_t
        reserve = cap / m_calc - 1 if m_calc else 9
        if reserve < RESERVE_MIN:
            continue
        free, nxt = is_free(eq.id, start, hours)
        c = Candidate(eq, chart, r_req, round(reserve, 2), free, nxt)
        price = eq.mobilization_fee + max(hours, eq.min_hours) * eq.hourly_rate
        over = max(0.0, reserve - 2.0)
        c.score = (40 if free else 10) + 30 * (1 / (1 + price / 5000)) + 15 * (1 / (1 + over)) + 10
        c.why = (f"Груз {weight_t:g} т с запасом на строповку и безопасность — расчётная масса {m_calc:g} т. "
                 f"Машина встанет в {offset_m:g} м, расчётный вылет {r_req:g} м: на этом вылете "
                 f"{eq.brand} {eq.model} поднимает до {cap:g} т (запас {round(reserve*100)} %). "
                 f"Требуемая высота {h_req:g} м, машина даёт {(chart.height_m if chart and chart.height_m else eq.height_m):g} м.")
        sel.candidates.append(c)

    sel.candidates.sort(key=lambda c: -c.score)
    if sel.candidates:
        sel.candidates[0].label = "optimal"
        by_price = sorted(sel.candidates, key=lambda c: c.equipment.hourly_rate)
        if by_price[0] is not sel.candidates[0]:
            by_price[0].label = "cheaper"
        bigger = [c for c in sel.candidates if c.equipment.capacity_t > sel.candidates[0].equipment.capacity_t and not c.label]
        if bigger:
            min(bigger, key=lambda c: c.equipment.capacity_t).label = "reserve"
        sel.candidates = [c for c in sel.candidates if c.label][:3]
    if not sel.candidates:
        r.append("В парке нет подходящей техники для автоматического подбора")
    sel.escalated = bool(r)
    return sel


MATERIALS = [("concrete", "Бетон", 2.5), ("brick", "Кирпич", 1.8), ("steel", "Сталь", 7.85), ("wood", "Дерево", 0.6),
             ("water", "Вода", 1.0), ("granite", "Гранит", 2.7), ("soil", "Грунт", 1.7), ("plastic", "Пластик", 0.95)]


def estimate_mass(l: float, w: float, h: float, material: str, hollow: bool) -> tuple[float, float]:
    dens = next((d for c, _, d in MATERIALS if c == material), 1.0)
    vol = max(0.0, l * w * h)
    mass = vol * dens * (0.06 if hollow else 1.0)
    return round(mass * 0.85, 2), round(mass * 1.15, 2)
