# ТЗ v2.0 — Том 5. Модель данных и DDL

**СУБД:** PostgreSQL 16 + расширения `uuid-ossp`/`pgcrypto`, `pg_trgm`, `btree_gist`, `postgis`, `ltree`
**ORM:** SQLAlchemy 2.x (typed declarative), миграции — Alembic
**Соглашения:**
- первичные ключи — `uuid` (`gen_random_uuid()`), кроме высокочастотных журналов (`bigserial`);
- все таблицы имеют `created_at timestamptz not null default now()`, `updated_at timestamptz`;
- мягкое удаление бизнес-сущностей — `deleted_at timestamptz`, частичные индексы `where deleted_at is null`;
- денежные суммы — `numeric(14,2)`, валюта — `char(3)`, по умолчанию `'MDL'`;
- многоязычные поля — `jsonb` вида `{"ro": "...", "ru": "...", "en": "..."}`;
- временные интервалы занятости — `tstzrange` с GiST-индексами;
- все внешние ключи — явные, с `on delete` политикой.

---

## 5.1. Расширения и общие типы

```sql
create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists btree_gist;
create extension if not exists postgis;
create extension if not exists ltree;

create type user_type       as enum ('b2c','partner','staff');
create type partner_status  as enum ('lead','active','suspended','closed');
create type equipment_status as enum ('active','maintenance','repair','reserve','written_off');
create type order_status    as enum (
  'draft','submitted','soft_reserved','under_review','quoted','confirmed',
  'scheduled','in_progress','completed','invoiced','paid',
  'cancelled_by_customer','cancelled_by_company','rejected','expired');
create type shift_status    as enum ('draft','submitted','approved','disputed','corrected');
create type task_status     as enum ('open','in_progress','blocked','done','verified');
create type doc_type        as enum ('quote','contract','annex','act','invoice','waybill','permit','shift_report','certificate');
create type outriggers_mode as enum ('full','partial','on_wheels');
create type pin_type        as enum ('crane_setup','pickup','drop','obstacle','power_line','entrance','storage','hazard');
```

---

## 5.2. Пользователи, партнёры, доступ

```sql
create table users (
  id              uuid primary key default gen_random_uuid(),
  email           citext unique,
  phone           text unique,                       -- нормализованный E.164
  password_hash   text,                              -- argon2id, null при входе по OTP
  full_name       text not null,
  locale          char(2) not null default 'ro',
  type            user_type not null,
  is_active       boolean not null default true,
  email_verified_at timestamptz,
  phone_verified_at timestamptz,
  mfa_secret      text,
  last_login_at   timestamptz,
  marketing_consent_at timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz,
  deleted_at      timestamptz,
  constraint users_contact_ck check (email is not null or phone is not null)
);
create index on users using gin (full_name gin_trgm_ops);

create table roles (
  id    smallserial primary key,
  code  text unique not null,
  name  jsonb not null
);
create table user_roles (
  user_id uuid references users(id) on delete cascade,
  role_id smallint references roles(id) on delete cascade,
  primary key (user_id, role_id)
);

create table partners (
  id                 uuid primary key default gen_random_uuid(),
  legal_name         text not null,
  brand_name         text,
  idno               text unique,                    -- фискальный код MD
  vat_code           text,
  legal_address      text,
  postal_address     text,
  bank_details       jsonb,
  status             partner_status not null default 'lead',
  tier_code          text references partner_tiers(code),
  price_list_id      uuid references price_lists(id),
  credit_limit       numeric(14,2) not null default 0,
  payment_terms_days smallint not null default 0,
  deposit_balance    numeric(14,2) not null default 0,
  manager_id         uuid references users(id),
  contract_no        text,
  contract_date      date,
  contract_valid_to  date,
  turnover_12m       numeric(14,2) not null default 0,   -- пересчитывается задачей
  notes              text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz,
  deleted_at         timestamptz
);

create table partner_members (
  id               uuid primary key default gen_random_uuid(),
  partner_id       uuid not null references partners(id) on delete cascade,
  user_id          uuid not null references users(id) on delete cascade,
  role_in_partner  text not null check (role_in_partner in ('admin','foreman','procurement','viewer','accountant')),
  can_see_prices   boolean not null default false,       -- O-3.1
  is_active        boolean not null default true,
  invited_by       uuid references users(id),
  invited_at       timestamptz,
  accepted_at      timestamptz,
  unique (partner_id, user_id)
);

create table partner_invites (
  id           uuid primary key default gen_random_uuid(),
  partner_id   uuid not null references partners(id) on delete cascade,
  email        citext not null,
  role_in_partner text not null,
  token_hash   text not null,
  expires_at   timestamptz not null,
  used_at      timestamptz,
  created_by   uuid references users(id),
  created_at   timestamptz not null default now()
);

create table partner_tiers (
  code             text primary key,                 -- base, bronze, silver, gold, platinum
  name             jsonb not null,
  min_turnover_12m numeric(14,2) not null,
  discount_pct     numeric(5,2) not null default 0,
  payment_terms_days smallint not null default 0,
  priority_weight  smallint not null default 0,      -- приоритет в очереди заявок
  perks            jsonb,                            -- машиночитаемый список привилегий
  sort_order       smallint not null default 0
);
```

