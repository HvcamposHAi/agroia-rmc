import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import CommandPalette from './CommandPalette'
import SeletorIdioma from './SeletorIdioma'
import { useT } from '../i18n'
import { NAV_MSG } from '../i18n/nav'

type NavKey = keyof typeof NAV_MSG.pt

const primaryNav: { to: string; icon: string; label: NavKey }[] = [
  { to: '/inicio', icon: '🏠', label: 'inicio' },
  { to: '/demanda', icon: '📊', label: 'demanda' },
  { to: '/mercado', icon: '💰', label: 'mercado' },
  { to: '/ofertas', icon: '🧺', label: 'ofertas' },
  { to: '/assistente', icon: '💬', label: 'assistente' },
]

const moreNav: { to: string; icon: string; label: NavKey }[] = [
  { to: '/produtor', icon: '🧑‍🌾', label: 'produtor' },
  { to: '/documentos', icon: '📄', label: 'documentos' },
  { to: '/alertas', icon: '🚨', label: 'alertas' },
  { to: '/auditoria', icon: '🔎', label: 'auditoria' },
  { to: '/benchmark', icon: '⚡', label: 'benchmark' },
  { to: '/coleta', icon: '🔄', label: 'coleta' },
]

export default function Layout({ children }: { children?: ReactNode }) {
  const t = useT(NAV_MSG)
  const [menuAberto, setMenuAberto] = useState(false)
  const [maisAberto, setMaisAberto] = useState(false)
  const [cmdkAberto, setCmdkAberto] = useState(false)
  const maisBtnRef = useRef<HTMLButtonElement>(null)
  // Posição (viewport) do dropdown "Mais" — usado no desktop, onde ele é position: fixed.
  const [maisPos, setMaisPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 })

  // Atalho global ⌘K / Ctrl+K abre a paleta de comandos.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCmdkAberto(v => !v)
      }
      if (e.key === 'Escape') {
        setMaisAberto(false)
        setMenuAberto(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Fecha o dropdown ao redimensionar (a posição fixa ficaria desalinhada).
  useEffect(() => {
    if (!maisAberto) return
    const onResize = () => setMaisAberto(false)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [maisAberto])

  const toggleMais = () => {
    setMaisAberto(v => {
      const proximo = !v
      if (proximo && maisBtnRef.current) {
        const r = maisBtnRef.current.getBoundingClientRect()
        setMaisPos({ top: r.bottom + 6, left: r.left })
      }
      return proximo
    })
  }

  const fecharTudo = () => { setMenuAberto(false); setMaisAberto(false) }

  return (
    <div className="layout">
      <header className="appbar">
        <NavLink to="/" className="appbar-brand" onClick={fecharTudo}>
          <span className="logo-icon">🌾</span>
          <span className="brand-text">AgroIA-RMC</span>
        </NavLink>

        <nav className={`appbar-nav${menuAberto ? ' open' : ''}`}>
          {primaryNav.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `topnav-item${isActive ? ' active' : ''}`}
              onClick={fecharTudo}
            >
              <span className="icon">{item.icon}</span>
              <span className="label">{t(item.label)}</span>
            </NavLink>
          ))}

          {/* "Mais" — agrupa os serviços secundários (desktop: dropdown; mobile: inline) */}
          <div className="topnav-more">
            <button ref={maisBtnRef} className="topnav-item" onClick={toggleMais} aria-haspopup="true" aria-expanded={maisAberto}>
              <span className="label">{t('mais')}</span> <span style={{ fontSize: 10 }}>▾</span>
            </button>
            {maisAberto && (
              <div className="topnav-dropdown" style={{ top: maisPos.top, left: maisPos.left }}>
                {moreNav.map(item => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) => `topnav-drop-item${isActive ? ' active' : ''}`}
                    onClick={fecharTudo}
                  >
                    <span className="icon">{item.icon}</span> {t(item.label)}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="appbar-actions">
          <SeletorIdioma />
          <button className="cmdk-trigger" onClick={() => setCmdkAberto(true)} title={t('buscarTitulo')}>
            <span>{t('buscar')}</span>
            <kbd>⌘K</kbd>
          </button>
          <div className="user-avatar" title={t('usuario')}>AG</div>
          <button
            className="hamburger"
            onClick={() => setMenuAberto(v => !v)}
            aria-label={t('abrirMenu')}
            aria-expanded={menuAberto}
          >
            ☰
          </button>
        </div>
      </header>

      {(menuAberto || maisAberto) && <div className="nav-backdrop" onClick={fecharTudo} />}

      <div className="main">
        {children ?? <Outlet />}
      </div>

      <CommandPalette open={cmdkAberto} onClose={() => setCmdkAberto(false)} />
    </div>
  )
}
