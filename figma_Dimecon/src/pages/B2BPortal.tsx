import { useState } from 'react'

const DARK = {
  bg: '#0F1214',
  subtle: '#171B1E',
  raised: '#1E2327',
  sunken: '#0A0C0E',
  text: '#F2F4F5',
  secondary: '#A3ADB4',
  muted: '#6F7A81',
  border: '#2C3338',
  borderStrong: '#3D454B',
}

const ATTENTION_ITEMS = [
  { type: 'invoice', icon: '📄', text: 'Счёт №INV-2024-089 на 18 400 lei ожидает оплаты', action: 'Оплатить', color: '#C77700', due: 'до 25 сент' },
  { type: 'report', icon: '📋', text: '3 сменных рапорта ожидают вашего подтверждения', action: 'Подтвердить', color: '#2D6CB5', due: '2 просрочено' },
  { type: 'conflict', icon: '⚠️', text: 'Конфликт техники: LTM 1070 — 2 заявки на 24 сент', action: 'Разрешить', color: '#C0392B', due: 'срочно' },
]

const ORDERS = [
  { id: 'ORD-2024-142', crane: 'LTM 1070-4.2', date: '20.09.2024', time: '08:00', site: 'ЖК Panorama', hours: 8, status: 'active', statusLabel: 'Выполняется' },
  { id: 'ORD-2024-141', crane: 'Potain MCT 88', date: '19.09.2024', time: '07:30', site: 'Завод «Нова»', hours: 12, status: 'done', statusLabel: 'Завершена' },
  { id: 'ORD-2024-140', crane: 'LTM 1100-5.2', date: '24.09.2024', time: '09:00', site: 'Мост трассы R2', hours: 16, status: 'confirmed', statusLabel: 'Подтверждена' },
  { id: 'ORD-2024-139', crane: 'LTM 1070-4.2', date: '26.09.2024', time: '08:00', site: 'ЖК Panorama', hours: 8, status: 'draft', statusLabel: 'Черновик' },
  { id: 'ORD-2024-138', crane: 'Grove GMK3060', date: '01.10.2024', time: '07:00', site: 'Элеватор Оргеев', hours: 24, status: 'submitted', statusLabel: 'Отправлена' },
]

const STATUS_STYLES: Record<string, { bg: string; color: string; border?: string }> = {
  active: { bg: 'rgba(46,125,79,0.2)', color: '#4CAF7D', border: undefined },
  done: { bg: 'rgba(90,100,107,0.2)', color: '#A3ADB4', border: undefined },
  confirmed: { bg: 'rgba(45,108,181,0.2)', color: '#5A9BE0', border: undefined },
  draft: { bg: 'transparent', color: '#6F7A81', border: `1px dashed #3D454B` },
  submitted: { bg: 'rgba(31,58,82,0.3)', color: '#A3ADB4', border: `1px solid #2C3338` },
  conflict: { bg: 'rgba(192,57,43,0.2)', color: '#E5665A', border: undefined },
}

const GANTT_DAYS = ['Пн 18', 'Вт 19', 'Ср 20', 'Чт 21', 'Пт 22', 'Сб 23', 'Вс 24', 'Пн 25']
const GANTT_DATA = [
  { crane: 'LTM 1070-4.2', blocks: [{ start: 2, span: 1, status: 'active', label: 'ЖК Panorama' }, { start: 4, span: 2, status: 'confirmed', label: 'Мост R2' }, { start: 6, span: 1, status: 'conflict', label: 'КОНФЛИКТ' }] },
  { crane: 'LTM 1100-5.2', blocks: [{ start: 1, span: 3, status: 'done', label: 'Элеватор' }, { start: 5, span: 2, status: 'confirmed', label: 'Завод' }] },
  { crane: 'Potain MCT 88', blocks: [{ start: 0, span: 7, status: 'active', label: 'ЖК Panorama (монтаж)' }] },
  { crane: 'Grove GMK3060', blocks: [{ start: 3, span: 1, status: 'submitted', label: 'Элеватор' }] },
]