---

## 5.3. Парк техники

```sql
create table equipment_categories (
  id          smallserial primary key,
  code        text unique not null,   -- tower_crane, mobile_crane, crawler_crane, semitrailer, tipper, lowbed
  name        jsonb not null,
  icon        text,
  sort_order  smallint not null default 0
);

create table equipment (
  id                 uuid primary key default gen_random_uuid(),
  inventory_no       text unique not null,
  category_id        smallint not null references equipment_categories(id),
  brand              text not null,
  model              text not null,
  year               smallint,
  plate_no           text,
  serial_no          text,
  status             equipment_status not null default 'active',
  home_base_geo      geography(point,4326),
  spec               jsonb not null default '{}',   -- типизированные ТТХ, см. §5.3.1
  slug               jsonb not null,                -- {"ro":"...","ru":"...","en":"..."}
  title              jsonb not null,
  description        jsonb,
  seo                jsonb,
  crew_size          smallint not null default 1,
  transport_required boolean not null default false,
  is_published       boolean not null default false,
  sort_order         smallint not null default 0,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz,
  deleted_at         timestamptz
);
create index on equipment (category_id, status) where deleted_at is null;
create index on equipment using gin (spec jsonb_path_ops);
```

### 5.3.1. Схема `equipment.spec` (валидируется JSON Schema на уровне приложения)

**Краны:**
```json
{
  "capacity_max_t": 100, "radius_max_m": 46, "height_max_m": 68,
  "boom_length_m": 51, "jib_available": true, "jib_length_m": 15,
  "counterweight_t": 40, "axles": 5, "total_weight_t": 60,
  "outrigger_span_a_m": 8.1, "outrigger_span_b_m": 8.1,
  "outrigger_half_width_m": 4.05,
  "min_setup_area_m2": 80, "assembly_time_h": 1.5,
  "power_kw": 370, "fuel_type": "diesel"
}
```

**Транспорт:**
```json
{
  "payload_kg": 63000, "platform_length_mm": 7950, "platform_extend_mm": 4000,
  "platform_width_mm": 2740, "platform_width_extend_mm": 375,
  "platform_height_mm": 860, "axles": 4, "is_lowbed": true,
  "ramp_type": "hydraulic", "tie_down_points": 20, "permit_class": "special"
}
```

### 5.3.2. Грузовые характеристики — ядро подборщика

```sql
create table equipment_load_charts (
  id             bigserial primary key,
  equipment_id   uuid not null references equipment(id) on delete cascade,
  configuration  text not null,              -- 'boom_30m', 'boom_30m_jib_15m', 'cw_40t'
  boom_length_m  numeric(6,2),
  jib_length_m   numeric(6,2),
  counterweight_t numeric(6,2),
  outriggers     outriggers_mode not null default 'full',
  radius_m       numeric(6,2) not null,
  capacity_t     numeric(8,3) not null,
  height_m       numeric(6,2) not null,
  source         text not null,              -- 'passport' | 'manufacturer'
  source_file_id uuid references media(id),
  valid_from     date not null default current_date,
  created_at     timestamptz not null default now(),
  unique (equipment_id, configuration, outriggers, radius_m)
);
create index on equipment_load_charts (equipment_id, outriggers, radius_m, capacity_t desc);
```

**Проверка монотонности [M]** — при импорте и как отложенная проверка:
```sql
-- capacity не должна возрастать при росте вылета в одной конфигурации
create or replace view v_load_chart_anomalies as
select a.equipment_id, a.configuration, a.outriggers, a.radius_m, a.capacity_t,
       b.radius_m as next_radius, b.capacity_t as next_capacity
from equipment_load_charts a
join lateral (
  select * from equipment_load_charts b
  where b.equipment_id = a.equipment_id and b.configuration = a.configuration
    and b.outriggers = a.outriggers and b.radius_m > a.radius_m
  order by b.radius_m limit 1
) b on true
where b.capacity_t > a.capacity_t;
```

