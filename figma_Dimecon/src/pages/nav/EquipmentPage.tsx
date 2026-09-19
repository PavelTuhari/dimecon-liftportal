import { useState } from 'react'
import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const ALL_EQUIPMENT = [
  { name: 'Liebherr LTM 1070-4.2', type: 'mobile', capacity: 70, radius: 48, height: 62, price: '1 200', available: true, img: 'https://images.unsplash.com/photo-1563391017873-6e6beab67fed?w=400&h=260&fit=crop&auto=format' },
  { name: 'Liebherr LTM 1100-5.2', type: 'mobile', capacity: 100, radius: 60, height: 80, price: '1 800', available: false, busyUntil: '28 sept', img: 'https://images.unsplash.com/photo-1535732759880-bbd5c7265e3f?w=400&h=260&fit=crop&auto=format' },
  { name: 'Grove GMK3060L', type: 'mobile', capacity: 60, radius: 40, height: 56, price: '980', available: true, img: 'https://images.unsplash.com/photo-1485083269755-a7b559a4fe5e?w=400&h=260&fit=crop&auto=format' },
  { name: 'Potain MCT 88', type: 'tower', capacity: 6, radius: 50, height: 45, price: '850', available: true, img: 'https://images.unsplash.com/photo-1539269071019-8bc6d57b0205?w=400&h=260&fit=crop&auto=format' },
  { name: 'Liebherr 280 EC-H', type: 'tower', capacity: 16, radius: 60, height: 70, price: '1 100', available: false, busyUntil: '1 oct', img: 'https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=400&h=260&fit=crop&auto=format' },
  { name: 'Manitowoc MLC165', type: 'mobile', capacity: 165, radius: 72, height: 98, price: '2 400', available: true, img: 'https://images.unsplash.com/photo-1517011453931-c30f571a4fab?w=400&h=260&fit=crop&auto=format' },
]

export default function EquipmentPage() {
  const { lang } = useLang()
  const [filter, setFilter] = useState<'all' | 'mobile' | 'tower'>('all')
  const [compare, setCompare] = useState<string[]>([])

  const filtered = ALL_EQUIPMENT.filter(e => filter === 'all' || e.type === filter)

  const toggleCompare = (name: string) => {
    setCompare(prev => prev.includes(name) ? prev.filter(n => n !== name) : prev.length < 3 ? [...prev, name] : prev)
  }

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        {/* Header */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.pages.equipmentPage.title, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 12px', letterSpacing: '-0.02em' }}>
            {tr(t.pages.equipmentPage.title, lang)}
          </h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{tr(t.pages.equipmentPage.subtitle, lang)}</p>
        </div>

        {/* Filters + Sort */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['all', 'mobile', 'tower'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '7px 16px', borderRadius: 4, border: `1px solid ${filter === f ? '#1F3A52' : '#C2C8CD'}`,
                background: filter === f ? '#1F3A52' : '#fff',
                color: filter === f ? '#F2F4F5' : '#5A646B',
                fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif',
              }}>
                {f === 'all' ? tr(t.pages.equipmentPage.allTypes, lang) : f === 'mobile' ? tr(t.pages.equipmentPage.mobile, lang) : tr(t.pages.equipmentPage.tower, lang)}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            {compare.length > 0 && (
              <button style={{ padding: '7px 16px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                {tr(t.pages.equipmentPage.compare, lang)} ({compare.length}) →
              </button>
            )}
            <select style={{ padding: '7px 12px', border: '1px solid #C2C8CD', borderRadius: 4, background: '#fff', fontSize: 13, fontFamily: 'Manrope, sans-serif', color: '#14181B' }}>
              <option>{tr(t.pages.equipmentPage.sort, lang)}: Г/П ↑</option>
              <option>{tr(t.pages.equipmentPage.sort, lang)}: Цена ↑</option>
              <option>{tr(t.pages.equipmentPage.sort, lang)}: Доступность</option>
            </select>
          </div>
        </div>

        {/* Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
          {filtered.map((eq, i) => (
            <div key={i} style={{ border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden', background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.06)', transition: 'all 200ms' }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.10)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)'; (e.currentTarget as HTMLElement).style.transform = 'none' }}
            >
              <div style={{ position: 'relative', height: 200, background: '#EDEFF1' }}>
                <img src={eq.img} alt={eq.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                <div style={{ position: 'absolute', top: 10, left: 10 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: eq.available ? 'rgba(46,125,79,0.9)' : 'rgba(192,57,43,0.85)', color: '#fff' }}>
                    {eq.available ? tr(t.equipment.free, lang) : `${tr(t.equipment.busy, lang)} ${eq.busyUntil}`}
                  </span>
                </div>
                <div style={{ position: 'absolute', top: 10, right: 10 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px', borderRadius: 4, background: 'rgba(31,58,82,0.85)', color: '#F2F4F5', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
                    <input type="checkbox" checked={compare.includes(eq.name)} onChange={() => toggleCompare(eq.name)} style={{ accentColor: '#F5A623' }} />
                    {tr(t.pages.equipmentPage.compare, lang)}
                  </label>
                </div>
              </div>
              <div style={{ padding: '18px 18px 20px' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#8A949B', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                  {eq.type === 'mobile' ? tr(t.equipment.autocrane, lang) : tr(t.equipment.towercrane, lang)}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#14181B', marginBottom: 14 }}>{eq.name}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 16 }}>
                  {[
                    { label: tr(t.equipment.capacity, lang), value: `${eq.capacity} т` },
                    { label: tr(t.equipment.reach, lang), value: `${eq.radius} м` },
                    { label: tr(t.equipment.height, lang), value: `${eq.height} м` },
                  ].map(spec => (
                    <div key={spec.label} style={{ background: '#F5F6F7', borderRadius: 4, padding: '8px 6px', textAlign: 'center' }}>
                      <div style={{ fontSize: 17, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{spec.value}</div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: '#8A949B', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 2 }}>{spec.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: '#14181B', fontVariantNumeric: 'tabular-nums' }}>
                    {tr(t.equipment.priceFrom, lang)} {eq.price} lei/ч
                  </span>
                  <button style={{ padding: '8px 16px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                    {tr(t.equipment.order, lang)}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
