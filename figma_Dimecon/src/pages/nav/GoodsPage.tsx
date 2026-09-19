import { useState } from 'react'
import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const CATEGORIES = [
  { id: 'all', ru: 'Все', ro: 'Toate', en: 'All' },
  { id: 'cables', ru: 'Канаты', ro: 'Cabluri', en: 'Cables' },
  { id: 'slings', ru: 'Стропы', ro: 'Chingi', en: 'Slings' },
  { id: 'hooks', ru: 'Крюки и скобы', ro: 'Cârlige și șacluri', en: 'Hooks & shackles' },
  { id: 'other', ru: 'Прочее', ro: 'Altele', en: 'Other' },
]

const PRODUCTS = [
  { cat: 'cables', name: { RU: 'Канат стальной 14 мм', RO: 'Cablu oțel 14 mm', EN: 'Steel cable 14 mm' }, spec: { RU: 'ГОСТ 3077-80 · Г/П 2,5 т · в наличии', RO: 'GOST 3077-80 · Cap. 2,5 t · în stoc', EN: 'GOST 3077-80 · Cap. 2.5 t · in stock' }, price: '85 lei/м', stock: true },
  { cat: 'cables', name: { RU: 'Канат стальной 20 мм', RO: 'Cablu oțel 20 mm', EN: 'Steel cable 20 mm' }, spec: { RU: 'ГОСТ 3077-80 · Г/П 5 т · в наличии', RO: 'GOST 3077-80 · Cap. 5 t · în stoc', EN: 'GOST 3077-80 · Cap. 5 t · in stock' }, price: '170 lei/м', stock: true },
  { cat: 'slings', name: { RU: 'Строп текстильный 3 т × 3 м', RO: 'Chingă textilă 3 t × 3 m', EN: 'Textile sling 3 t × 3 m' }, spec: { RU: 'ГОСТ 25573-82 · Красный · в наличии', RO: 'GOST 25573-82 · Roșu · în stoc', EN: 'GOST 25573-82 · Red · in stock' }, price: '320 lei/шт', stock: true },
  { cat: 'slings', name: { RU: 'Строп цепной 5 т × 2 м', RO: 'Chingă lanț 5 t × 2 m', EN: 'Chain sling 5 t × 2 m' }, spec: { RU: 'Класс 8 · нержавеющая сталь · под заказ', RO: 'Clasa 8 · oțel inox · la comandă', EN: 'Grade 8 · stainless steel · on order' }, price: '1 200 lei/шт', stock: false },
  { cat: 'hooks', name: { RU: 'Крюк кованый 5 т с предохранителем', RO: 'Cârlig forjat 5 t cu siguranță', EN: 'Forged hook 5 t with latch' }, spec: { RU: 'DIN 15401 · оцинкованный · в наличии', RO: 'DIN 15401 · zincat · în stoc', EN: 'DIN 15401 · galvanised · in stock' }, price: '480 lei/шт', stock: true },
  { cat: 'hooks', name: { RU: 'Скоба такелажная 8,5 т', RO: 'Șaclă tachelaj 8,5 t', EN: 'Rigging shackle 8.5 t' }, spec: { RU: 'ГОСТ 26815-86 · горячая оцинковка · в наличии', RO: 'GOST 26815-86 · galvanizare la cald · în stoc', EN: 'GOST 26815-86 · hot-dip galv. · in stock' }, price: '190 lei/шт', stock: true },
  { cat: 'other', name: { RU: 'Траверса балочная 10 т', RO: 'Traversă grindă 10 t', EN: 'Beam spreader 10 t' }, spec: { RU: 'L=2000 мм · в наличии 2 шт', RO: 'L=2000 mm · în stoc 2 buc', EN: 'L=2000 mm · 2 pcs in stock' }, price: '4 800 lei/шт', stock: true },
  { cat: 'other', name: { RU: 'Подкладная плита 1000×1000×50 мм', RO: 'Placă suport 1000×1000×50 mm', EN: 'Outrigger pad 1000×1000×50 mm' }, spec: { RU: 'Полиэтилен высокой плотности · 1 шт = 50 кг', RO: 'Polietilenă densitate mare · 1 buc = 50 kg', EN: 'HDPE · 1 pc = 50 kg' }, price: '2 200 lei/шт', stock: true },
]

type Lang = 'RO' | 'RU' | 'EN'

export default function GoodsPage() {
  const { lang } = useLang()
  const [cat, setCat] = useState('all')

  const filtered = PRODUCTS.filter(p => cat === 'all' || p.cat === cat)

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.nav.goods, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 12px', letterSpacing: '-0.02em' }}>
            {tr(t.pages.goodsPage.title, lang)}
          </h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{tr(t.pages.goodsPage.subtitle, lang)}</p>
        </div>

        {/* Category filter */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
          {CATEGORIES.map(c => (
            <button key={c.id} onClick={() => setCat(c.id)} style={{
              padding: '7px 16px', borderRadius: 4, border: `1px solid ${cat === c.id ? '#1F3A52' : '#C2C8CD'}`,
              background: cat === c.id ? '#1F3A52' : '#fff',
              color: cat === c.id ? '#F2F4F5' : '#5A646B',
              fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif',
            }}>
              {lang === 'RO' ? c.ro : lang === 'EN' ? c.en : c.ru}
            </button>
          ))}
        </div>

        {/* Product list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr 1fr 1fr', padding: '8px 20px', background: '#EDEFF1', border: '1px solid #DDE1E4', borderBottom: 'none', borderRadius: '8px 8px 0 0' }}>
            {[
              lang === 'RO' ? 'Denumire' : lang === 'EN' ? 'Name' : 'Наименование',
              lang === 'RO' ? 'Specificație' : lang === 'EN' ? 'Specification' : 'Характеристики',
              lang === 'RO' ? 'Preț' : lang === 'EN' ? 'Price' : 'Цена',
              lang === 'RO' ? 'Stoc' : lang === 'EN' ? 'Stock' : 'Наличие',
              '',
            ].map((h, i) => (
              <div key={i} style={{ fontSize: 10, fontWeight: 700, color: '#8A949B', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{h}</div>
            ))}
          </div>
          {filtered.map((p, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '2fr 2fr 1fr 1fr 1fr',
              padding: '14px 20px', background: '#fff',
              border: '1px solid #DDE1E4', borderTop: 'none',
              alignItems: 'center',
              borderRadius: i === filtered.length - 1 ? '0 0 8px 8px' : 0,
              transition: 'background 150ms',
            }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F6F7' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = '#fff' }}
            >
              <div style={{ fontSize: 14, fontWeight: 600, color: '#14181B' }}>{p.name[lang as Lang]}</div>
              <div style={{ fontSize: 12, color: '#5A646B' }}>{p.spec[lang as Lang]}</div>
              <div style={{ fontSize: 14, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{p.price}</div>
              <div>
                <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: p.stock ? 'rgba(46,125,79,0.1)' : 'rgba(199,119,0,0.1)', color: p.stock ? '#2E7D4F' : '#C77700' }}>
                  {p.stock ? (lang === 'RO' ? 'în stoc' : lang === 'EN' ? 'in stock' : 'в наличии') : (lang === 'RO' ? 'la comandă' : lang === 'EN' ? 'on order' : 'под заказ')}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button style={{ padding: '5px 12px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                  {lang === 'RO' ? 'Adaugă' : lang === 'EN' ? 'Add' : 'Заказать'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