### 5.3.3. Документы техники, ТО, экипажи

```sql
create table equipment_documents (
  id           uuid primary key default gen_random_uuid(),
  equipment_id uuid not null references equipment(id) on delete cascade,
  doc_type     doc_type not null,
  number       text,
  issued_at    date,
  valid_until  date,
  file_id      uuid references media(id),
  is_public    boolean not null default false,
  created_at   timestamptz not null default now()
);
create index on equipment_documents (valid_until) where valid_until is not null;

create table maintenance_records (
  id           uuid primary key default gen_random_uuid(),
  equipment_id uuid not null references equipment(id) on delete cascade,
  type         text not null,     -- to1, to2, repair, load_test, diagnostics
  planned_at   date,
  performed_at date,
  hours_meter  numeric(10,1),
  cost         numeric(14,2),
  performer    text,
  next_due_at  date,
  notes        text,
  created_at   timestamptz not null default now()
);

create table crew_members (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid references users(id),
  full_name      text not null,
  role           text not null,     -- operator, rigger, driver
  phone          text,
  photo_id       uuid references media(id),
  certifications jsonb,             -- [{"type":"...","no":"...","valid_until":"2027-05-01"}]
  is_active      boolean not null default true
);
```

### 5.3.4. Доступность — защита от двойного бронирования

```sql
create table equipment_availability (
  id           bigserial primary key,
  equipment_id uuid not null references equipment(id) on delete cascade,
  period       tstzrange not null,
  reason       text not null,        -- order, maintenance, transfer, reserve, soft_reserve
  ref_id       uuid,
  created_at   timestamptz not null default now(),
  -- жёсткие брони не могут пересекаться; мягкие (soft_reserve) исключены из ограничения
  constraint equipment_no_overlap
    exclude using gist (equipment_id with =, period with &&)
    where (reason <> 'soft_reserve')
);
create index on equipment_availability using gist (period);
create index on equipment_availability (equipment_id, reason);
```

**Мягкая бронь** живёт в той же таблице с `reason='soft_reserve'` и снимается Celery-задачей по TTL; она не блокирует жёсткое бронирование, но учитывается при показе доступности как «резерв другого клиента, 1 ч 47 мин».

---

## 5.4. Каталог: услуги, товары, контент

```sql
create table services (
  id            uuid primary key default gen_random_uuid(),
  code          text unique not null,
  slug          jsonb not null,
  title         jsonb not null,
  short_text    jsonb,
  body          jsonb,
  category      text,
  icon          text,
  is_orderable  boolean not null default true,
  pricing_model text not null default 'hourly',   -- hourly, shift, per_km, per_object, on_request
  related_equipment uuid[] default '{}',
  faq           jsonb,        -- [{"q":{...},"a":{...}}]
  seo           jsonb,
  is_published  boolean not null default false,
  sort_order    smallint not null default 0,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz
);

create table product_categories (
  id        uuid primary key default gen_random_uuid(),
  parent_id uuid references product_categories(id),
  path      ltree,
  slug      jsonb not null,
  title     jsonb not null,
  sort_order smallint not null default 0
);
create index on product_categories using gist (path);

create table products (
  id              uuid primary key default gen_random_uuid(),
  sku             text unique not null,
  category_id     uuid references product_categories(id),
  slug            jsonb not null,
  title           jsonb not null,
  description     jsonb,
  attributes      jsonb,            -- диаметр, конструкция, разрывное усилие, ГОСТ/EN, г/п стропа
  unit            text not null default 'pcs',
  price           numeric(14,2),
  currency        char(3) not null default 'MDL',
  vat_rate        numeric(5,2) not null default 20,
  stock_qty       numeric(12,2),
  is_made_to_order boolean not null default false,
  lead_time_days  smallint,
  is_published    boolean not null default false,
  seo             jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz
);
create index on products using gin (attributes jsonb_path_ops);

create table content_pages (
  id        uuid primary key default gen_random_uuid(),
  slug      jsonb not null,
  title     jsonb not null,
  body      jsonb,
  template  text not null default 'default',
  seo       jsonb,
  is_published boolean not null default false,
  updated_at timestamptz
);

create table posts (            -- «Отчёты и события»
  id           uuid primary key default gen_random_uuid(),
  slug         jsonb not null,
  title        jsonb not null,
  excerpt      jsonb,
  body         jsonb,
  cover_id     uuid references media(id),
  tags         text[],
  published_at timestamptz,
  seo          jsonb
);

create table showcases (        -- кейсы
  id          uuid primary key default gen_random_uuid(),
  slug        jsonb not null,
  title       jsonb not null,
  client_name text,
  year        smallint,
  location    text,
  geo         geography(point,4326),
  equipment_used uuid[] default '{}',
  body        jsonb,
  metrics     jsonb,          -- {"weight_t":42,"height_m":38,"hours":6}
  gallery     uuid[] default '{}',
  is_published boolean not null default false
);

create table cargo_presets (    -- пресеты груза для визарда
  id            uuid primary key default gen_random_uuid(),
  code          text unique not null,
  title         jsonb not null,
  hint          jsonb,
  task_types    text[] not null,       -- к каким типам задач относится
  mass_typical_t numeric(8,3) not null,
  mass_min_t    numeric(8,3),
  mass_max_t    numeric(8,3),
  dim_l_m       numeric(6,2),
  dim_w_m       numeric(6,2),
  dim_h_m       numeric(6,2),
  needs_fill_question boolean not null default false,
  icon          text,
  sort_order    smallint not null default 0,
  is_active     boolean not null default true
);

create table materials (        -- для калькулятора массы
  code      text primary key,
  name      jsonb not null,
  density_t_m3 numeric(6,3) not null,
  is_hollow_capable boolean not null default false,
  hollow_fill_ratio numeric(5,3)     -- доля материала для полых объектов
);
```

