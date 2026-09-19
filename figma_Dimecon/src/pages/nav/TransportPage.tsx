import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const VEHICLES = [
  { name: 'Tral 40 т', spec: 'Până la 40 т · 20×3,5×4 м · Permis standard', price: '8 lei/km', img: 'https://images.unsplash.com/photo-1586458995526-09ce6839babe?w=400&h=240&fit=crop&auto=format' },
  { name: 'Tral 60 т', spec: 'Până la 60 т · 24×4×4,5 м · Escortă inclusă', price: '14 lei/km', img: 'https://images.unsplash.com/photo-1517011453931-c30f571a4fab?w=400&h=240&fit=crop&auto=format' },
  { name: 'Tral 100 т', spec: 'Până la 100 т · 28×5×5 м · Permis special + escortă', price: '22 lei/km', img: 'https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=400&h=240&fit=crop&auto=format' },
]

const DOCS = [
  { ru: 'Разрешение на перевозку негабаритного груза', ro: 'Autorizație transport supragabaritic', en: 'Oversized cargo transport permit' },
  { ru: 'Согласование с дорожной полицией', ro: 'Coordonare cu Poliția Rutieră', en: 'Road police coordination' },
  { ru: 'Эскорт полицейского автомобиля (при необходимости)', ro: 'Escortă auto polițienească (dacă este necesar)', en: 'Police vehicle escort (if required)' },
  { ru: 'Страхование груза на период перевозки', ro: 'Asigurarea mărfii pe durata transportului', en: 'Cargo insurance during transport' },
  { ru: 'Схема маршрута с анализом препятствий', ro: 'Schemă rută cu analiza obstacolelor', en: 'Route scheme with obstacle analysis' },
]

type Lang = 'RO' | 'RU' | 'EN'

export default function TransportPage() {
  const { lang } = useLang()

  const title = tr(t.pages.transportPage.title, lang)
  const subtitle = tr(t.pages.transportPage.subtitle, lang)

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        <div style={{ marginBottom: 48 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.nav.transport, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 12px', letterSpacing: '-0.02em' }}>{title}</h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{subtitle}</p>
        </div>

        {/* Vehicles */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 56 }}>
          {VEHICLES.map((v, i) => (
            <div key={i} style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
              <div style={{ height: 200, background: '#EDEFF1' }}>
                <img src={v.img} alt={v.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              </div>
              <div style={{ padding: '20px 20px 22px' }}>
                <div style={{ fontSize: 17, fontWeight: 800, color: '#14181B', marginBottom: 8 }}>{v.name}</div>
                <div style={{ fontSize: 13, color: '#5A646B', marginBottom: 14, lineHeight: 1.55 }}>{v.spec}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{v.price}</span>
                  <button style={{ padding: '7px 14px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                    {lang === 'RO' ? 'Solicitați ofertă' : lang === 'EN' ? 'Request quote' : 'Запросить'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Permits & Docs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40 }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: '#14181B', margin: '0 0 20px', letterSpacing: '-0.01em' }}>
              {lang === 'RO' ? 'Documente și permise' : lang === 'EN' ? 'Documents & permits' : 'Документы и разрешения'}
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {DOCS.map((doc, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#fff', border: '1px solid #DDE1E4', borderRadius: 6, alignItems: 'flex-start' }}>
                  <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#1F3A52', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 1 }}>
                    <span style={{ color: '#F5A623', fontSize: 11, fontWeight: 800 }}>✓</span>
                  </div>
                  <span style={{ fontSize: 13, color: '#14181B', lineHeight: 1.5 }}>
                    {lang === 'RO' ? doc.ro : lang === 'EN' ? doc.en : doc.ru}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: '#14181B', margin: '0 0 20px', letterSpacing: '-0.01em' }}>
              {lang === 'RO' ? 'Zone de acoperire' : lang === 'EN' ? 'Coverage zones' : 'Зоны охвата'}
            </h2>
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden' }}>
              {[
                { zone: lang === 'RO' ? 'Chișinău + 15 km' : lang === 'EN' ? 'Chisinau + 15 km' : 'Кишинёв + 15 км', time: lang === 'RO' ? 'de la 2 ore' : lang === 'EN' ? 'from 2 hours' : 'от 2 часов', price: lang === 'RO' ? 'Inclus' : lang === 'EN' ? 'Included' : 'Включено', color: '#2E7D4F' },
                { zone: lang === 'RO' ? 'Moldova Centrală' : lang === 'EN' ? 'Central Moldova' : 'Центральная Молдова', time: lang === 'RO' ? 'de la 3 ore' : lang === 'EN' ? 'from 3 hours' : 'от 3 часов', price: '4–8 lei/km', color: '#2D6CB5' },
                { zone: lang === 'RO' ? 'Nord și Sud' : lang === 'EN' ? 'North & South' : 'Север и Юг', time: lang === 'RO' ? 'de la 5 ore' : lang === 'EN' ? 'from 5 hours' : 'от 5 часов', price: '8–12 lei/km', color: '#C77700' },
                { zone: lang === 'RO' ? 'România, Ucraina' : lang === 'EN' ? 'Romania, Ukraine' : 'Румыния, Украина', time: lang === 'RO' ? 'La cerere' : lang === 'EN' ? 'On request' : 'По запросу', price: lang === 'RO' ? 'Calculul individual' : lang === 'EN' ? 'Individual quote' : 'Индивидуально', color: '#8A949B' },
              ].map((z, i, arr) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < arr.length - 1 ? '1px solid #DDE1E4' : 'none' }}>
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: z.color, flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#14181B' }}>{z.zone}</div>
                      <div style={{ fontSize: 11, color: '#8A949B' }}>{z.time}</div>
                    </div>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: z.color, fontVariantNumeric: 'tabular-nums' }}>{z.price}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
