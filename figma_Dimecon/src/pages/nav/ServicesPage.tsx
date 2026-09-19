import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

const SERVICES = [
  { icon: '🏗️', ru: 'Монтаж металлоконструкций', ro: 'Montaj structuri metalice', en: 'Steel structure assembly', desc: { RU: 'Балки, фермы, колонны, перекрытия — точный монтаж с ППР', RO: 'Grinzi, ferme, stâlpi, plăci — montaj precis conform PPR', EN: 'Beams, trusses, columns, slabs — precise installation with work plan' }, price: 'от 1 200 lei/ч' },
  { icon: '🧱', ru: 'Подъём строительных материалов', ro: 'Ridicare materiale de construcție', en: 'Lifting construction materials', desc: { RU: 'Поддоны, блоки, плиты перекрытий, кирпич', RO: 'Paleți, blocuri, plăci de planșeu, cărămidă', EN: 'Pallets, blocks, floor slabs, bricks' }, price: 'от 800 lei/ч' },
  { icon: '🏠', ru: 'Монтаж бытовок и модулей', ro: 'Montaj barăci și module', en: 'Siting cabins & modules', desc: { RU: 'Контейнеры, вахтовые городки, торговые павильоны', RO: 'Containere, orășele muncitorești, pavilioane comerciale', EN: 'Containers, worker camps, retail pavilions' }, price: 'от 900 lei/вызов' },
  { icon: '⚡', ru: 'Промышленное оборудование', ro: 'Echipamente industriale', en: 'Industrial equipment', desc: { RU: 'Генераторы, трансформаторы, насосные станции', RO: 'Generatoare, transformatoare, stații de pompare', EN: 'Generators, transformers, pump stations' }, price: 'от 1 500 lei/ч' },
  { icon: '🌳', ru: 'Ландшафтные работы', ro: 'Lucrări peisagistice', en: 'Landscape works', desc: { RU: 'Крупномерные деревья, фонтаны, малые формы', RO: 'Copaci maturi, fântâni, forme mici de arhitectură', EN: 'Mature trees, fountains, small architectural forms' }, price: 'от 700 lei/ч' },
  { icon: '🚢', ru: 'Негабаритный транспорт', ro: 'Transport supragabaritic', en: 'Oversized transport', desc: { RU: 'Спецразрешения, сопровождение, маршрут', RO: 'Permise speciale, escortă, planificarea rutei', EN: 'Special permits, escort, route planning' }, price: 'по запросу' },
  { icon: '🔩', ru: 'Демонтаж конструкций', ro: 'Demontarea structurilor', en: 'Structure dismantling', desc: { RU: 'Безопасный демонтаж с утилизацией материалов', RO: 'Demontare sigură cu reciclarea materialelor', EN: 'Safe dismantling with material disposal' }, price: 'от 1 100 lei/ч' },
  { icon: '📐', ru: 'Инженерный надзор', ro: 'Supervizare inginerească', en: 'Engineering supervision', desc: { RU: 'ИТД, ППР, авторский надзор', RO: 'Documentație inginerească, PPR, supraveghere de autor', EN: 'Technical documentation, work plans, author supervision' }, price: 'от 200 lei/ч' },
  { icon: '🏭', ru: 'Монтаж технологических линий', ro: 'Montaj linii tehnologice', en: 'Process line installation', desc: { RU: 'Пищевое, химическое, производственное оборудование', RO: 'Echipamente alimentare, chimice, de producție', EN: 'Food, chemical, production equipment' }, price: 'от 1 800 lei/ч' },
  { icon: '🌉', ru: 'Мостовые и путепроводные работы', ro: 'Lucrări de poduri și pasaje', en: 'Bridge & overpass works', desc: { RU: 'Монтаж пролётных строений, опор', RO: 'Montaj tablier, pile de pod', EN: 'Span assembly, bridge piers' }, price: 'по запросу' },
  { icon: '🏗️', ru: 'Аренда башенного крана с монтажом', ro: 'Închiriere macara turn cu montaj', en: 'Tower crane with assembly', desc: { RU: 'Полный цикл: монтаж, аренда, демонтаж', RO: 'Ciclu complet: montaj, închiriere, demontaj', EN: 'Full cycle: assembly, rental, disassembly' }, price: 'от 850 lei/ч' },
  { icon: '📦', ru: 'Складские и логистические работы', ro: 'Lucrări logistice și de depozitare', en: 'Warehouse & logistics works', desc: { RU: 'Разгрузка, перестановка крупногабаритных грузов', RO: 'Descărcare, repozitionare mărfuri supradimensionate', EN: 'Unloading, repositioning of oversized goods' }, price: 'от 600 lei/ч' },
  { icon: '💧', ru: 'Монтаж инженерных сетей', ro: 'Montaj rețele inginerești', en: 'Engineering network installation', desc: { RU: 'Трубопроводы, резервуары, очистные сооружения', RO: 'Conducte, rezervoare, stații de epurare', EN: 'Pipelines, tanks, treatment plants' }, price: 'от 1 300 lei/ч' },
  { icon: '⚓', ru: 'Аварийно-спасательные работы', ro: 'Lucrări de urgență și salvare', en: 'Emergency rescue works', desc: { RU: 'Извлечение техники, ликвидация завалов', RO: 'Extracție utilaje, lichidare dărâmături', EN: 'Equipment extraction, debris clearance' }, price: 'по вызову' },
]