---

## 5.5. Лиды, заказы, проекты, смены

```sql
create table wizard_sessions (
  token       text primary key,
  payload     jsonb not null default '{}',
  step        smallint not null default 1,
  locale      char(2),
  utm         jsonb,
  user_id     uuid references users(id),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz,
  expires_at  timestamptz not null
);

create table leads (
  id              uuid primary key default gen_random_uuid(),
  source          text not null,      -- wizard, form, phone, chat, api, telegram
  entry_point     text,               -- E1..E9
  channel         text,
  utm             jsonb,
  contact_name    text,
  phone           text,
  email           citext,
  locale          char(2),
  payload         jsonb not null default '{}',
  estimated_min   numeric(14,2),
  estimated_max   numeric(14,2),
  escalated       boolean not null default false,
  escalation_reasons text[],
  status          text not null default 'new',
  assigned_to     uuid references users(id),
  first_response_at timestamptz,      -- для SLA
  converted_order_id uuid,
  created_at      timestamptz not null default now()
);
create index on leads (status, created_at desc);

create table orders (
  id              uuid primary key default gen_random_uuid(),
  number          text unique not null,          -- D-2026-00417
  customer_type   text not null check (customer_type in ('b2c','b2b')),
  user_id         uuid references users(id),
  partner_id      uuid references partners(id),
  project_id      uuid references projects(id),
  service_id      uuid references services(id),
  status          order_status not null default 'draft',
  site_address    text,
  site_geo        geography(point,4326),
  zone_code       text,
  starts_at       timestamptz,
  ends_at         timestamptz,
  duration_hours  numeric(6,2),
  cargo_description text,
  cargo_weight_kg numeric(12,2),
  lift_height_m   numeric(6,2),
  lift_radius_m   numeric(6,2),
  conditions      jsonb not null default '{}',
  price_estimate_min numeric(14,2),
  price_estimate_max numeric(14,2),
  price_final     numeric(14,2),
  vat_amount      numeric(14,2),
  currency        char(3) not null default 'MDL',
  payment_status  text not null default 'none',
  idempotency_key text unique,
  created_by      uuid references users(id),
  cancellation_reason text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz
);
create index on orders (partner_id, status, starts_at);
create index on orders (user_id, created_at desc);
create index on orders using gist (site_geo);

create table order_items (
  id          uuid primary key default gen_random_uuid(),
  order_id    uuid not null references orders(id) on delete cascade,
  kind        text not null,      -- equipment, service, crew, transport, addon, fee, discount
  code        text,
  ref_id      uuid,
  title       jsonb not null,
  explanation jsonb,              -- «4 ч × 1 200 лей»
  qty         numeric(12,3) not null default 1,
  unit        text,
  unit_price  numeric(14,2) not null default 0,
  discount_pct numeric(5,2) not null default 0,
  total       numeric(14,2) not null default 0,
  sort_order  smallint not null default 0
);

create table order_assignments (
  id             uuid primary key default gen_random_uuid(),
  order_id       uuid not null references orders(id) on delete cascade,
  equipment_id   uuid references equipment(id),
  crew_member_id uuid references crew_members(id),
  planned_from   timestamptz,
  planned_to     timestamptz,
  actual_from    timestamptz,
  actual_to      timestamptz,
  status         text not null default 'planned'
);

create table order_status_history (
  id         bigserial primary key,
  order_id   uuid not null references orders(id) on delete cascade,
  from_status order_status,
  to_status  order_status not null,
  actor_id   uuid references users(id),
  comment    text,
  created_at timestamptz not null default now()
);
```

