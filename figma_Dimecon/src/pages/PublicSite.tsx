import { useState } from 'react'
import { useLang } from '../context/LangContext'
import { t, tr } from '../i18n'
import EquipmentPage from './nav/EquipmentPage'
import ServicesPage from './nav/ServicesPage'
import TransportPage from './nav/TransportPage'
import GoodsPage from './nav/GoodsPage'
import CasesPage from './nav/CasesPage'
import AboutPage from './nav/AboutPage'
import ContactsPage from './nav/ContactsPage'

type NavPage = 'home' | 'equipment' | 'services' | 'transport' | 'goods' | 'cases' | 'about' | 'contacts'

const LANGS = ['RO', 'RU', 'EN'] as const

const TASKS = [
  { icon: '🏗️', ru: 'Монтаж металлоконструкций', ro: 'Montaj structuri metalice', en: 'Steel structure assembly', descRu: 'Балки, фермы, колонны — точная установка с допуском ±5 мм', descRo: 'Grinzi, ferme, stâlpi — montaj precis cu toleranță ±5 mm', descEn: 'Beams, trusses, columns — precise installation within ±5 mm' },
  { icon: '🧱', ru: 'Подъём стройматериалов', ro: 'Ridicare materiale de construcție', en: 'Lifting construction materials', descRu: 'Поддоны кирпича, бетонные блоки, плиты перекрытий', descRo: 'Paleți de cărămidă, blocuri de beton, plăci de planșeu', descEn: 'Brick pallets, concrete blocks, floor slabs' },
  { icon: '🏠', ru: 'Монтаж бытовок и модулей', ro: 'Montaj barăci și module', en: 'Siting cabins & modules', descRu: 'Вахтовые городки, торговые павильоны, контейнеры', descRo: 'Orășele muncitorești, pavilioane comerciale, containere', descEn: 'Worker camps, retail pavilions, containers' },
  { icon: '⚡', ru: 'Промышленное оборудование', ro: 'Echipamente industriale', en: 'Industrial equipment', descRu: 'Генераторы, трансформаторы, насосные станции', descRo: 'Generatoare, transformatoare, stații de pompare', descEn: 'Generators, transformers, pump stations' },
  { icon: '🌳', ru: 'Ландшафтные работы', ro: 'Lucrări peisagistice', en: 'Landscape works', descRu: 'Крупномерные деревья, фонтаны, малые архитектурные формы', descRo: 'Copaci maturi, fântâni, elemente de arhitectură mică', descEn: 'Mature trees, fountains, small architectural forms' },
  { icon: '🔩', ru: 'Негабаритные грузы', ro: 'Sarcini supragabaritice', en: 'Oversized loads', descRu: 'Спецразрешения, сопровождение, маршрутизация', descRo: 'Permise speciale, escortă, planificarea rutelor', descEn: 'Special permits, escort, route planning' },
]

const EQUIPMENT = [
  { name: 'Liebherr LTM 1070-4.2', capacity: 70, radius: 48, height: 62, price: '1 200', available: true, img: 'https://images.unsplash.com/photo-1563391017873-6e6beab67fed?w=400&h=280&fit=crop&auto=format' },
  { name: 'Liebherr LTM 1100-5.2', capacity: 100, radius: 60, height: 80, price: '1 800', available: false, img: 'https://images.unsplash.com/photo-1535732759880-bbd5c7265e3f?w=400&h=280&fit=crop&auto=format' },
  { name: 'Potain MCT 88', capacity: 6, radius: 50, height: 45, price: '850', available: true, img: 'https://images.unsplash.com/photo-1485083269755-a7b559a4fe5e?w=400&h=280&fit=crop&auto=format' },
]