const NAV_ITEMS = [
  { icon: '⬛', label: 'Обзор', active: true },
  { icon: '📁', label: 'Проекты' },
  { icon: '📋', label: 'Заявки' },
  { icon: '📅', label: 'Календарь' },
  { icon: '🔩', label: 'График техники' },
  { icon: '🗺️', label: 'Plan объекта' },
  { icon: '📊', label: 'Смены и рапорты' },
  { icon: '📄', label: 'Счета' },
  { icon: '📈', label: 'Аналитика' },
  { icon: '⚙️', label: 'Настройки' },
]

const METRICS = [
  { label: 'Расход за сентябрь', value: '84 200 lei', delta: '+12%', bad: true },
  { label: 'Машино-часов', value: '312 ч', delta: '−8 ч от плана', bad: false },
  { label: 'Простои', value: '4,2 ч', delta: 'по вине заказчика', bad: false },
  { label: 'SLA подачи', value: '97,3%', delta: '↑ от 94%', bad: false },
]

export default function B2BPortal() {
  const [activeNav, setActiveNav] = useState(0)
  const [activeTab, setActiveTab] = useState<'orders' | 'gantt'>('orders')
  const [dark] = useState(true)

  const bg = DARK

  return (
    <div style={{ fontFamily: 'Manrope, sans-serif', background: bg.bg, color: bg.text, minHeight: '100vh', display: 'flex' }}>
      {/* Sidebar */}
      <aside style={{ width: 220, background: bg.sunken, borderRight: `1px solid ${bg.border}`, display: 'flex', flexDirection: 'column', flexShrink: 0, position: 'sticky', top: 40, height: 'calc(100vh - 40px)' }}>
        {/* Logo */}
        <div style={{ padding: '20px 16px', borderBottom: `1px solid ${bg.border}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 28, height: 28, background: '#F5A623', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#14181B' }}>D</span>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 800, color: bg.text }}>DIMECON</div>
            <div style={{ fontSize: 10, color: bg.muted, fontWeight: 500 }}>Партнёрский портал</div>
          </div>
        </div>

        {/* Project selector */}
        <div style={{ padding: '12px 12px 8px' }}>
          <button style={{ width: '100%', padding: '8px 10px', background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: 11, color: bg.muted, fontWeight: 500 }}>Проект</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: bg.text }}>ЖК Panorama</div>
            </div>
            <span style={{ color: bg.muted, fontSize: 10 }}>▼</span>
          </button>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '4px 8px', overflowY: 'auto' }}>
          {NAV_ITEMS.map((item, i) => (
            <button key={i} onClick={() => setActiveNav(i)} style={{
              width: '100%', padding: '8px 10px', borderRadius: 5, border: 'none',
              background: activeNav === i ? '#1F3A52' : 'transparent',
              color: activeNav === i ? '#F2F4F5' : bg.secondary,
              display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
              fontFamily: 'Manrope, sans-serif', fontSize: 13, fontWeight: activeNav === i ? 600 : 400,
              marginBottom: 2, textAlign: 'left',
            }}>
              <span style={{ fontSize: 14 }}>{item.icon}</span>
              {item.label}
              {item.label === 'Заявки' && (
                <span style={{ marginLeft: 'auto', background: '#C0392B', color: '#fff', borderRadius: 10, padding: '1px 6px', fontSize: 10, fontWeight: 700 }}>3</span>
              )}
            </button>
          ))}
        </nav>

        {/* User */}
        <div style={{ padding: '12px 12px', borderTop: `1px solid ${bg.border}` }}>
          {/* Tier progress */}
          <div style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 8, padding: '10px 12px', marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#F5A623' }}>🥈 SILVER</span>
              <span style={{ fontSize: 10, color: bg.muted }}>→ GOLD</span>
            </div>
            <div style={{ height: 4, background: bg.border, borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: '65%', height: '100%', background: '#F5A623', borderRadius: 2 }} />
            </div>
            <div style={{ fontSize: 10, color: bg.muted, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>65 000 / 100 000 lei · −8% на тариф</div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#1F3A52', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: '#F5A623', flexShrink: 0 }}>
              АП
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: bg.text }}>Андрей Попеску</div>
              <div style={{ fontSize: 10, color: bg.muted }}>Прораб · SC Conslux</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto' }}>
        {/* Top bar */}
        <div style={{ padding: '16px 24px', borderBottom: `1px solid ${bg.border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: bg.subtle, position: 'sticky', top: 40, zIndex: 10 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: bg.text, margin: 0, letterSpacing: '-0.02em' }}>Обзор · ЖК Panorama</h1>
            <div style={{ fontSize: 12, color: bg.muted, marginTop: 2 }}>Пятница, 20 сентября 2024 · Кишинёв</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button style={{ padding: '7px 14px', background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 5, color: bg.secondary, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
              + Создать заявку
            </button>
            <button style={{ padding: '7px 16px', background: '#F5A623', border: 'none', borderRadius: 5, color: '#14181B', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
              Быстрая бронь
            </button>
            {/* Dispatcher card */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 12px', background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 6 }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#2A4F6E', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#F5A623', flexShrink: 0 }}>
                МД
              </div>
              <div>
                <div style={{ fontSize: 11, color: bg.muted }}>Диспетчер</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: bg.text }}>Михаил Думу</div>
              </div>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#4CAF7D' }} className="pulse-dot" />
            </div>
          </div>
        </div>

        <div style={{ padding: 24 }}>
          {/* Attention row */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: bg.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 10 }}>ТРЕБУЕТ ВНИМАНИЯ</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {ATTENTION_ITEMS.map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 8, borderLeft: `3px solid ${item.color}` }}>
                  <span style={{ fontSize: 16 }}>{item.icon}</span>
                  <span style={{ fontSize: 13, color: bg.text, flex: 1 }}>{item.text}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: item.color, background: `${item.color}22`, padding: '2px 8px', borderRadius: 4, whiteSpace: 'nowrap' }}>{item.due}</span>
                  <button style={{ padding: '5px 12px', background: item.color, border: 'none', borderRadius: 4, color: '#fff', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', whiteSpace: 'nowrap' }}>
                    {item.action}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
            {METRICS.map((m, i) => (
              <div key={i} style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 8, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: bg.muted, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>{m.label}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: bg.text, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>{m.value}</div>
                <div style={{ fontSize: 11, color: m.bad ? '#E5665A' : '#4CAF7D', marginTop: 4, fontWeight: 600 }}>{m.delta}</div>
              </div>
            ))}
          </div>

          {/* Orders / Gantt tabs */}
          <div style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ borderBottom: `1px solid ${bg.border}`, display: 'flex', gap: 0 }}>
              {(['orders', 'gantt'] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  padding: '12px 20px', border: 'none', background: 'transparent',
                  color: activeTab === tab ? bg.text : bg.muted,
                  fontSize: 13, fontWeight: activeTab === tab ? 700 : 400,
                  cursor: 'pointer', fontFamily: 'Manrope, sans-serif',
                  borderBottom: activeTab === tab ? `2px solid #F5A623` : '2px solid transparent',
                  marginBottom: -1,
                }}>
                  {tab === 'orders' ? '📋 Заявки' : '📅 График техники'}
                </button>
              ))}
              <div style={{ flex: 1 }} />
              <div style={{ padding: '8px 16px', display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="search" placeholder="Поиск…" style={{ padding: '5px 10px', background: bg.sunken, border: `1px solid ${bg.border}`, borderRadius: 4, color: bg.text, fontSize: 12, fontFamily: 'Manrope, sans-serif', width: 140 }} />
                <button style={{ padding: '5px 12px', background: bg.sunken, border: `1px solid ${bg.border}`, borderRadius: 4, color: bg.secondary, fontSize: 12, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>Фильтр ▼</button>
              </div>
            </div>

            {activeTab === 'orders' && (
              <div>
                {/* Table header */}
                <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1.8fr 1.2fr 1.2fr 0.8fr 1fr 1fr', padding: '8px 16px', background: bg.sunken, borderBottom: `1px solid ${bg.border}` }}>
                  {['№ Заявки', 'Техника', 'Дата и время', 'Объект', 'Часы', 'Статус', 'Действия'].map(h => (
                    <div key={h} style={{ fontSize: 10, fontWeight: 700, color: bg.muted, letterSpacing: '0.08em', textTransform: 'uppercase' }}>{h}</div>
                  ))}
                </div>
                {ORDERS.map((order, i) => {
                  const st = STATUS_STYLES[order.status]
                  return (
                    <div key={i} style={{
                      display: 'grid', gridTemplateColumns: '1.4fr 1.8fr 1.2fr 1.2fr 0.8fr 1fr 1fr',
                      padding: '11px 16px', borderBottom: `1px solid ${bg.border}`,
                      alignItems: 'center', cursor: 'pointer', transition: 'background 150ms',
                    }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = bg.subtle }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 700, color: bg.secondary, fontVariantNumeric: 'tabular-nums' }}>{order.id}</div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: bg.text }}>{order.crane}</div>
                      <div style={{ fontSize: 12, color: bg.secondary, fontVariantNumeric: 'tabular-nums' }}>{order.date} · {order.time}</div>
                      <div style={{ fontSize: 12, color: bg.secondary }}>{order.site}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: bg.text, fontVariantNumeric: 'tabular-nums' }}>{order.hours} ч</div>
                      <div>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                          padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
                          background: st.bg, color: st.color,
                          border: st.border || 'none',
                        }}>
                          {order.status === 'active' && <span className="pulse-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: '#4CAF7D' }} />}
                          {order.statusLabel}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button style={{ padding: '4px 10px', background: bg.subtle, border: `1px solid ${bg.border}`, borderRadius: 4, color: bg.secondary, fontSize: 11, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>Детали</button>
                        {order.status === 'draft' && (
                          <button style={{ padding: '4px 10px', background: '#1F3A52', border: 'none', borderRadius: 4, color: '#F2F4F5', fontSize: 11, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>Отправить</button>
                        )}
                      </div>
                    </div>
                  )
                })}
                <div style={{ padding: '10px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 12, color: bg.muted }}>5 из 23 заявок</span>
                  <button style={{ fontSize: 12, fontWeight: 600, color: '#F5A623', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>Показать все →</button>
                </div>
              </div>
            )}

            {activeTab === 'gantt' && (
              <div style={{ padding: '0 0 16px' }}>
                {/* Day headers */}
                <div style={{ display: 'grid', gridTemplateColumns: '160px repeat(8, 1fr)', borderBottom: `1px solid ${bg.border}`, background: bg.sunken }}>
                  <div style={{ padding: '8px 12px', fontSize: 10, fontWeight: 700, color: bg.muted, textTransform: 'uppercase', letterSpacing: '0.06em', borderRight: `1px solid ${bg.border}` }}>Техника</div>
                  {GANTT_DAYS.map((d, i) => (
                    <div key={i} style={{ padding: '8px 4px', textAlign: 'center', fontSize: 11, fontWeight: d.includes('24') ? 700 : 500, color: d.includes('24') ? '#E5665A' : bg.secondary, borderRight: `1px solid ${bg.border}` }}>{d}</div>
                  ))}
                </div>
                {GANTT_DATA.map((row, ri) => (
                  <div key={ri} style={{ display: 'grid', gridTemplateColumns: '160px repeat(8, 1fr)', borderBottom: `1px solid ${bg.border}`, minHeight: 52, position: 'relative', alignItems: 'center' }}>
                    <div style={{ padding: '0 12px', fontSize: 12, fontWeight: 600, color: bg.secondary, borderRight: `1px solid ${bg.border}`, height: '100%', display: 'flex', alignItems: 'center' }}>{row.crane}</div>
                    {/* Gantt blocks */}
                    {row.blocks.map((block, bi) => {
                      const st = STATUS_STYLES[block.status]
                      return (
                        <div key={bi} style={{
                          position: 'absolute',
                          left: `calc(160px + ${block.start} * (100% - 160px) / 8)`,
                          width: `calc(${block.span} * (100% - 160px) / 8 - 4px)`,
                          height: 32, top: '50%', transform: 'translateY(-50%)',
                          background: st.bg || `${st.color}22`,
                          border: st.border || `1px solid ${st.color}55`,
                          borderRadius: 4, padding: '0 8px',
                          display: 'flex', alignItems: 'center',
                          fontSize: 11, fontWeight: 700, color: st.color,
                          cursor: 'pointer', overflow: 'hidden', whiteSpace: 'nowrap',
                          marginLeft: 2,
                        }}>
                          {block.status === 'active' && <span className="pulse-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: '#4CAF7D', marginRight: 5, flexShrink: 0 }} />}
                          {block.label}
                        </div>
                      )
                    })}
                    {/* Empty cells for visual grid */}
                    {Array.from({ length: 8 }).map((_, ci) => (
                      <div key={ci} style={{ height: '100%', borderRight: `1px solid ${bg.border}`, opacity: 0.4 }} />
                    ))}
                  </div>
                ))}
                <div style={{ padding: '12px 16px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  {[
                    { label: 'Выполняется', status: 'active' },
                    { label: 'Подтверждена', status: 'confirmed' },
                    { label: 'Завершена', status: 'done' },
                    { label: 'Отправлена', status: 'submitted' },
                    { label: 'Конфликт', status: 'conflict' },
                  ].map(({ label, status }) => {
                    const st = STATUS_STYLES[status]
                    return (
                      <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11 }}>
                        <div style={{ width: 12, height: 12, borderRadius: 2, background: st.bg || 'transparent', border: st.border || `1px solid ${st.color}` }} />
                        <span style={{ color: bg.muted }}>{label}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Bottom grid: Activity + Quick actions */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
            {/* Activity feed */}
            <div style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 10, padding: '16px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: bg.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 14 }}>ЛЕНТА АКТИВНОСТИ</div>
              {[
                { time: '10:42', text: 'Рапорт за смену 19.09 требует подтверждения', type: 'report', icon: '📋' },
                { time: '09:18', text: 'LTM 1070 прибыл на объект ЖК Panorama', type: 'active', icon: '🚚' },
                { time: 'вчера', text: 'Счёт INV-2024-089 выставлен на 18 400 lei', type: 'invoice', icon: '💰' },
                { time: 'вчера', text: 'Заявка ORD-2024-141 закрыта, 12 часов', type: 'done', icon: '✅' },
                { time: '17 сент', text: 'Диспетчер Думу подтвердил бронь на 24.09', type: 'confirmed', icon: '📅' },
              ].map((item, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: i < 4 ? `1px solid ${bg.border}` : 'none', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 14, flexShrink: 0 }}>{item.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, color: bg.text, lineHeight: 1.4 }}>{item.text}</div>
                    <div style={{ fontSize: 10, color: bg.muted, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{item.time}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Quick actions + upcoming */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Upcoming today */}
              <div style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 10, padding: '16px 20px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: bg.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>СЕГОДНЯ НА ОБЪЕКТЕ</div>
                {[
                  { time: '08:00', label: 'LTM 1070 · ЖК Panorama', op: 'Оператор: Кирстеа И.', status: 'active' },
                  { time: '14:00', label: 'Ожидается завершение смены', op: 'Рапорт на проверку', status: 'submitted' },
                ].map((item, i) => {
                  const st = STATUS_STYLES[item.status]
                  return (
                    <div key={i} style={{ display: 'flex', gap: 12, padding: '8px 0', borderBottom: i === 0 ? `1px solid ${bg.border}` : 'none', alignItems: 'center' }}>
                      <div style={{ fontSize: 13, fontWeight: 800, color: bg.muted, fontVariantNumeric: 'tabular-nums', width: 40, flexShrink: 0 }}>{item.time}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: bg.text }}>{item.label}</div>
                        <div style={{ fontSize: 11, color: bg.muted, marginTop: 2 }}>{item.op}</div>
                      </div>
                      <span style={{ padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 700, background: st.bg, color: st.color }}>{item.status === 'active' ? 'Выполняется' : 'Ожидает'}</span>
                    </div>
                  )
                })}
              </div>

              {/* Quick actions */}
              <div style={{ background: bg.raised, border: `1px solid ${bg.border}`, borderRadius: 10, padding: '16px 20px' }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: bg.muted, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>БЫСТРЫЕ ДЕЙСТВИЯ</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {[
                    { icon: '🔁', label: 'Повторить заявку' },
                    { icon: '📋', label: 'Новая заявка' },
                    { icon: '📥', label: 'Скачать акты' },
                    { icon: '📞', label: 'Позвонить Думу' },
                  ].map((a, i) => (
                    <button key={i} style={{ padding: '10px 12px', background: bg.subtle, border: `1px solid ${bg.border}`, borderRadius: 7, display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', fontFamily: 'Manrope, sans-serif', color: bg.secondary, fontSize: 12, fontWeight: 600, textAlign: 'left' }}>
                      <span style={{ fontSize: 16 }}>{a.icon}</span>
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