### 5.5.1. Проекты и портал

```sql
create table projects (
  id          uuid primary key default gen_random_uuid(),
  partner_id  uuid not null references partners(id) on delete cascade,
  name        text not null,
  code        text,
  address     text,
  geo         geography(point,4326),
  starts_at   date,
  ends_at     date,
  status      text not null default 'active',
  owner_user_id uuid references users(id),
  dispatcher_id uuid references users(id),        -- закреплённый диспетчер Dimecon
  description text,
  cover_id    uuid references media(id),
  settings    jsonb not null default '{}',        -- require_photo, auto_approve_shifts...
  created_at  timestamptz not null default now(),
  deleted_at  timestamptz
);
create index on projects (partner_id, status);

create table project_members (
  project_id uuid references projects(id) on delete cascade,
  user_id    uuid references users(id) on delete cascade,
  role       text not null,
  notify_prefs jsonb,
  primary key (project_id, user_id)
);

create table project_plans (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  title       text not null,
  file_id     uuid not null references media(id),
  page_count  smallint default 1,
  version     smallint not null default 1,
  scale_m_per_px numeric(10,6),
  is_current  boolean not null default true,
  uploaded_by uuid references users(id),
  created_at  timestamptz not null default now()
);

create table plan_pins (
  id          uuid primary key default gen_random_uuid(),
  plan_id     uuid not null references project_plans(id) on delete cascade,
  page_no     smallint not null default 1,
  x           numeric(8,5) not null,    -- нормализованные координаты 0..1
  y           numeric(8,5) not null,
  type        pin_type not null,
  label       text,
  attributes  jsonb,                    -- покрытие, ширина въезда, напряжение ЛЭП...
  photo_ids   uuid[] default '{}',
  linked_order_id uuid references orders(id),
  linked_task_id  uuid,
  created_by  uuid references users(id),
  created_at  timestamptz not null default now()
);

create table tasks (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  title       text not null,
  description text,
  type        text not null default 'crane_request',
  status      task_status not null default 'open',
  priority    text not null default 'normal',
  assignee_id uuid references users(id),
  due_at      timestamptz,
  linked_order_id uuid references orders(id),
  checklist   jsonb,
  watchers    uuid[] default '{}',
  created_by  uuid references users(id),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz
);

create table order_templates (       -- шаблоны заявок партнёра
  id         uuid primary key default gen_random_uuid(),
  partner_id uuid not null references partners(id) on delete cascade,
  project_id uuid references projects(id) on delete cascade,
  name       text not null,
  payload    jsonb not null,
  use_count  integer not null default 0,
  created_by uuid references users(id),
  created_at timestamptz not null default now()
);

create table shifts (
  id             uuid primary key default gen_random_uuid(),
  order_id       uuid not null references orders(id) on delete cascade,
  project_id     uuid references projects(id),
  equipment_id   uuid references equipment(id),
  crew_member_id uuid references crew_members(id),
  work_date      date not null,
  arrived_at     timestamptz,
  started_at     timestamptz,
  finished_at    timestamptz,
  departed_at    timestamptz,
  hours_worked   numeric(6,2),
  hours_idle     numeric(6,2) default 0,
  idle_reason    text,
  idle_fault     text check (idle_fault in ('customer','company','force_majeure')),
  lifts_count    integer,
  hour_meter_start numeric(10,1),
  hour_meter_end   numeric(10,1),
  odometer_start numeric(10,1),
  odometer_end   numeric(10,1),
  works_done     text,
  notes          text,
  photo_ids      uuid[] default '{}',
  operator_signature_id uuid references media(id),
  customer_signature_id uuid references media(id),
  status         shift_status not null default 'draft',
  submitted_at   timestamptz,
  approved_at    timestamptz,
  approved_by    uuid references users(id),
  dispute_reason text,
  client_uuid    text unique,          -- идемпотентность офлайн-синхронизации
  created_at     timestamptz not null default now(),
  updated_at     timestamptz
);
create index on shifts (project_id, work_date desc);
create index on shifts (status) where status in ('submitted','disputed');
```