const CASES = [
  { titleRu: 'ЖК «Panorama»', titleRo: 'Bloc «Panorama»', titleEn: '"Panorama" Residential', city: 'Chișinău', tech: 'LTM 1070', resultRu: '320 т конструкций за 18 смен', resultRo: '320 t structuri în 18 schimburi', resultEn: '320 t structures in 18 shifts', img: 'https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=600&h=400&fit=crop&auto=format' },
  { titleRu: 'Завод Moldagroindbank', titleRo: 'Uzina Moldagroindbank', titleEn: 'Moldagroindbank Factory', city: 'Orhei', tech: 'MCT 88 + LTM 1100', resultRu: '7 500 м² металлоконструкций', resultRo: '7 500 m² structuri metalice', resultEn: '7,500 m² steel structures', img: 'https://images.unsplash.com/photo-1517011453931-c30f571a4fab?w=600&h=400&fit=crop&auto=format' },
  { titleRu: 'Мост через Днестр', titleRo: 'Podul peste Nistru', titleEn: 'Dniester Bridge', city: 'Vadul lui Vodă', tech: 'LTM 1100-5.2', resultRu: '4 пролёта по 34 т каждый', resultRo: '4 travee de 34 t fiecare', resultEn: '4 spans of 34 t each', img: 'https://images.unsplash.com/photo-1539269071019-8bc6d57b0205?w=600&h=400&fit=crop&auto=format' },
]

const PARTNER_FEATURES = [
  { icon: '🗓️', ru: 'Бронь техники', ro: 'Rezervare utilaje', en: 'Equipment booking', dRu: 'Через портал, за 30 сек', dRo: 'Prin portal, în 30 sec', dEn: 'Via portal, in 30 sec' },
  { icon: '💼', ru: 'Договорная цена', ro: 'Preț contractual', en: 'Contract rate', dRu: 'От −5% до −20%', dRo: 'De la −5% la −20%', dEn: 'From −5% to −20%' },
  { icon: '📋', ru: 'Сменные рапорты', ro: 'Rapoarte de schimb', en: 'Shift reports', dRu: 'Онлайн, с подписью', dRo: 'Online, cu semnătură', dEn: 'Online, with signature' },
  { icon: '👤', ru: 'Закреплённый диспетчер', ro: 'Dispecer dedicat', en: 'Dedicated dispatcher', dRu: 'Всегда один контакт', dRo: 'Mereu un singur contact', dEn: 'Always one contact' },
]

type Lang = 'RO' | 'RU' | 'EN'

function L({ field, lang }: { field: { RO: string; RU: string; EN: string }; lang: Lang }) {
  return <>{field[lang]}</>
}

