import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const TIMELINE = [
  { year: '1968', ru: 'Основание предприятия. Первые башенные краны на стройках Кишинёва.', ro: 'Fondarea întreprinderii. Primele macarale turn pe șantierele din Chișinău.', en: 'Company founded. First tower cranes on Chisinau construction sites.' },
  { year: '1991', ru: 'Реорганизация в SA «Dimecon 11». Расширение парка автокранами.', ro: 'Reorganizare în SA «Dimecon 11». Extinderea parcului cu automacara.', en: 'Reorganised as SA «Dimecon 11». Fleet expanded with mobile cranes.' },
  { year: '2005', ru: 'Первый Liebherr LTM 1100. Выход на рынок негабаритного транспорта.', ro: 'Primul Liebherr LTM 1100. Intrare pe piața transportului supragabaritic.', en: 'First Liebherr LTM 1100 acquired. Entry into oversized transport market.' },
  { year: '2015', ru: 'Сертификация ISO 9001. Запуск онлайн-кабинета для партнёров.', ro: 'Certificare ISO 9001. Lansarea cabinetului online pentru parteneri.', en: 'ISO 9001 certification. Launch of online partner portal.' },
  { year: '2020', ru: 'Парк достигает 12 единиц. Запуск платформы цифрового подбора.', ro: 'Parcul ajunge la 12 utilaje. Lansarea platformei digitale de selecție.', en: 'Fleet reaches 12 units. Launch of digital selection platform.' },
  { year: '2024', ru: 'Новая цифровая платформа dimecon.md. Грузоподъёмность до 165 т.', ro: 'Noua platformă digitală dimecon.md. Capacitate de ridicare până la 165 t.', en: 'New digital platform dimecon.md. Lift capacity up to 165 t.' },
]

const TEAM = [
  { name: 'Ion Duma', role: { RU: 'Генеральный директор', RO: 'Director general', EN: 'CEO' }, exp: '28' },
  { name: 'Mihail Dumitraș', role: { RU: 'Главный инженер', RO: 'Inginer șef', EN: 'Chief Engineer' }, exp: '22' },
  { name: 'Svetlana Cozu', role: { RU: 'Коммерческий директор', RO: 'Director comercial', EN: 'Commercial Director' }, exp: '15' },
  { name: 'Andrei Chiriac', role: { RU: 'Начальник диспетчерской', RO: 'Șef dispecerat', EN: 'Dispatch Manager' }, exp: '11' },
]

type Lang = 'RO' | 'RU' | 'EN'