---

## 5.6. Тарифы, расчёты, финансы

```sql
create table price_lists (
  id         uuid primary key default gen_random_uuid(),
  code       text unique not null,
  name       jsonb not null,
  partner_id uuid references partners(id),
  currency   char(3) not null default 'MDL',
  valid_from date not null,
  valid_to   date,
  is_default boolean not null default false,
  version    integer not null default 1,
  created_by uuid references users(id),
  created_at timestamptz not null default now()
);

create table price_rules (
  id             uuid primary key default gen_random_uuid(),
  price_list_id  uuid not null references price_lists(id) on delete cascade,
  applies_to     text not null,        -- equipment | category | service | product
  ref_id         uuid,
  hourly_rate    numeric(14,2),
  daily_rate     numeric(14,2),
  monthly_rate   numeric(14,2),
  shift_minimum_hours numeric(5,2) not null default 4,
  idle_hour_rate numeric(14,2),
  travel_hour_rate numeric(14,2),
  mobilization_fee numeric(14,2),
  assembly_fee   numeric(14,2),
  free_radius_km numeric(6,2) not null default 0,
  per_km_rate    numeric(10,2) not null default 0,
  operator_included boolean not null default true,
  fuel_included  boolean not null default true,
  conditions     jsonb
);

create table price_modifiers (        -- K_время, K_сезон, K_условия, K_срочность
  id         uuid primary key default gen_random_uuid(),
  group_code text not null,           -- time, season, conditions, urgency
  code       text not null,
  name       jsonb not null,
  factor     numeric(6,3) not null,
  conditions jsonb,
  valid_from date,
  valid_to   date,
  is_active  boolean not null default true,
  unique (group_code, code)
);

create table service_zones (
  id            uuid primary key default gen_random_uuid(),
  code          text unique not null,
  name          jsonb not null,
  area          geography(multipolygon,4326),
  mobilization_fee numeric(14,2) not null,
  free_radius_km numeric(6,2) not null default 0,
  per_km_rate   numeric(10,2) not null default 0,
  sla_minutes   smallint,
  sort_order    smallint not null default 0
);
create index on service_zones using gist (area);

create table addons (
  id        uuid primary key default gen_random_uuid(),
  code      text unique not null,
  name      jsonb not null,
  unit      text not null,
  price     numeric(14,2) not null,
  is_creditable boolean not null default false,   -- survey зачитывается при заказе
  is_active boolean not null default true
);

create table discounts (
  id         uuid primary key default gen_random_uuid(),
  code       text not null,
  type       text not null,     -- volume, loyalty, flexible_date, repeat_site, promo, referral, contract
  name       jsonb not null,
  value_pct  numeric(5,2),
  value_abs  numeric(14,2),
  partner_id uuid references partners(id),
  conditions jsonb,
  valid_from date,
  valid_to   date,
  usage_limit integer,
  used_count integer not null default 0,
  is_active  boolean not null default true
);

create table price_calculations (      -- воспроизводимость каждой показанной цены
  id            bigserial primary key,
  order_id      uuid references orders(id),
  lead_id       uuid references leads(id),
  engine_version text not null,
  price_list_id uuid references price_lists(id),
  price_list_version integer,
  input         jsonb not null,
  breakdown     jsonb not null,
  total_net     numeric(14,2),
  total_gross   numeric(14,2),
  created_at    timestamptz not null default now()
);

create table pricing_accuracy (        -- факт vs оценка
  id          bigserial primary key,
  order_id    uuid not null references orders(id) on delete cascade,
  estimated   numeric(14,2),
  actual      numeric(14,2),
  deviation_pct numeric(6,2),
  reason      text,
  segment     jsonb,
  created_at  timestamptz not null default now()
);

create table documents (
  id          uuid primary key default gen_random_uuid(),
  type        doc_type not null,
  number      text not null,
  partner_id  uuid references partners(id),
  user_id     uuid references users(id),
  order_id    uuid references orders(id),
  project_id  uuid references projects(id),
  shift_id    uuid references shifts(id),
  issued_at   date not null default current_date,
  due_at      date,
  amount      numeric(14,2),
  paid_amount numeric(14,2) not null default 0,
  currency    char(3) not null default 'MDL',
  status      text not null default 'issued',
  file_id     uuid references media(id),
  external_ref text,                  -- 1С / e-Factura
  created_at  timestamptz not null default now(),
  unique (type, number)
);
create index on documents (partner_id, type, issued_at desc);
create index on documents (status, due_at) where status <> 'paid';

create table payments (
  id           uuid primary key default gen_random_uuid(),
  order_id     uuid references orders(id),
  document_id  uuid references documents(id),
  partner_id   uuid references partners(id),
  provider     text not null,
  provider_ref text,
  amount       numeric(14,2) not null,
  currency     char(3) not null default 'MDL',
  status       text not null,
  paid_at      timestamptz,
  raw_payload  jsonb,
  idempotency_key text unique,
  created_at   timestamptz not null default now()
);

create table deposit_transactions (    -- депозитный кошелёк партнёра
  id         bigserial primary key,
  partner_id uuid not null references partners(id) on delete cascade,
  amount     numeric(14,2) not null,   -- + пополнение, − списание
  balance_after numeric(14,2) not null,
  reason     text not null,
  ref_id     uuid,
  created_by uuid references users(id),
  created_at timestamptz not null default now()
);

create table subscriptions (           -- пакеты часов, сезонные абонементы, сервисные контракты
  id           uuid primary key default gen_random_uuid(),
  partner_id   uuid references partners(id),
  user_id      uuid references users(id),
  type         text not null,          -- hours_package, seasonal, service_contract
  equipment_category_id smallint references equipment_categories(id),
  hours_total  numeric(8,2),
  hours_used   numeric(8,2) not null default 0,
  price        numeric(14,2),
  discount_pct numeric(5,2),
  valid_from   date not null,
  valid_to     date not null,
  status       text not null default 'active',
  created_at   timestamptz not null default now()
);
```

