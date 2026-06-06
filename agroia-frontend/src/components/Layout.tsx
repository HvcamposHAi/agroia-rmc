import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import CommandPalette from './CommandPalette'

const primaryNav = [
  { to: '/', icon: '🏠', label: 'Início' },
  { to: '/demanda', icon: '📊', label: 'Demanda' },
  { to: '/mercado', icon: '💰', label: 'Mercado' },
  { to: '/ofertas', icon: '🧺', label: 'Ofertas' },
  { to: '/assistente', icon: '💬', label: 'Assistente' },
]

const moreNav = [
  { to: '/produtor', icon: '🧑‍🌾', label: 'Sou Produtor' },
  { to: '/documentos', icon: '📄', label: 'Documentos' },
  { to: '/alertas', icon: '🚨', label: 'Alertas IA' },
  { to: '/auditoria', icon: '🔎', label: 'Auditoria' },
  { to: '/coleta', icon: '🔄', label: 'Atualização' },
]

export default function Layout({ children }: { children?: ReactNode }) {
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
              <span className="label">{item.label}</span>
            </NavLink>
          ))}

          {/* "Mais" — agrupa os serviços secundários (desktop: dropdown; mobile: inline) */}
          <div className="topnav-more">
            <button ref={maisBtnRef} className="topnav-item" onClick={toggleMais} aria-haspopup="true" aria-expanded={maisAberto}>
              <span className="label">Mais</span> <span style={{ fontSize: 10 }}>▾</span>
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
                    <span className="icon">{item.icon}</span> {item.label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="appbar-actions">
          <button className="cmdk-trigger" onClick={() => setCmdkAberto(true)} title="Buscar / comandos (Ctrl+K)">
            <span>🔎 Buscar</span>
            <kbd>⌘K</kbd>
          </button>
          <div className="user-avatar" title="Gestor SMSAN — Curitiba/PR">AG</div>
          <button
            className="hamburger"
            onClick={() => setMenuAberto(v => !v)}
            aria-label="Abrir menu"
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
