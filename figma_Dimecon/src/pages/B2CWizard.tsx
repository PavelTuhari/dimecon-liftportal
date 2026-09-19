import { useState } from 'react'

const STEPS = ['Задача', 'Груз', 'Высота', 'Вылет', 'Условия', 'Дата и место', 'Результат']

const TASK_TYPES = [
  { id: 'montazh', icon: '🏗️', title: 'Монтаж конструкций', desc: 'Балки, фермы, перекрытия' },
  { id: 'podjem', icon: '📦', title: 'Подъём груза', desc: 'Оборудование, ёмкости' },
  { id: 'bytovka', icon: '🏠', title: 'Бытовка / модуль', desc: 'Контейнеры, павильоны' },
  { id: 'derevo', icon: '🌳', title: 'Крупномерное дерево', desc: 'Ландшафтные работы' },
  { id: 'mashina', icon: '🚗', title: 'Автомобиль / техника', desc: 'Извлечение, установка' },
  { id: 'negabrit', icon: '🔩', title: 'Негабаритный груз', desc: 'Трансформаторы, резервуары' },
  { id: 'stroit', icon: '🧱', title: 'Строительные материалы', desc: 'Кирпич, блоки, плиты' },
  { id: 'drugoe', icon: '❓', title: 'Другое', desc: 'Опишем вместе' },
]

const PRESETS = [
  { id: 'bytovka', icon: '🏠', title: 'Бытовка 6м', weight: '≈ 3–5 т' },
  { id: 'paleta', icon: '🧱', title: 'Поддон кирпича', weight: '≈ 1–1,5 т' },
  { id: 'generator', icon: '⚡', title: 'Генератор 500 кВт', weight: '≈ 5–8 т' },
  { id: 'balka', icon: '🏗️', title: 'Стальная балка', weight: '≈ 2–6 т' },
  { id: 'neznayu', icon: '❓', title: 'Не знаю вес', weight: 'Помогу рассчитать' },
]

const SITUATIONS = [
  { id: 'open', title: 'Открытая площадка', desc: 'Кран стоит рядом с грузом, препятствий нет', meters: '≤ 12 м' },
  { id: 'fence', title: 'Через забор', desc: 'Груз за забором или в углублении', meters: '12–25 м' },
  { id: 'building', title: 'Через здание', desc: 'Нужно подать «через крышу» соседнего здания', meters: '25–40 м' },
  { id: 'deep', title: 'Узкий двор', desc: 'Двор-колодец, кран снаружи', meters: '> 40 м' },
]

const RESULTS = [
  {
    tag: '⚡ Оптимально',
    tagColor: '#2E7D4F',
    name: 'Liebherr LTM 1070-4.2',
    type: 'Автокран · 70 т',
    capacity: 70, radius: 48, height: 62,
    price: '5 200', breakdown: true,
    reason: 'Грузоподъёмность при вашем вылете — 12 т при запросе 5 т. Запас 2,4× даёт безопасность и возможность добавить стропы.',
    img: 'https://images.unsplash.com/photo-1563391017873-6e6beab67fed?w=300&h=200&fit=crop&auto=format',
  },
  {
    tag: '💰 Дешевле',
    tagColor: '#2D6CB5',
    name: 'Grove GMK3060L',
    type: 'Автокран · 60 т',
    capacity: 60, radius: 40, height: 56,
    price: '4 100', breakdown: false,
    reason: 'Подходит по параметрам, но с меньшим запасом по грузоподъёмности — 8,2 т vs 5 т запроса. Приемлемо, если груз взвешен точно.',
    img: 'https://images.unsplash.com/photo-1535732759880-bbd5c7265e3f?w=300&h=200&fit=crop&auto=format',
  },
  {
    tag: '🛡️ С запасом',
    tagColor: '#C77700',
    name: 'Liebherr LTM 1100-5.2',
    type: 'Автокран · 100 т',
    capacity: 100, radius: 60, height: 80,
    price: '7 800', breakdown: false,
    reason: 'Избыточная мощность для этой задачи, но единственный вариант, если груз тяжелее заявленного или появятся дополнительные работы.',
    img: 'https://images.unsplash.com/photo-1485083269755-a7b559a4fe5e?w=300&h=200&fit=crop&auto=format',
  },
]