---

## 5.7. Подборщик, SLA, кампании, служебные

```sql
create table selector_log (        -- юридически значимый журнал рекомендаций
  id             bigserial primary key,
  lead_id        uuid references leads(id),
  order_id       uuid references orders(id),
  session_token  text,
  algo_version   text not null,
  input          jsonb not null,
  computed       jsonb not null,    -- m_calc, H_req, R_req
  candidates     jsonb not null,    -- все рассмотренные варианты с обоснованием
  chosen_equipment_id uuid references equipment(id),
  escalated      boolean not null default false,
  escalation_reasons text[],
  created_at     timestamptz not null default now()
);

create table sla_events (
  id          bigserial primary key,
  sla_code    text not null,        -- first_response, arrival_accuracy, replacement, quote_range
  order_id    uuid references orders(id),
  partner_id  uuid references partners(id),
  target_at   timestamptz,
  actual_at   timestamptz,
  is_breached boolean not null default false,
  compensation_amount numeric(14,2) default 0,
  compensation_applied boolean not null default false,
  created_at  timestamptz not null default now()
);
create index on sla_events (sla_code, is_breached, created_at desc);

create table campaigns (
  id          uuid primary key default gen_random_uuid(),
  code        text unique not null,
  name        jsonb not null,
  trigger     jsonb not null,     -- {"event":"order_completed","delay_hours":3}
  audience    jsonb,
  channel     text not null,      -- sms, email, push, task
  template_code text not null,
  is_active   boolean not null default true,
  max_per_month smallint default 2,
  created_at  timestamptz not null default now()
);

create table campaign_sends (
  id          bigserial primary key,
  campaign_id uuid references campaigns(id),
  user_id     uuid references users(id),
  partner_id  uuid references partners(id),
  channel     text not null,
  status      text not null,
  sent_at     timestamptz,
  opened_at   timestamptz,
  clicked_at  timestamptz,
  converted_order_id uuid references orders(id)
);

create table reviews (
  id         uuid primary key default gen_random_uuid(),
  order_id   uuid references orders(id),
  user_id    uuid references users(id),
  rating     smallint not null check (rating between 1 and 5),
  body       text,
  photo_ids  uuid[] default '{}',
  is_published boolean not null default false,
  company_reply text,
  replied_by uuid references users(id),
  created_at timestamptz not null default now()
);

create table churn_signals (
  id         bigserial primary key,
  partner_id uuid references partners(id),
  user_id    uuid references users(id),
  signal     text not null,
  severity   smallint not null default 1,
  details    jsonb,
  handled_by uuid references users(id),
  handled_at timestamptz,
  created_at timestamptz not null default now()
);

create table media (
  id         uuid primary key default gen_random_uuid(),
  file_key   text not null unique,
  mime       text not null,
  size_bytes bigint not null,
  width      integer, height integer,
  checksum   text,
  alt        jsonb,
  variants   jsonb,             -- {"webp":{"800":"key"},"avif":{...}}
  uploaded_by uuid references users(id),
  created_at timestamptz not null default now()
);

create table audit_log (
  id         bigserial primary key,
  actor_id   uuid references users(id),
  entity     text not null,
  entity_id  uuid,
  action     text not null,
  diff       jsonb,
  ip         inet,
  user_agent text,
  created_at timestamptz not null default now()
);
create index on audit_log (entity, entity_id, created_at desc);

create table events (             -- собственная событийная аналитика (§0.8)
  id         bigserial primary key,
  name       text not null,
  user_id    uuid references users(id),
  session_id text,
  params     jsonb,
  locale     char(2),
  device     text,
  created_at timestamptz not null default now()
) partition by range (created_at);

create table redirects (
  id          bigserial primary key,
  from_path   text not null unique,
  to_path     text not null,
  status_code smallint not null default 301,
  hits        integer not null default 0,
  last_hit_at timestamptz
);

create table settings (
  key        text primary key,
  value      jsonb not null,
  updated_by uuid references users(id),
  updated_at timestamptz not null default now()
);

create table feature_flags (
  code       text primary key,
  is_enabled boolean not null default false,
  partner_ids uuid[] default '{}',   -- точечное включение для пилота
  description text,
  updated_at timestamptz
);

create table notifications (
  id         bigserial primary key,
  user_id    uuid references users(id),
  channel    text not null,
  template   text not null,
  payload    jsonb,
  status     text not null default 'queued',
  sent_at    timestamptz,
  read_at    timestamptz,
  created_at timestamptz not null default now()
);
```

