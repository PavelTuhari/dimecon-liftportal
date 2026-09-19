import { useState } from 'react'
import { LangProvider } from './context/LangContext'
import PublicSite from './pages/PublicSite'
import B2CWizard from './pages/B2CWizard'
import B2BPortal from './pages/B2BPortal'

type View = 'public' | 'b2c' | 'b2b'

export default function App() {
  const [view, setView] = useState<View>('public')

  return (
    <LangProvider>
      <div className="min-h-screen">
        {/* Preview Switcher */}
        <div style={{ background: '#0A0C0E', borderBottom: '1px solid #2C3338', position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 16px' }}>
          <span style={{ color: '#6F7A81', fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginRight: 8 }}>dimecon.md — МАКЕТ</span>
          {([
            { id: 'public', label: '① Публичный сайт' },
            { id: 'b2c', label: '② B2C Визард' },
            { id: 'b2b', label: '③ B2B Портал' },
          ] as { id: View; label: string }[]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              style={{
                padding: '4px 12px', borderRadius: 4, border: 'none', cursor: 'pointer',
                fontSize: 11, fontWeight: 700, fontFamily: 'Manrope, sans-serif',
                background: view === tab.id ? '#F5A623' : '#1E2327',
                color: view === tab.id ? '#14181B' : '#A3ADB4',
                transition: 'all 150ms ease',
              }}
            >
              {tab.label}
            </button>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4CAF7D' }} className="pulse-dot" />
            <span style={{ fontSize: 10, color: '#6F7A81', fontWeight: 500 }}>Live preview</span>
          </div>
        </div>

        <div style={{ paddingTop: 38 }}>
          {view === 'public' && <PublicSite />}
          {view === 'b2c' && <B2CWizard />}
          {view === 'b2b' && <B2BPortal />}
        </div>
      </div>
    </LangProvider>
  )
}