export default function PublicSite() {
  const { lang, setLang } = useLang()
  const [page, setPage] = useState<NavPage>('home')
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const [taskType, setTaskType] = useState('')
  const [period, setPeriod] = useState('')
  const [address, setAddress] = useState('')

  const navItems: { id: NavPage; label: { RO: string; RU: string; EN: string } }[] = [
    { id: 'equipment', label: t.nav.equipment },
    { id: 'services', label: t.nav.services },
    { id: 'transport', label: t.nav.transport },
    { id: 'goods', label: t.nav.goods },
    { id: 'cases', label: t.nav.cases },
    { id: 'about', label: t.nav.about },
    { id: 'contacts', label: t.nav.contacts },
  ]

  return (
    <div style={{ fontFamily: 'Manrope, sans-serif', color: '#14181B', background: '#fff' }}>
      {/* ─── HEADER ─── */}
      <header style={{ position: 'sticky', top: 40, zIndex: 100, background: '#1F3A52', borderBottom: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 2px 16px rgba(0,0,0,0.24)' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 48px', display: 'flex', alignItems: 'center', height: 60, gap: 24 }}>
          {/* Logo */}
          <button onClick={() => setPage('home')} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'none', border: 'none', cursor: 'pointer', padding: 0, flexShrink: 0 }}>
            <div style={{ width: 32, height: 32, background: '#F5A623', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: '#14181B' }}>D</span>
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: '#F2F4F5', lineHeight: 1.1 }}>DIMECON</div>
              <div style={{ fontSize: 9, fontWeight: 600, color: '#A3ADB4', letterSpacing: '0.1em' }}>MACARAGII · 1968</div>
            </div>
          </button>

          {/* Nav */}
          <nav style={{ display: 'flex', gap: 1, flex: 1 }}>
            {navItems.map(item => (
              <button key={item.id} onClick={() => setPage(item.id)} style={{
                padding: '6px 11px', borderRadius: 4, fontSize: 12, fontWeight: page === item.id ? 700 : 500,
                color: page === item.id ? '#F2F4F5' : '#A3ADB4',
                background: page === item.id ? 'rgba(255,255,255,0.1)' : 'transparent',
                border: 'none', cursor: 'pointer', fontFamily: 'Manrope, sans-serif',
                borderBottom: page === item.id ? '2px solid #F5A623' : '2px solid transparent',
                transition: 'all 150ms', whiteSpace: 'nowrap',
              }}
                onMouseEnter={e => { if (page !== item.id) { (e.currentTarget as HTMLElement).style.color = '#F2F4F5'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)' } }}
                onMouseLeave={e => { if (page !== item.id) { (e.currentTarget as HTMLElement).style.color = '#A3ADB4'; (e.currentTarget as HTMLElement).style.background = 'transparent' } }}
              >
                <L field={item.label} lang={lang} />
              </button>
            ))}
          </nav>

          {/* Right actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            {/* Language switcher */}
            <div style={{ display: 'flex', gap: 1, background: 'rgba(255,255,255,0.06)', borderRadius: 4, padding: 2 }}>
              {LANGS.map(l => (
                <button key={l} onClick={() => setLang(l)} style={{
                  padding: '3px 8px', borderRadius: 3, border: 'none', cursor: 'pointer',
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
                  background: lang === l ? '#F5A623' : 'transparent',
                  color: lang === l ? '#14181B' : '#A3ADB4',
                  fontFamily: 'Manrope, sans-serif', transition: 'all 150ms',
                }}>
                  {l}
                </button>
              ))}
            </div>
            <a href="tel:+37322123456" style={{ color: '#F2F4F5', fontSize: 12, fontWeight: 700, textDecoration: 'none', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
              +373 22 123-456
            </a>
            <button onClick={() => setPage('contacts')} style={{ padding: '5px 12px', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, background: 'transparent', color: '#F2F4F5', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
              <L field={t.nav.cabinet} lang={lang} />
            </button>
            <button onClick={() => setPage('home')} style={{ padding: '6px 16px', border: 'none', borderRadius: 4, background: '#F5A623', color: '#14181B', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', whiteSpace: 'nowrap' }}>
              <L field={t.nav.calculate} lang={lang} />
            </button>
          </div>
        </div>
      </header>

      {/* ─── SUB-PAGES ─── */}
      {page === 'equipment' && <EquipmentPage />}
      {page === 'services' && <ServicesPage />}
      {page === 'transport' && <TransportPage />}
      {page === 'goods' && <GoodsPage />}
      {page === 'cases' && <CasesPage />}
      {page === 'about' && <AboutPage />}
      {page === 'contacts' && <ContactsPage />}

      {/* ─── HOMEPAGE ─── */}
      {page === 'home' && (
        <>
          {/* HERO */}
          <section style={{ position: 'relative', height: 600, overflow: 'hidden' }}>
            <img src="https://images.unsplash.com/photo-1563391017873-6e6beab67fed?w=1440&h=700&fit=crop&auto=format" alt="Autocran Dimecon" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
            <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(15,18,20,0.90) 0%, rgba(15,18,20,0.55) 60%, rgba(15,18,20,0.15) 100%)' }} />
            <div style={{ position: 'relative', maxWidth: 1280, margin: '0 auto', padding: '0 80px', height: '100%', display: 'flex', alignItems: 'center' }}>
              <div style={{ maxWidth: 660 }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: 'rgba(245,166,35,0.15)', border: '1px solid rgba(245,166,35,0.3)', borderRadius: 4, padding: '4px 12px', marginBottom: 20 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#F5A623' }} className="pulse-dot" />
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.08em' }}><L field={t.hero.badge} lang={lang} /></span>
                </div>
                <h1 style={{ fontSize: 46, fontWeight: 800, lineHeight: 1.14, color: '#F2F4F5', margin: '0 0 16px', letterSpacing: '-0.02em' }}>
                  <L field={t.hero.title1} lang={lang} /><br />
                  <span style={{ color: '#F5A623' }}><L field={t.hero.titleAccent} lang={lang} /></span><br />
                  <L field={t.hero.title2} lang={lang} />
                </h1>
                <p style={{ fontSize: 16, lineHeight: 1.65, color: '#A3ADB4', margin: '0 0 28px', maxWidth: 520 }}>
                  <L field={t.hero.subtitle} lang={lang} />
                </p>
                {/* Mini form */}
                <div style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, padding: 14, backdropFilter: 'blur(12px)', display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <div style={{ flex: '1 1 150px' }}>
                    <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#A3ADB4', marginBottom: 5, letterSpacing: '0.08em', textTransform: 'uppercase' }}><L field={t.hero.taskLabel} lang={lang} /></label>
                    <select value={taskType} onChange={e => setTaskType(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.08)', color: taskType ? '#F2F4F5' : '#6F7A81', fontSize: 12, fontFamily: 'Manrope, sans-serif', cursor: 'pointer' }}>
                      <option value=""><L field={t.hero.taskPlaceholder} lang={lang} /></option>
                      {TASKS.map((task, i) => (
                        <option key={i} value={task.ru}>{lang === 'RO' ? task.ro : lang === 'EN' ? task.en : task.ru}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ flex: '1 1 130px' }}>
                    <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#A3ADB4', marginBottom: 5, letterSpacing: '0.08em', textTransform: 'uppercase' }}><L field={t.hero.dateLabel} lang={lang} /></label>
                    <input type="date" value={period} onChange={e => setPeriod(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.08)', color: '#F2F4F5', fontSize: 12, fontFamily: 'Manrope, sans-serif', colorScheme: 'dark' }} />
                  </div>
                  <div style={{ flex: '1 1 160px' }}>
                    <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: '#A3ADB4', marginBottom: 5, letterSpacing: '0.08em', textTransform: 'uppercase' }}><L field={t.hero.addressLabel} lang={lang} /></label>
                    <input type="text" placeholder={tr(t.hero.addressPlaceholder, lang)} value={address} onChange={e => setAddress(e.target.value)} style={{ width: '100%', padding: '8px 10px', borderRadius: 4, border: '1px solid rgba(255,255,255,0.15)', background: 'rgba(255,255,255,0.08)', color: '#F2F4F5', fontSize: 12, fontFamily: 'Manrope, sans-serif' }} />
                  </div>
                  <button style={{ padding: '9px 20px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', whiteSpace: 'nowrap', flexShrink: 0 }}>
                    <L field={t.hero.cta} lang={lang} />
                  </button>
                </div>
                <p style={{ fontSize: 11, color: '#6F7A81', marginTop: 8 }}><L field={t.hero.hint} lang={lang} /></p>
              </div>
            </div>
          </section>

          {/* STATS */}
          <div style={{ background: '#1F3A52' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
              {[
                { value: '1968', label: t.stats.founded },
                { value: '100 т', label: t.stats.capacity },
                { value: '60 м', label: t.stats.reach },
                { value: '500+', label: t.stats.objects },
              ].map((s, i) => (
                <div key={i} style={{ padding: '22px 0', textAlign: 'center', borderRight: i < 3 ? '1px solid rgba(255,255,255,0.08)' : 'none' }}>
                  <div style={{ fontSize: 34, fontWeight: 800, color: '#F5A623', fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>{s.value}</div>
                  <div style={{ fontSize: 12, color: '#A3ADB4', marginTop: 2, fontWeight: 500 }}><L field={s.label} lang={lang} /></div>
                </div>
              ))}
            </div>
          </div>

          {/* TASKS */}
          <section style={{ background: '#F5F6F7', padding: '72px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ marginBottom: 40 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.tasksLabel} lang={lang} /></div>
                <h2 style={{ fontSize: 30, fontWeight: 800, color: '#14181B', margin: 0, letterSpacing: '-0.02em' }}><L field={t.sections.tasksTitle} lang={lang} /></h2>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
                {TASKS.map((task, i) => (
                  <div key={i} style={{ background: '#fff', padding: '24px 24px', border: '1px solid #DDE1E4', cursor: 'pointer', transition: 'all 200ms', borderRadius: i === 0 ? '8px 0 0 0' : i === 2 ? '0 8px 0 0' : i === 3 ? '0 0 0 8px' : i === 5 ? '0 0 8px 0' : 0 }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = 'inset 0 0 0 2px #1F3A52' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = 'none' }}
                  >
                    <div style={{ fontSize: 26, marginBottom: 10 }}>{task.icon}</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#14181B', marginBottom: 6 }}>{lang === 'RO' ? task.ro : lang === 'EN' ? task.en : task.ru}</div>
                    <div style={{ fontSize: 13, color: '#5A646B', lineHeight: 1.55 }}>{lang === 'RO' ? task.descRo : lang === 'EN' ? task.descEn : task.descRu}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* EQUIPMENT */}
          <section style={{ padding: '72px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 36 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.equipmentLabel} lang={lang} /></div>
                  <h2 style={{ fontSize: 30, fontWeight: 800, color: '#14181B', margin: 0, letterSpacing: '-0.02em' }}><L field={t.sections.equipmentTitle} lang={lang} /></h2>
                </div>
                <button onClick={() => setPage('equipment')} style={{ background: 'none', border: 'none', fontSize: 14, fontWeight: 600, color: '#1F3A52', cursor: 'pointer', borderBottom: '1px solid #1F3A52', padding: '0 0 2px', fontFamily: 'Manrope, sans-serif' }}>
                  <L field={t.sections.equipmentAll} lang={lang} />
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
                {EQUIPMENT.map((eq, i) => (
                  <div key={i} style={{ border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden', background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.06)', transition: 'all 200ms' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.10)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)'; (e.currentTarget as HTMLElement).style.transform = 'none' }}
                  >
                    <div style={{ position: 'relative', height: 190, background: '#EDEFF1' }}>
                      <img src={eq.img} alt={eq.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      <div style={{ position: 'absolute', top: 10, left: 10 }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: eq.available ? 'rgba(46,125,79,0.9)' : 'rgba(192,57,43,0.85)', color: '#fff' }}>
                          {eq.available && <span className="pulse-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: '#fff' }} />}
                          {eq.available ? tr(t.equipment.free, lang) : tr(t.equipment.busy, lang)}
                        </span>
                      </div>
                    </div>
                    <div style={{ padding: '18px 18px 22px' }}>
                      <div style={{ fontSize: 15, fontWeight: 700, color: '#14181B', marginBottom: 12 }}>{eq.name}</div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
                        {[
                          { label: tr(t.equipment.capacity, lang), value: `${eq.capacity} т` },
                          { label: tr(t.equipment.reach, lang), value: `${eq.radius} м` },
                          { label: tr(t.equipment.height, lang), value: `${eq.height} м` },
                        ].map(spec => (
                          <div key={spec.label} style={{ background: '#F5F6F7', borderRadius: 4, padding: '7px 6px', textAlign: 'center' }}>
                            <div style={{ fontSize: 17, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{spec.value}</div>
                            <div style={{ fontSize: 9, fontWeight: 700, color: '#8A949B', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 2 }}>{spec.label}</div>
                          </div>
                        ))}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 16, fontWeight: 800, color: '#14181B', fontVariantNumeric: 'tabular-nums' }}>
                          {tr(t.equipment.priceFrom, lang)} {eq.price} lei/ч
                        </span>
                        <button style={{ padding: '7px 16px', background: '#F5A623', border: 'none', borderRadius: 4, color: '#14181B', fontSize: 12, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                          <L field={t.equipment.order} lang={lang} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* HOW IT WORKS */}
          <section style={{ background: '#1F3A52', padding: '72px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ marginBottom: 52 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.stepsLabel} lang={lang} /></div>
                <h2 style={{ fontSize: 30, fontWeight: 800, color: '#F2F4F5', margin: 0, letterSpacing: '-0.02em' }}><L field={t.sections.stepsTitle} lang={lang} /></h2>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0 }}>
                {[
                  { num: '01', title: t.steps.s1title, desc: t.steps.s1desc },
                  { num: '02', title: t.steps.s2title, desc: t.steps.s2desc },
                  { num: '03', title: t.steps.s3title, desc: t.steps.s3desc },
                  { num: '04', title: t.steps.s4title, desc: t.steps.s4desc },
                ].map((step, i) => (
                  <div key={i} style={{ paddingRight: i < 3 ? 36 : 0, borderRight: i < 3 ? '1px solid rgba(255,255,255,0.1)' : 'none', paddingLeft: i > 0 ? 36 : 0 }}>
                    <div style={{ fontSize: 44, fontWeight: 800, color: 'rgba(245,166,35,0.22)', fontVariantNumeric: 'tabular-nums', lineHeight: 1, marginBottom: 18 }}>{step.num}</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#F2F4F5', marginBottom: 8 }}><L field={step.title} lang={lang} /></div>
                    <div style={{ fontSize: 13, color: '#A3ADB4', lineHeight: 1.65 }}><L field={step.desc} lang={lang} /></div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* PRICING */}
          <section style={{ padding: '72px 0', background: '#F5F6F7' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.priceLabel} lang={lang} /></div>
                  <h2 style={{ fontSize: 30, fontWeight: 800, color: '#14181B', margin: '0 0 16px', letterSpacing: '-0.02em' }}><L field={t.sections.priceTitle} lang={lang} /></h2>
                  <p style={{ fontSize: 15, color: '#5A646B', lineHeight: 1.65, marginBottom: 28 }}><L field={t.pricing.text} lang={lang} /></p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {[
                      { label: t.pricing.rental, value: '1 200 lei/ч', note: 'LTM 1070, 4 ч' },
                      { label: t.pricing.dispatch, value: '800 lei', note: '< 15 km' },
                      { label: t.pricing.assembly, value: t.pricing.included, accent: true },
                      { label: t.pricing.operator, value: t.pricing.included, accent: true },
                      { label: t.pricing.insurance, value: t.pricing.included, accent: true },
                    ].map((row, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 14px', background: '#fff', borderRadius: 6, border: '1px solid #DDE1E4' }}>
                        <span style={{ fontSize: 13, color: '#14181B', fontWeight: 500 }}><L field={row.label} lang={lang} /></span>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: row.accent ? '#2E7D4F' : '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>
                            {typeof row.value === 'string' ? row.value : <L field={row.value} lang={lang} />}
                          </span>
                          {row.note && <div style={{ fontSize: 10, color: '#8A949B', marginTop: 1 }}>{row.note}</div>}
                        </div>
                      </div>
                    ))}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 14px', background: '#1F3A52', borderRadius: 6 }}>
                      <span style={{ fontSize: 14, color: '#F2F4F5', fontWeight: 600 }}><L field={t.pricing.total} lang={lang} /></span>
                      <span style={{ fontSize: 22, fontWeight: 800, color: '#F5A623', fontVariantNumeric: 'tabular-nums' }}>5 600 lei</span>
                    </div>
                  </div>
                </div>
                <div style={{ position: 'relative' }}>
                  <img src="https://images.unsplash.com/photo-1527335988388-b40ee248d80c?w=600&h=700&fit=crop&auto=format" alt="Montaj" style={{ width: '100%', height: 460, objectFit: 'cover', borderRadius: 8, display: 'block' }} />
                  <div style={{ position: 'absolute', bottom: 24, left: -24, background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: '14px 18px', boxShadow: '0 12px 32px rgba(0,0,0,0.16)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#8A949B', marginBottom: 3, letterSpacing: '0.06em', textTransform: 'uppercase' }}><L field={t.pricing.saving} lang={lang} /></div>
                    <div style={{ fontSize: 22, fontWeight: 800, color: '#2E7D4F', fontVariantNumeric: 'tabular-nums' }}>−18%</div>
                    <div style={{ fontSize: 11, color: '#5A646B' }}><L field={t.pricing.flexDate} lang={lang} /></div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* CASES */}
          <section style={{ padding: '72px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 36 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.casesLabel} lang={lang} /></div>
                  <h2 style={{ fontSize: 30, fontWeight: 800, color: '#14181B', margin: 0, letterSpacing: '-0.02em' }}><L field={t.sections.casesTitle} lang={lang} /></h2>
                </div>
                <button onClick={() => setPage('cases')} style={{ background: 'none', border: 'none', fontSize: 14, fontWeight: 600, color: '#1F3A52', cursor: 'pointer', borderBottom: '1px solid #1F3A52', padding: '0 0 2px', fontFamily: 'Manrope, sans-serif' }}>
                  <L field={t.sections.casesAll} lang={lang} />
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 2, borderRadius: 8, overflow: 'hidden' }}>
                {CASES.map((c, i) => (
                  <div key={i} style={{ position: 'relative', height: i === 0 ? 380 : 190, overflow: 'hidden', cursor: 'pointer' }}
                    onMouseEnter={e => { const img = e.currentTarget.querySelector('img') as HTMLImageElement; if (img) img.style.transform = 'scale(1.05)' }}
                    onMouseLeave={e => { const img = e.currentTarget.querySelector('img') as HTMLImageElement; if (img) img.style.transform = 'scale(1)' }}
                  >
                    <img src={c.img} alt={lang === 'RO' ? c.titleRo : lang === 'EN' ? c.titleEn : c.titleRu} style={{ width: '100%', height: '100%', objectFit: 'cover', transition: 'transform 400ms ease' }} />
                    <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(0deg, rgba(0,0,0,0.75) 0%, transparent 60%)' }} />
                    <div style={{ position: 'absolute', bottom: 16, left: 16, right: 16 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: '#F5A623', marginBottom: 3, letterSpacing: '0.06em' }}>{c.city} · {c.tech}</div>
                      <div style={{ fontSize: i === 0 ? 18 : 13, fontWeight: 700, color: '#fff', marginBottom: 3 }}>{lang === 'RO' ? c.titleRo : lang === 'EN' ? c.titleEn : c.titleRu}</div>
                      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>{lang === 'RO' ? c.resultRo : lang === 'EN' ? c.resultEn : c.resultRu}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* PARTNERS */}
          <section style={{ background: '#F5F6F7', padding: '64px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 72, alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.partnersLabel} lang={lang} /></div>
                <h2 style={{ fontSize: 28, fontWeight: 800, color: '#14181B', margin: '0 0 14px', letterSpacing: '-0.02em' }}><L field={t.sections.partnersTitle} lang={lang} /></h2>
                <p style={{ fontSize: 15, color: '#5A646B', lineHeight: 1.65, marginBottom: 22 }}><L field={t.sections.partnersText} lang={lang} /></p>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button style={{ padding: '9px 22px', background: '#1F3A52', border: 'none', borderRadius: 4, color: '#F2F4F5', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                    <L field={t.sections.becomePartner} lang={lang} />
                  </button>
                  <button style={{ padding: '9px 22px', background: 'transparent', border: '1px solid #C2C8CD', borderRadius: 4, color: '#14181B', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                    <L field={t.sections.portalDemo} lang={lang} />
                  </button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                {PARTNER_FEATURES.map((f, i) => (
                  <div key={i} style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: '16px 16px' }}>
                    <div style={{ fontSize: 22, marginBottom: 8 }}>{f.icon}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#14181B', marginBottom: 4 }}>{lang === 'RO' ? f.ro : lang === 'EN' ? f.en : f.ru}</div>
                    <div style={{ fontSize: 12, color: '#5A646B' }}>{lang === 'RO' ? f.dRo : lang === 'EN' ? f.dEn : f.dRu}</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* FAQ */}
          <section style={{ padding: '72px 0' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 80 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}><L field={t.sections.faqLabel} lang={lang} /></div>
                  <h2 style={{ fontSize: 30, fontWeight: 800, color: '#14181B', margin: '0 0 14px', letterSpacing: '-0.02em' }}><L field={t.sections.faqTitle} lang={lang} /></h2>
                  <p style={{ fontSize: 14, color: '#5A646B', lineHeight: 1.6, marginBottom: 20 }}><L field={t.sections.faqText} lang={lang} /></p>
                  <a href="tel:+37322123456" style={{ fontSize: 18, fontWeight: 800, color: '#1F3A52', textDecoration: 'none', fontVariantNumeric: 'tabular-nums' }}>+373 22 123-456</a>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {[
                    { q: t.faq.q1, a: t.faq.a1 },
                    { q: t.faq.q2, a: t.faq.a2 },
                    { q: t.faq.q3, a: t.faq.a3 },
                    { q: t.faq.q4, a: t.faq.a4 },
                  ].map((faq, i) => (
                    <div key={i} style={{ border: '1px solid #DDE1E4', borderRadius: 8, overflow: 'hidden' }}>
                      <button onClick={() => setOpenFaq(openFaq === i ? null : i)} style={{ width: '100%', padding: '16px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: openFaq === i ? '#1F3A52' : '#fff', border: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: 'Manrope, sans-serif' }}>
                        <span style={{ fontSize: 14, fontWeight: 600, color: openFaq === i ? '#F2F4F5' : '#14181B' }}><L field={faq.q} lang={lang} /></span>
                        <span style={{ fontSize: 18, color: openFaq === i ? '#F5A623' : '#8A949B', flexShrink: 0, marginLeft: 14 }}>{openFaq === i ? '−' : '+'}</span>
                      </button>
                      {openFaq === i && (
                        <div style={{ padding: '14px 18px', background: '#F5F6F7', fontSize: 13, color: '#5A646B', lineHeight: 1.65 }}>
                          <L field={faq.a} lang={lang} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* FOOTER */}
          <footer style={{ background: '#0F1214', padding: '56px 0 28px' }}>
            <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 40, paddingBottom: 40, borderBottom: '1px solid #2C3338' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ width: 28, height: 28, background: '#F5A623', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <span style={{ fontSize: 14, fontWeight: 800, color: '#14181B' }}>D</span>
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 800, color: '#F2F4F5' }}>DIMECON</span>
                  </div>
                  <p style={{ fontSize: 12, color: '#6F7A81', lineHeight: 1.7, marginBottom: 14, maxWidth: 260 }}>SA «Dimecon 11» · IDNO 1003600123456<br />MD-2001, Chișinău, str. Industrială, 14</p>
                  <a href="tel:+37322123456" style={{ fontSize: 14, fontWeight: 700, color: '#F2F4F5', textDecoration: 'none', display: 'block', marginBottom: 3, fontVariantNumeric: 'tabular-nums' }}>+373 22 123-456</a>
                  <a href="mailto:info@dimecon.md" style={{ fontSize: 12, color: '#A3ADB4', textDecoration: 'none' }}>info@dimecon.md</a>
                </div>
                {[
                  { title: t.footer.company, links: [{ l: t.footer.about, p: 'about' as NavPage }, { l: t.footer.fleet, p: 'equipment' as NavPage }, { l: t.footer.cases, p: 'cases' as NavPage }, { l: t.footer.contacts, p: 'contacts' as NavPage }] },
                  { title: t.footer.services, links: [{ l: t.footer.craneRental, p: 'services' as NavPage }, { l: t.footer.transport, p: 'transport' as NavPage }, { l: t.footer.goods, p: 'goods' as NavPage }, { l: t.footer.partners, p: 'contacts' as NavPage }] },
                  { title: t.footer.documents, links: [{ l: t.footer.offer, p: 'contacts' as NavPage }, { l: t.footer.privacy, p: 'contacts' as NavPage }, { l: t.footer.cookies, p: 'contacts' as NavPage }, { l: t.footer.requisites, p: 'contacts' as NavPage }] },
                ].map((col, ci) => (
                  <div key={ci}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#6F7A81', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 14 }}><L field={col.title} lang={lang} /></div>
                    {col.links.map((link, li) => (
                      <button key={li} onClick={() => setPage(link.p)} style={{ display: 'block', fontSize: 12, color: '#A3ADB4', background: 'none', border: 'none', padding: '0 0 8px', cursor: 'pointer', fontFamily: 'Manrope, sans-serif', textAlign: 'left', transition: 'color 150ms' }}
                        onMouseEnter={e => { (e.target as HTMLElement).style.color = '#F2F4F5' }}
                        onMouseLeave={e => { (e.target as HTMLElement).style.color = '#A3ADB4' }}
                      >
                        <L field={link.l} lang={lang} />
                      </button>
                    ))}
                  </div>
                ))}
              </div>
              <div style={{ paddingTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#6F7A81', fontVariantNumeric: 'tabular-nums' }}>© {new Date().getFullYear()} SA «Dimecon 11». <L field={t.footer.copyright} lang={lang} /></span>
                <div style={{ display: 'flex', gap: 6 }}>
                  {LANGS.map(l => (
                    <button key={l} onClick={() => setLang(l)} style={{ padding: '3px 8px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', background: lang === l ? '#F5A623' : '#1E2327', color: lang === l ? '#14181B' : '#6F7A81', fontFamily: 'Manrope, sans-serif' }}>
                      {l}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </footer>
        </>
      )}
    </div>
  )
}