---

## 5.8. Изоляция данных партнёров [M]

Помимо фильтрации в сервисном слое — **второй рубеж на уровне БД** через Row Level Security для ключевых таблиц:

```sql
alter table projects enable row level security;
create policy projects_partner_isolation on projects
  using (partner_id = current_setting('app.current_partner_id', true)::uuid);
```

Приложение устанавливает `app.current_partner_id` в начале запроса. Для служебных ролей политика обходится через `bypassrls`-роль. **Требование [M]:** интеграционный тест на каждую защищённую таблицу — «партнёр A не получает ни одной строки партнёра B».

---

## 5.9. Производительность и обслуживание

| Мера | Детали |
|---|---|
| Партиционирование | `events`, `audit_log` — по месяцам; ретеншн 12 мес (`events`), 24 мес (`audit_log`) |
| Материализованные представления | `mv_partner_monthly_spend`, `mv_equipment_utilization` — обновление по расписанию |
| Индексы под подборщик | покрывающий индекс по `equipment_load_charts (equipment_id, outriggers, radius_m, capacity_t desc)` |
| Полнотекстовый поиск | `pg_trgm` по названиям техники, товаров, проектов |
| Бэкапы | ежедневный дамп + WAL-архив (PITR, RPO ≤ 15 мин) |
| Мониторинг | `pg_stat_statements`, алерты на медленные запросы > 500 мс |
| Миграции | expand/contract, обратно совместимые, без блокировок на больших таблицах (`create index concurrently`) |

---

## 5.10. Seed-данные для dev и демо [M]

Фикстуры: 3 языка контента, 12 единиц техники с реальными ТТХ и грузовыми таблицами, 40 пресетов груза, справочник материалов, 14 услуг, 20 товаров, 3 зоны обслуживания, базовый прайс-лист, 5 уровней партнёрства, 2 демо-партнёра с проектами, заявками и сменами, 20 заказов в разных статусах. Команда `flask seed --demo` разворачивает полностью рабочую демо-среду за одну команду — нужна и для разработки, и для демонстраций партнёрам.

---

## 5.11. Чек-лист приёмки Тома 5

- [ ] Все таблицы созданы миграциями Alembic, откат проверен
- [ ] `exclude using gist` предотвращает двойную бронь (тест)
- [ ] Проверка монотонности грузовых таблиц работает при импорте
- [ ] RLS включён на `projects`, `orders`, `shifts`, `documents`, `tasks`, тесты изоляции проходят
- [ ] `price_calculations` позволяет воспроизвести любую показанную цену
- [ ] `selector_log` пишется на каждую выдачу подборщика
- [ ] Партиционирование и ретеншн настроены
- [ ] `flask seed --demo` разворачивает полную демо-среду
- [ ] PITR-восстановление проверено на staging

---

**Далее:** Том 6 — план реализации, оценки, приёмка, эксплуатация.