export default function B2CWizard() {
  const [step, setStep] = useState(0)
  const [selected, setSelected] = useState<string>('')
  const [preset, setPreset] = useState<string>('')
  const [height, setHeight] = useState(12)
  const [situation, setSituation] = useState<string>('')
  const [chosenResult, setChosenResult] = useState<number | null>(null)
  const [showBreakdown, setShowBreakdown] = useState(false)

  const progress = ((step + 1) / STEPS.length) * 100

  return (
    <div style={{ fontFamily: 'Manrope, sans-serif', background: '#F5F6F7', minHeight: '100vh' }}>
      {/* Wizard Header */}
      <div style={{ background: '#1F3A52', padding: '0 0 0' }}>
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '16px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 28, height: 28, background: '#F5A623', borderRadius: 3, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 800, color: '#14181B' }}>D</span>
              </div>
              <span style={{ fontSize: 14, fontWeight: 700, color: '#F2F4F5' }}>Подбор крана</span>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: '#A3ADB4' }}>Шаг {step + 1} из {STEPS.length}</span>
              <button style={{ padding: '5px 12px', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, background: 'transparent', color: '#A3ADB4', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                📞 Помощь
              </button>
            </div>
          </div>
          {/* Progress bar */}
          <div style={{ height: 3, background: 'rgba(255,255,255,0.12)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${progress}%`, background: '#F5A623', borderRadius: 2, transition: 'width 300ms ease' }} />
          </div>
          {/* Step labels */}
          <div style={{ display: 'flex', marginTop: 10, gap: 4 }}>
            {STEPS.map((s, i) => (
              <button key={i} onClick={() => i <= step && setStep(i)} style={{
                flex: 1, padding: '3px 0', border: 'none', background: 'transparent',
                fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
                color: i === step ? '#F5A623' : i < step ? '#A3ADB4' : '#3D454B',
                cursor: i <= step ? 'pointer' : 'default',
                fontFamily: 'Manrope, sans-serif', textAlign: 'center',
              }}>
                {i < step ? '✓ ' : ''}{s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 24px' }} className="slide-up">
        {/* Step 0: Task type */}
        {step === 0 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Что нужно сделать?</h2>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 24px' }}>Выберите тип задачи — это помогает подобрать подходящую технику</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              {TASK_TYPES.map(t => (
                <button key={t.id} onClick={() => setSelected(t.id)} style={{
                  padding: '20px 16px', border: `2px solid ${selected === t.id ? '#1F3A52' : '#DDE1E4'}`,
                  borderRadius: 8, background: selected === t.id ? '#EEF2F5' : '#fff',
                  cursor: 'pointer', textAlign: 'left', fontFamily: 'Manrope, sans-serif',
                  transition: 'all 150ms',
                }}>
                  <div style={{ fontSize: 28, marginBottom: 8 }}>{t.icon}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#14181B', marginBottom: 4 }}>{t.title}</div>
                  <div style={{ fontSize: 12, color: '#8A949B' }}>{t.desc}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 1: Cargo */}
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Что поднимаем?</h2>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 24px' }}>Выберите из типичных грузов или введите вес вручную</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
              {PRESETS.map(p => (
                <button key={p.id} onClick={() => setPreset(p.id)} style={{
                  padding: '16px 12px', border: `2px solid ${preset === p.id ? '#1F3A52' : '#DDE1E4'}`,
                  borderRadius: 8, background: preset === p.id ? '#EEF2F5' : '#fff',
                  cursor: 'pointer', textAlign: 'center', fontFamily: 'Manrope, sans-serif',
                }}>
                  <div style={{ fontSize: 26, marginBottom: 8 }}>{p.icon}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#14181B', marginBottom: 3 }}>{p.title}</div>
                  <div style={{ fontSize: 11, color: '#F5A623', fontWeight: 600 }}>{p.weight}</div>
                </button>
              ))}
            </div>
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#14181B', marginBottom: 12 }}>Или укажите вес точно</div>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <input type="number" placeholder="0,0" style={{ width: 120, padding: '10px 12px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums', fontFamily: 'Manrope, sans-serif', color: '#14181B' }} />
                <span style={{ fontSize: 16, fontWeight: 600, color: '#5A646B' }}>тонн</span>
                <span style={{ fontSize: 13, color: '#8A949B', marginLeft: 8 }}>Если не знаете — воспользуйтесь калькулятором массы →</span>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Height */}
        {step === 2 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 8px', letterSpacing: '-0.02em' }}>На какую высоту?</h2>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 32px' }}>Высота подъёма груза от земли до места установки</p>
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 12, padding: 32 }}>
              {/* Building silhouette visualization */}
              <div style={{ position: 'relative', height: 200, marginBottom: 24, display: 'flex', alignItems: 'flex-end', gap: 2, justifyContent: 'center' }}>
                {/* Building */}
                <div style={{ width: 80, background: '#EDEFF1', border: '1px solid #DDE1E4', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', position: 'relative', borderRadius: '4px 4px 0 0' }}>
                  {Array.from({ length: Math.ceil(height / 3) }).map((_, i) => (
                    <div key={i} style={{ height: 24, borderBottom: '1px solid #DDE1E4', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                      <div style={{ width: 10, height: 12, background: i < Math.ceil(height / 3) - 1 ? '#A3ADB4' : '#F5A623', borderRadius: 1 }} />
                      <div style={{ width: 10, height: 12, background: '#A3ADB4', borderRadius: 1 }} />
                    </div>
                  ))}
                </div>
                {/* Height indicator */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: Math.min(height * 8, 192), marginLeft: 16 }}>
                  <div style={{ background: '#F5A623', color: '#14181B', padding: '4px 10px', borderRadius: 4, fontSize: 16, fontWeight: 800, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                    {height} м
                  </div>
                  <div style={{ width: 2, flex: 1, background: '#F5A623', marginTop: 4, borderRadius: 1 }} />
                </div>
              </div>
              {/* Slider */}
              <div>
                <input type="range" min={2} max={80} value={height} onChange={e => setHeight(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#F5A623', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#8A949B', marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
                  <span>2 м</span>
                  <span>20 м (≈6 эт)</span>
                  <span>40 м (≈12 эт)</span>
                  <span>80 м</span>
                </div>
              </div>
              <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                {[6, 12, 20, 32, 45, 60].map(h => (
                  <button key={h} onClick={() => setHeight(h)} style={{
                    padding: '5px 12px', border: `1px solid ${height === h ? '#1F3A52' : '#DDE1E4'}`,
                    borderRadius: 4, background: height === h ? '#1F3A52' : '#fff',
                    color: height === h ? '#F2F4F5' : '#5A646B', fontSize: 12, fontWeight: 600,
                    cursor: 'pointer', fontFamily: 'Manrope, sans-serif', fontVariantNumeric: 'tabular-nums',
                  }}>{h} м</button>
                ))}
                <button style={{ padding: '5px 12px', border: '1px solid #DDE1E4', borderRadius: 4, background: '#fff', color: '#5A646B', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                  Ниже уровня земли
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Step 3: Reach */}
        {step === 3 && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 8px', letterSpacing: '-0.02em' }}>Как далеко груз от крана?</h2>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 24px' }}>Выберите вашу ситуацию — это «вылет» крана</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
              {SITUATIONS.map(s => (
                <button key={s.id} onClick={() => setSituation(s.id)} style={{
                  padding: 20, border: `2px solid ${situation === s.id ? '#1F3A52' : '#DDE1E4'}`,
                  borderRadius: 8, background: situation === s.id ? '#EEF2F5' : '#fff',
                  cursor: 'pointer', textAlign: 'left', fontFamily: 'Manrope, sans-serif',
                  display: 'flex', gap: 16, alignItems: 'flex-start',
                }}>
                  {/* Schematic top-view illustration */}
                  <div style={{ width: 80, height: 70, flexShrink: 0, background: '#F5F6F7', borderRadius: 6, border: '1px solid #DDE1E4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>
                    {s.id === 'open' ? '🏗️' : s.id === 'fence' ? '🧱' : s.id === 'building' ? '🏢' : '🏚️'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#14181B', marginBottom: 4 }}>{s.title}</div>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', background: 'rgba(245,166,35,0.1)', padding: '2px 8px', borderRadius: 4 }}>{s.meters}</span>
                    </div>
                    <div style={{ fontSize: 13, color: '#5A646B', lineHeight: 1.5 }}>{s.desc}</div>
                  </div>
                </button>
              ))}
            </div>
            <div style={{ marginTop: 16, background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: '#5A646B' }}>Знаю точный вылет:</span>
              <input type="number" placeholder="0" style={{ width: 80, padding: '6px 10px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 16, fontWeight: 700, fontVariantNumeric: 'tabular-nums', fontFamily: 'Manrope, sans-serif' }} />
              <span style={{ fontSize: 14, color: '#5A646B' }}>м</span>
            </div>
          </div>
        )}

        {/* Steps 4-5: simplified */}
        {(step === 4 || step === 5) && (
          <div>
            <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: '0 0 8px', letterSpacing: '-0.02em' }}>
              {step === 4 ? 'Условия на объекте' : 'Когда и где?'}
            </h2>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 24px' }}>
              {step === 4 ? 'Отметьте всё, что актуально для вашего объекта' : 'Выберите дату и укажите адрес'}
            </p>
            {step === 4 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { id: 'lek', label: 'Есть ЛЭП или воздушные кабели рядом', tooltip: 'При наличии ЛЭП может потребоваться согласование с энергетиками' },
                  { id: 'narrow', label: 'Узкий проезд (менее 4 метров)', tooltip: 'Часть кранов требует более широкого заезда' },
                  { id: 'soft', label: 'Мягкий/насыпной грунт или подвал под площадкой', tooltip: 'Потребуются дополнительные подкладные плиты' },
                  { id: 'night', label: 'Работа ночью или в выходные', tooltip: 'Коэффициент 1,2 к почасовой ставке' },
                  { id: 'obstacles', label: 'Препятствия сверху (деревья, другие краны)', tooltip: 'Влияет на выбор конфигурации стрелы' },
                ].map(item => (
                  <label key={item.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 16px', background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, cursor: 'pointer' }}>
                    <input type="checkbox" style={{ marginTop: 2, accentColor: '#1F3A52', width: 16, height: 16 }} />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: '#14181B' }}>{item.label}</div>
                      <div style={{ fontSize: 12, color: '#8A949B', marginTop: 2 }}>ℹ️ {item.tooltip}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}
            {step === 5 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#14181B', marginBottom: 12 }}>Дата работ</div>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <input type="date" style={{ padding: '10px 12px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 14, fontFamily: 'Manrope, sans-serif' }} />
                    <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13, color: '#5A646B', cursor: 'pointer' }}>
                      <input type="checkbox" style={{ accentColor: '#1F3A52' }} />
                      Гибкая дата <span style={{ color: '#2E7D4F', fontWeight: 700 }}>−10%</span>
                    </label>
                  </div>
                </div>
                <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#14181B', marginBottom: 12 }}>Длительность</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {['4 ч', '8 ч', '12 ч', '1 смена', 'Несколько дней'].map(d => (
                      <button key={d} style={{ padding: '7px 14px', border: '1px solid #DDE1E4', borderRadius: 4, background: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', color: '#5A646B' }}>{d}</button>
                    ))}
                  </div>
                </div>
                <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 8, padding: 20 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#14181B', marginBottom: 12 }}>Адрес объекта</div>
                  <input type="text" placeholder="Введите адрес или кликните на карте" style={{ width: '100%', padding: '10px 12px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 14, fontFamily: 'Manrope, sans-serif', boxSizing: 'border-box' }} />
                  <div style={{ height: 160, background: '#F5F6F7', borderRadius: 4, marginTop: 8, border: '1px solid #DDE1E4', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8A949B', fontSize: 13 }}>
                    🗺️ Карта для выбора точки
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 6: Results */}
        {step === 6 && (
          <div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
              <h2 style={{ fontSize: 26, fontWeight: 800, color: '#14181B', margin: 0, letterSpacing: '-0.02em' }}>Подбор завершён</h2>
              <span style={{ padding: '3px 10px', background: 'rgba(46,125,79,0.1)', color: '#2E7D4F', borderRadius: 4, fontSize: 12, fontWeight: 700 }}>3 варианта</span>
            </div>
            <p style={{ fontSize: 15, color: '#5A646B', margin: '0 0 24px' }}>На основе ваших параметров: 5 т · {height} м высота · до 18 м вылет</p>

            {/* Safety disclaimer */}
            <div style={{ background: '#FFF8ED', border: '1px solid rgba(199,119,0,0.3)', borderRadius: 8, padding: '12px 16px', marginBottom: 20, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
              <div style={{ fontSize: 13, color: '#8A5C00', lineHeight: 1.5 }}>
                <strong>Безопасность прежде всего.</strong> Все работы выполняются лицензированными операторами по ППР. Финальная грузоподъёмность определяется на объекте после осмотра площадки.
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {RESULTS.map((r, i) => (
                <div key={i} onClick={() => setChosenResult(i)} style={{
                  background: '#fff', border: `2px solid ${chosenResult === i ? '#1F3A52' : '#DDE1E4'}`,
                  borderRadius: 12, overflow: 'hidden', cursor: 'pointer',
                  boxShadow: chosenResult === i ? '0 4px 16px rgba(31,58,82,0.15)' : '0 1px 4px rgba(0,0,0,0.06)',
                  transition: 'all 200ms',
                }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', minHeight: 140 }}>
                    <div style={{ position: 'relative' }}>
                      <img src={r.img} alt={r.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      <div style={{ position: 'absolute', top: 10, left: 10 }}>
                        <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700, background: r.tagColor, color: '#fff' }}>{r.tag}</span>
                      </div>
                    </div>
                    <div style={{ padding: '20px 24px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontSize: 16, fontWeight: 800, color: '#14181B', marginBottom: 2 }}>{r.name}</div>
                          <div style={{ fontSize: 13, color: '#8A949B', marginBottom: 12 }}>{r.type}</div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <div style={{ fontSize: 24, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>{r.price} lei</div>
                          <div style={{ fontSize: 11, color: '#8A949B' }}>предварительно</div>
                          {r.breakdown && (
                            <button onClick={e => { e.stopPropagation(); setShowBreakdown(!showBreakdown) }} style={{ marginTop: 4, fontSize: 11, fontWeight: 600, color: '#1F3A52', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontFamily: 'Manrope, sans-serif' }}>
                              Из чего складывается {showBreakdown ? '▲' : '▼'}
                            </button>
                          )}
                        </div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, auto)', gap: '6px 20px', marginBottom: 12 }}>
                        {[
                          { l: 'Г/П', v: `${r.capacity} т` },
                          { l: 'Вылет', v: `${r.radius} м` },
                          { l: 'Высота', v: `${r.height} м` },
                        ].map(s => (
                          <div key={s.l} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <span style={{ fontSize: 11, color: '#8A949B', fontWeight: 600 }}>{s.l}</span>
                            <span style={{ fontSize: 14, fontWeight: 800, color: '#14181B', fontVariantNumeric: 'tabular-nums' }}>{s.v}</span>
                          </div>
                        ))}
                      </div>
                      <div style={{ fontSize: 13, color: '#5A646B', lineHeight: 1.5, background: '#F5F6F7', padding: '8px 12px', borderRadius: 6 }}>
                        <strong style={{ color: '#14181B' }}>Почему эта машина: </strong>{r.reason}
                      </div>
                    </div>
                  </div>
                  {/* Price breakdown */}
                  {r.breakdown && showBreakdown && chosenResult === i && (
                    <div style={{ borderTop: '1px solid #DDE1E4', padding: '16px 24px', background: '#F5F6F7' }}>
                      {[
                        { item: 'Аренда LTM 1070 (4 ч × 1 200 lei)', value: '4 800 lei' },
                        { item: 'Подача (12 км)', value: '480 lei' },
                        { item: 'НДС 20%', value: '– включён' },
                        { item: 'Страховка ГО', value: '– включена' },
                        { item: 'Оператор', value: '– включён' },
                      ].map((row, ri) => (
                        <div key={ri} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: ri < 4 ? '1px solid #EDEFF1' : 'none', fontSize: 13 }}>
                          <span style={{ color: '#5A646B' }}>{row.item}</span>
                          <span style={{ fontWeight: 700, color: '#14181B', fontVariantNumeric: 'tabular-nums' }}>{row.value}</span>
                        </div>
                      ))}
                      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0', borderTop: '2px solid #DDE1E4', marginTop: 8 }}>
                        <span style={{ fontSize: 15, fontWeight: 700, color: '#14181B' }}>Итого</span>
                        <span style={{ fontSize: 20, fontWeight: 800, color: '#1F3A52', fontVariantNumeric: 'tabular-nums' }}>5 200 lei</span>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {chosenResult !== null && (
              <div style={{ marginTop: 24, padding: '20px 24px', background: '#1F3A52', borderRadius: 12, display: 'flex', gap: 20, alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: 14, color: '#A3ADB4', marginBottom: 4 }}>Выбрано: <strong style={{ color: '#F2F4F5' }}>{RESULTS[chosenResult].name}</strong></div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#F5A623', fontVariantNumeric: 'tabular-nums' }}>{RESULTS[chosenResult].price} lei</div>
                </div>
                <button style={{ padding: '12px 32px', background: '#F5A623', border: 'none', borderRadius: 6, color: '#14181B', fontSize: 15, fontWeight: 800, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', whiteSpace: 'nowrap' }}>
                  Оставить заявку →
                </button>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32, paddingTop: 24, borderTop: '1px solid #DDE1E4' }}>
          <button
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            style={{ padding: '10px 24px', border: '1px solid #DDE1E4', borderRadius: 6, background: '#fff', color: step === 0 ? '#C2C8CD' : '#14181B', fontSize: 14, fontWeight: 600, cursor: step === 0 ? 'default' : 'pointer', fontFamily: 'Manrope, sans-serif' }}
          >
            ← Назад
          </button>
          {step < STEPS.length - 1 && (
            <button
              onClick={() => setStep(Math.min(STEPS.length - 1, step + 1))}
              style={{ padding: '10px 32px', background: '#F5A623', border: 'none', borderRadius: 6, color: '#14181B', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}
            >
              Далее →
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