export default function AboutPage() {
  const { lang } = useLang()

  return (
    <div style={{ background: '#fff', minHeight: '100vh' }}>
      {/* Hero */}
      <div style={{ background: '#1F3A52', padding: '56px 0' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 12 }}>
            {tr(t.nav.about, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 40, fontWeight: 800, color: '#F2F4F5', margin: '0 0 16px', letterSpacing: '-0.02em' }}>
            {tr(t.pages.aboutPage.title, lang)}
          </h1>
          <p style={{ fontSize: 18, color: '#A3ADB4', margin: 0, maxWidth: 600 }}>
            {tr(t.pages.aboutPage.subtitle, lang)}
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '64px 80px 80px' }}>
        {/* Timeline */}
        <div style={{ marginBottom: 72 }}>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 36px', letterSpacing: '-0.01em' }}>
            {tr(t.pages.aboutPage.history, lang)}
          </h2>
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', left: 56, top: 0, bottom: 0, width: 2, background: '#DDE1E4' }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {TIMELINE.map((item, i) => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '112px 1fr', gap: 24, paddingBottom: 28, alignItems: 'flex-start' }}>
                  <div style={{ textAlign: 'right', position: 'relative' }}>
                    <span style={{ fontSize: 16, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{item.year}</span>
                    <div style={{ position: 'absolute', right: -31, top: 5, width: 10, height: 10, borderRadius: '50%', background: i === TIMELINE.length - 1 ? '#F5A623' : '#1F3A52', border: '2px solid #fff', boxShadow: '0 0 0 2px #1F3A52' }} />
                  </div>
                  <div style={{ paddingLeft: 8, paddingTop: 2 }}>
                    <div style={{ fontSize: 14, color: '#14181B', lineHeight: 1.6 }}>
                      {lang === 'RO' ? item.ro : lang === 'EN' ? item.en : item.ru}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, marginBottom: 72 }}>
          {[
            { value: '56', label: { RU: 'лет на рынке', RO: 'ani pe piață', EN: 'years in business' } },
            { value: '12', label: { RU: 'единиц техники', RO: 'utilaje în parc', EN: 'fleet units' } },
            { value: '47', label: { RU: 'сертифицированных операторов', RO: 'operatori certificați', EN: 'certified operators' } },
            { value: '500+', label: { RU: 'завершённых объектов', RO: 'obiecte finalizate', EN: 'completed projects' } },
          ].map((s, i) => (
            <div key={i} style={{ background: i === 0 ? '#1F3A52' : '#F5F6F7', border: '1px solid #DDE1E4', padding: '28px 24px', textAlign: 'center', borderRadius: i === 0 ? '8px 0 0 8px' : i === 3 ? '0 8px 8px 0' : 0 }}>
              <div style={{ fontSize: 42, fontWeight: 800, color: i === 0 ? '#F5A623' : '#1F3A52', fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em' }}>{s.value}</div>
              <div style={{ fontSize: 13, color: i === 0 ? '#A3ADB4' : '#5A646B', marginTop: 6, fontWeight: 500 }}>{s.label[lang as Lang]}</div>
            </div>
          ))}
        </div>

        {/* Team */}
        <div style={{ marginBottom: 64 }}>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 28px', letterSpacing: '-0.01em' }}>
            {tr(t.pages.aboutPage.team, lang)}
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {TEAM.map((member, i) => (
              <div key={i} style={{ background: '#F5F6F7', border: '1px solid #DDE1E4', borderRadius: 8, padding: '24px 20px', textAlign: 'center' }}>
                <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#1F3A52', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', fontSize: 22, fontWeight: 800, color: '#F5A623' }}>
                  {member.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#14181B', marginBottom: 4 }}>{member.name}</div>
                <div style={{ fontSize: 12, color: '#5A646B', marginBottom: 8 }}>{member.role[lang as Lang]}</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#F5A623' }}>
                  {member.exp} {lang === 'RO' ? 'ani exp.' : lang === 'EN' ? 'yrs exp.' : 'лет опыта'}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Documents */}
        <div>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 20px', letterSpacing: '-0.01em' }}>
            {tr(t.pages.aboutPage.docs, lang)}
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {[
              { ru: 'Свидетельство о регистрации', ro: 'Certificat de înregistrare', en: 'Registration certificate' },
              { ru: 'ISO 9001:2015 — Система менеджмента качества', ro: 'ISO 9001:2015 — Sistem de management al calității', en: 'ISO 9001:2015 — Quality management system' },
              { ru: 'Лицензия на перевозку негабаритных грузов', ro: 'Licență transport supragabaritic', en: 'Oversized cargo transport licence' },
              { ru: 'Сертификаты операторов НАРМ', ro: 'Certificate operatori ANRE', en: 'Operator certificates (NARM)' },
              { ru: 'Паспорта техники (Liebherr, Grove, Potain)', ro: 'Pașapoarte tehnice (Liebherr, Grove, Potain)', en: 'Equipment passports (Liebherr, Grove, Potain)' },
              { ru: 'Договор страхования гражданской ответственности', ro: 'Contract asigurare răspundere civilă', en: 'Public liability insurance policy' },
            ].map((doc, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#fff', border: '1px solid #DDE1E4', borderRadius: 6, alignItems: 'center', cursor: 'pointer', transition: 'all 150ms' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = '#1F3A52' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#DDE1E4' }}
              >
                <span style={{ fontSize: 18 }}>📄</span>
                <span style={{ fontSize: 13, color: '#14181B', fontWeight: 500 }}>{lang === 'RO' ? doc.ro : lang === 'EN' ? doc.en : doc.ru}</span>
                <span style={{ marginLeft: 'auto', fontSize: 13, color: '#1F3A52' }}>↓</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
