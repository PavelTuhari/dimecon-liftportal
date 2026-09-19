import { useState } from 'react'
import { useLang } from '../../context/LangContext'
import { t, tr } from '../../i18n'

export default function ContactsPage() {
  const { lang } = useLang()
  const [form, setForm] = useState({ name: '', phone: '', message: '' })
  const [sent, setSent] = useState(false)

  const ct = t.pages.contactsPage

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setSent(true)
  }

  return (
    <div style={{ background: '#F5F6F7', minHeight: '100vh', padding: '40px 0 80px' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 80px' }}>
        <div style={{ marginBottom: 48 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F5A623', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10 }}>
            {tr(t.nav.contacts, lang).toUpperCase()}
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, color: '#14181B', margin: '0 0 10px', letterSpacing: '-0.02em' }}>
            {tr(ct.title, lang)}
          </h1>
          <p style={{ fontSize: 16, color: '#5A646B', margin: 0 }}>{tr(ct.subtitle, lang)}</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 40 }}>
          {/* Left: info */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Address */}
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 10, padding: '24px 28px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8A949B', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>{tr(ct.address, lang)}</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#14181B', marginBottom: 4 }}>SA «Dimecon 11»</div>
              <div style={{ fontSize: 14, color: '#5A646B', lineHeight: 1.65 }}>
                {lang === 'RO' ? 'IDNO 1003600123456\nMD-2001, Chișinău\nstr. Industrială, 14' : lang === 'EN' ? 'IDNO 1003600123456\nMD-2001, Chisinau\n14 Industriala str.' : 'IDNO 1003600123456\nMD-2001, Кишинёв\nул. Индустриалэ, 14'}
              </div>
            </div>

            {/* Phones */}
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 10, padding: '24px 28px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8A949B', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>
                {lang === 'RO' ? 'Telefoane' : lang === 'EN' ? 'Phones' : 'Телефоны'}
              </div>
              {[
                { label: lang === 'RO' ? 'Dispecerat' : lang === 'EN' ? 'Dispatch' : 'Диспетчерская', number: '+373 22 123-456', main: true },
                { label: lang === 'RO' ? 'Comercial' : lang === 'EN' ? 'Sales' : 'Коммерческий', number: '+373 22 123-789', main: false },
                { label: 'WhatsApp', number: '+373 69 123-456', main: false },
              ].map((p, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: i > 0 ? '10px 0 0' : '0 0 10px', borderBottom: i < 2 ? '1px solid #EDEFF1' : 'none' }}>
                  <span style={{ fontSize: 13, color: '#8A949B', fontWeight: 500 }}>{p.label}</span>
                  <a href={`tel:${p.number.replace(/\s/g, '')}`} style={{ fontSize: p.main ? 18 : 14, fontWeight: p.main ? 800 : 600, color: '#1F3A52', textDecoration: 'none', fontVariantNumeric: 'tabular-nums' }}>
                    {p.number}
                  </a>
                </div>
              ))}
            </div>

            {/* Hours */}
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 10, padding: '24px 28px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8A949B', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 16 }}>{tr(ct.hours, lang)}</div>
              {[
                { day: tr(ct.weekdays, lang), time: '07:00 – 20:00' },
                { day: tr(ct.saturday, lang), time: '08:00 – 16:00' },
                { day: tr(ct.sunday, lang), time: lang === 'RO' ? 'Închis' : lang === 'EN' ? 'Closed' : 'Закрыто' },
                { day: tr(ct.emergency, lang), time: '24/7' },
              ].map((row, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: i < 3 ? '1px solid #EDEFF1' : 'none' }}>
                  <span style={{ fontSize: 13, color: '#5A646B' }}>{row.day}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: i === 3 ? '#F5A623' : i === 2 ? '#C0392B' : '#14181B', fontVariantNumeric: 'tabular-nums' }}>{row.time}</span>
                </div>
              ))}
            </div>

            {/* Map placeholder */}
            <div style={{ background: '#EDEFF1', border: '1px solid #DDE1E4', borderRadius: 10, height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 32 }}>🗺️</span>
              <span style={{ fontSize: 13, color: '#8A949B', fontWeight: 500 }}>
                {lang === 'RO' ? 'Hartă interactivă' : lang === 'EN' ? 'Interactive map' : 'Интерактивная карта'}
              </span>
              <span style={{ fontSize: 11, color: '#C2C8CD' }}>str. Industrială, 14, Chișinău</span>
            </div>
          </div>

          {/* Right: form */}
          <div>
            <div style={{ background: '#fff', border: '1px solid #DDE1E4', borderRadius: 10, padding: '32px 36px' }}>
              <h2 style={{ fontSize: 22, fontWeight: 800, color: '#14181B', margin: '0 0 24px', letterSpacing: '-0.01em' }}>
                {tr(ct.form, lang)}
              </h2>

              {sent ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#2E7D4F', marginBottom: 8 }}>
                    {lang === 'RO' ? 'Mesaj trimis!' : lang === 'EN' ? 'Message sent!' : 'Сообщение отправлено!'}
                  </div>
                  <div style={{ fontSize: 14, color: '#5A646B' }}>
                    {lang === 'RO' ? 'Vă sunăm în 15 minute în orele de lucru' : lang === 'EN' ? 'We will call you within 15 minutes during working hours' : 'Перезвоним в течение 15 минут в рабочее время'}
                  </div>
                  <button onClick={() => { setSent(false); setForm({ name: '', phone: '', message: '' }) }} style={{ marginTop: 20, padding: '8px 20px', background: 'transparent', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 13, fontWeight: 600, cursor: 'pointer', fontFamily: 'Manrope, sans-serif', color: '#5A646B' }}>
                    {lang === 'RO' ? 'Trimite alt mesaj' : lang === 'EN' ? 'Send another message' : 'Отправить ещё'}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  {[
                    { key: 'name', label: tr(ct.name, lang), type: 'text', placeholder: lang === 'RO' ? 'Ion Popescu' : lang === 'EN' ? 'John Smith' : 'Иван Иванов' },
                    { key: 'phone', label: tr(ct.phone, lang), type: 'tel', placeholder: '+373 6X XXX-XXX' },
                  ].map(field => (
                    <div key={field.key}>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#5A646B', marginBottom: 6, letterSpacing: '0.04em' }}>{field.label}</label>
                      <input
                        type={field.type}
                        placeholder={field.placeholder}
                        required
                        value={form[field.key as 'name' | 'phone']}
                        onChange={e => setForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                        style={{ width: '100%', padding: '10px 12px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 14, fontFamily: 'Manrope, sans-serif', color: '#14181B', boxSizing: 'border-box' }}
                      />
                    </div>
                  ))}
                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#5A646B', marginBottom: 6, letterSpacing: '0.04em' }}>{tr(ct.message, lang)}</label>
                    <textarea
                      rows={5}
                      placeholder={lang === 'RO' ? 'Descrieți lucrarea…' : lang === 'EN' ? 'Describe your task…' : 'Опишите задачу…'}
                      value={form.message}
                      onChange={e => setForm(prev => ({ ...prev, message: e.target.value }))}
                      style={{ width: '100%', padding: '10px 12px', border: '1px solid #DDE1E4', borderRadius: 4, fontSize: 14, fontFamily: 'Manrope, sans-serif', color: '#14181B', resize: 'vertical', boxSizing: 'border-box' }}
                    />
                  </div>
                  <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}>
                    <input type="checkbox" required style={{ marginTop: 2, accentColor: '#1F3A52' }} />
                    <span style={{ fontSize: 12, color: '#8A949B', lineHeight: 1.5 }}>
                      {lang === 'RO' ? 'Sunt de acord cu prelucrarea datelor personale conform politicii de confidențialitate' : lang === 'EN' ? 'I agree to the processing of personal data in accordance with the privacy policy' : 'Даю согласие на обработку персональных данных в соответствии с политикой конфиденциальности'}
                    </span>
                  </label>
                  <button type="submit" style={{ padding: '12px 0', background: '#F5A623', border: 'none', borderRadius: 6, color: '#14181B', fontSize: 15, fontWeight: 800, cursor: 'pointer', fontFamily: 'Manrope, sans-serif' }}>
                    {tr(ct.send, lang)} →
                  </button>
                </form>
              )}
            </div>

            {/* Requisites */}
            <div style={{ marginTop: 20, background: '#fff', border: '1px solid #DDE1E4', borderRadius: 10, padding: '20px 28px' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#8A949B', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 12 }}>
                {lang === 'RO' ? 'Rechizite bancare' : lang === 'EN' ? 'Bank details' : 'Банковские реквизиты'}
              </div>
              {[
                { l: lang === 'RO' ? 'Denumire' : lang === 'EN' ? 'Company' : 'Наименование', v: 'SA «Dimecon 11»' },
                { l: 'IDNO', v: '1003600123456' },
                { l: lang === 'RO' ? 'Cont bancar' : lang === 'EN' ? 'Bank account' : 'Расчётный счёт', v: 'MD24 AGRNMD 0000 0000 0012 3456' },
                { l: 'Banca / Bank', v: 'BC Moldova-Agroindbank SA' },
                { l: 'SWIFT', v: 'AGRNMD22' },
                { l: lang === 'RO' ? 'Cod TVA' : lang === 'EN' ? 'VAT code' : 'Код НДС', v: '1003600123456' },
              ].map((r, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < 5 ? '1px solid #EDEFF1' : 'none' }}>
                  <span style={{ fontSize: 12, color: '#8A949B' }}>{r.l}</span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: '#14181B', fontVariantNumeric: 'tabular-nums' }}>{r.v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