type Lang = 'RO' | 'RU' | 'EN'

export default function ServicesPage() {
  const { lang } = useLang()

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        <div style={{ marginBottom: 40 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.nav.services, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 12px', letterSpacing: '-0.02em' }}>
            {tr(t.pages.servicesPage.title, lang)}
          </h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{tr(t.pages.servicesPage.subtitle, lang)}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}>
          {SERVICES.map((svc, i) => {
            const title = lang === 'RO' ? svc.ro : lang === 'EN' ? svc.en : svc.ru
            const desc = svc.desc[lang as Lang]
            return (
              <div key={i} style={{ background: '#fff', border: '1px solid #DDE1E4', padding: '24px 24px', cursor: 'pointer', transition: 'all 200ms', borderRadius: i === 0 ? '8px 0 0 0' : i === 2 ? '0 8px 0 0' : i === 11 ? '0 0 0 8px' : i === 13 ? '0 0 8px 0' : 0 }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F6F7'; (e.currentTarget as HTMLElement).style.boxShadow = 'inset 0 0 0 2px #1F3A52' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = '#fff'; (e.currentTarget as HTMLElement).style.boxShadow = 'none' }}
              >
                <div style={{ fontSize: 30, marginBottom: 12 }}>{svc.icon}</div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#14181B', marginBottom: 6 }}>{title}</div>
                <div style={{ fontSize: 13, color: '#5A646B', lineHeight: 1.55, marginBottom: 12 }}>{desc}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#F5A623' }}>{svc.price}</div>
              </div>
            )
          })}
        </div>

        <div style={{ marginTop: 40, background: '#1F3A52', borderRadius: 12, padding: '32px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#F2F4F5', marginBottom: 6 }}>
              {lang === 'RO' ? 'Nu ați găsit serviciul dorit?' : lang === 'EN' ? "Didn't find what you need?" : 'Не нашли нужную услугу?'}
            </div>
            <div style={{ fontSize: 14, color: '#A3ADB4' }}>
              {lang === 'RO' ? 'Sunați-ne — vom găsi o soluție' : lang === 'EN' ? "Call us — we'll find a solution" : 'Позвоните нам — найдём решение'}
            </div>
          </div>
          <a href="tel:+37322123456" style={{ padding: '12px 28px', background: '#F5A623', borderRadius: 6, color: '#14181B', fontSize: 15, fontWeight: 800, textDecoration: 'none', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
            +373 22 123-456
          </a>
        </div>
      </div>
    </div>
  )
}
