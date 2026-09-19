import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const CASES = [
  { title: { RU: 'ЖК «Panorama»', RO: 'Bloc «Panorama»', EN: '"Panorama" Residential Complex' }, city: 'Chișinău', tech: 'LTM 1070', period: { RU: '2023–2024 · 18 смен', RO: '2023–2024 · 18 schimburi', EN: '2023–2024 · 18 shifts' }, result: { RU: '320 т конструкций смонтировано', RO: '320 t structuri montate', EN: '320 t of structures assembled' }, img: 'https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=600&h=380&fit=crop&auto=format' },
  { title: { RU: 'Завод Moldagroindbank', RO: 'Uzina Moldagroindbank', EN: 'Moldagroindbank Factory' }, city: 'Orhei', tech: 'MCT 88 + LTM 1100', period: { RU: '2023 · 42 смены', RO: '2023 · 42 schimburi', EN: '2023 · 42 shifts' }, result: { RU: '7 500 м² металлоконструкций', RO: '7 500 m² structuri metalice', EN: '7,500 m² steel structures' }, img: 'https://images.unsplash.com/photo-1517011453931-c30f571a4fab?w=600&h=380&fit=crop&auto=format' },
  { title: { RU: 'Мост через Днестр', RO: 'Podul peste Nistru', EN: 'Dniester River Bridge' }, city: 'Vadul lui Vodă', tech: 'LTM 1100-5.2', period: { RU: '2022 · 8 смен', RO: '2022 · 8 schimburi', EN: '2022 · 8 shifts' }, result: { RU: '4 пролёта по 34 т каждый', RO: '4 travee de 34 t fiecare', EN: '4 spans of 34 t each' }, img: 'https://images.unsplash.com/photo-1539269071019-8bc6d57b0205?w=600&h=380&fit=crop&auto=format' },
  { title: { RU: 'Отель «Grand»', RO: 'Hotel «Grand»', EN: '"Grand" Hotel' }, city: 'Chișinău', tech: 'LTM 1070 + Potain', period: { RU: '2022–2023 · 60 смен', RO: '2022–2023 · 60 schimburi', EN: '2022–2023 · 60 shifts' }, result: { RU: '14-этажный корпус, 2 400 т', RO: 'Corp 14 etaje, 2 400 t', EN: '14-storey block, 2,400 t' }, img: 'https://images.unsplash.com/photo-1485083269755-a7b559a4fe5e?w=600&h=380&fit=crop&auto=format' },
  { title: { RU: 'Зернохранилище АФ «Floreni»', RO: 'Siloz SA «Floreni»', EN: '"Floreni" Grain Silo' }, city: 'Floreni', tech: 'LTM 1100', period: { RU: '2021 · 12 смен', RO: '2021 · 12 schimburi', EN: '2021 · 12 shifts' }, result: { RU: '6 резервуаров по 2 000 т зерна', RO: '6 rezervoare de 2 000 t cereale', EN: '6 tanks at 2,000 t grain each' }, img: 'https://images.unsplash.com/photo-1563391017873-6e6beab67fed?w=600&h=380&fit=crop&auto=format' },
  { title: { RU: 'ТЦ «Malldova»', RO: 'CC «Malldova»', EN: '"Malldova" Shopping Centre' }, city: 'Chișinău', tech: 'Liebherr 280 EC-H', period: { RU: '2020–2021 · 90 смен', RO: '2020–2021 · 90 schimburi', EN: '2020–2021 · 90 shifts' }, result: { RU: '45 000 м² торговых площадей', RO: '45 000 m² suprafețe comerciale', EN: '45,000 m² retail area' }, img: 'https://images.unsplash.com/photo-1535732759880-bbd5c7265e3f?w=600&h=380&fit=crop&auto=format' },
]

type Lang = 'RO' | 'RU' | 'EN'

export default function CasesPage() {
  const { lang } = useLang()

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        <div style={{ marginBottom: 48 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.nav.cases, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 12px', letterSpacing: '-0.02em' }}>
            {tr(t.pages.casesPage.title, lang)}
          </h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{tr(t.pages.casesPage.subtitle, lang)}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
          {CASES.map((c, i) => (
            <div key={i} style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.06)', cursor: 'pointer', transition: 'all 200ms' }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.10)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)'; (e.currentTarget as HTMLElement).style.transform = 'none' }}
            >
              <div style={{ height: 220, background: '#EDEFF1', position: 'relative', overflow: 'hidden' }}>
                <img src={c.img} alt={c.title[lang as Lang]} style={{ width: '100%', height: '100%', objectFit: 'cover', transition: 'transform 400ms ease' }} />
                <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(0deg, rgba(0,0,0,0.5) 0%, transparent 60%)' }} />
                <div style={{ position: 'absolute', bottom: 12, left: 14 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', background: 'rgba(0,0,0,0.6)', padding: '2px 8px', borderRadius: 4 }}>{c.tech}</span>
                </div>
              </div>
              <div style={{ padding: '18px 20px 22px' }}>
                <div style={{ fontSize: 11, color: '#8A949B', fontWeight: 600, marginBottom: 6, letterSpacing: '0.04em' }}>{c.city} · {c.period[lang as Lang]}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#14181B', marginBottom: 10 }}>{c.title[lang as Lang]}</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div style={{ width: 3, height: 3, borderRadius: '50%', background: '#F5A623', flexShrink: 0 }} />
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#1F3A52' }}>{c.result[lang as Lang]}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
