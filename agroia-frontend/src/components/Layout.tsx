import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  House, MessageSquare, ChartColumn, TrendingUp, Tractor, FileText,
  BellRing, ShieldCheck, RefreshCw, FlaskConical, Sprout, Search, Menu, ChevronDown,
} from 'lucide-react'
import CommandPalette from './CommandPalette'
import SeletorIdioma from './SeletorIdioma'
import { useT } from '../i18n'
import { NAV_MSG } from '../i18n/nav'

type NavKey = keyof typeof NAV_MSG.pt
interface NavItem { to: string; icon: LucideIcon; label: NavKey }

// Navegação principal: o que prefeitura e cooperativas usam no dia a dia.
const primaryNav: NavItem[] = [
  { to: '/inicio', icon: House, label: 'inicio' },
  { to: '/assistente', icon: MessageSquare, label: 'assistente' },
  { to: '/demanda', icon: ChartColumn, label: 'demanda' },
  { to: '/mercado', icon: TrendingUp, label: 'mercado' },
  { to: '/produtor', icon: Tractor, label: 'produtor' },
  { to: '/documentos', icon: FileText, label: 'documentos' },
]

// "Gestão": ferramentas da equipe técnica (monitoramento, qualidade, operação).
const moreNav: NavItem[] = [
  { to: '/alertas', icon: BellRing, label: 'alertas' },
  { to: '/auditoria', icon: ShieldCheck, label: 'auditoria' },
  { to: '/coleta', icon: RefreshCw, label: 'coleta' },
  { to: '/benchmark', icon: FlaskConical, label: 'benchmark' },
]

export default function Layout({ children }: { children?: ReactNode }) {
  const t = useT(NAV_MSG)
  const [menuAberto, setMenuAberto] = useState(false)
  const [maisAberto, setMaisAberto] = useState(false)
  const [cmdkAberto, setCmdkAberto] = useState(false)
  const maisBtnRef = useRef<HTMLButtonElement>(null)
  // Posição (viewport) do dropdown "Gestão" — usado no desktop, onde ele é position: fixed.
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
        <NavLink to="/inicio" className="appbar-brand" onClick={fecharTudo}>
          <span className="logo-icon" aria-hidden><Sprout size={20} strokeWidth={2.2} /></span>
          <span className="brand-stack">
            <span className="brand-text">AgroIA-RMC</span>
            <span className="brand-sub">{t('marcaSub')}</span>
          </span>
        </NavLink>

        <nav className={`appbar-nav${menuAberto ? ' open' : ''}`} aria-label="Principal">
          {primaryNav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `topnav-item${isActive ? ' active' : ''}`}
              onClick={fecharTudo}
            >
              <span className="icon"><Icon size={17} aria-hidden /></span>
              <span className="label">{t(label)}</span>
            </NavLink>
          ))}

          {/* "Gestão" — agrupa as ferramentas internas (desktop: dropdown; mobile: inline) */}
          <div className="topnav-more">
            <button ref={maisBtnRef} className="topnav-item" onClick={toggleMais} aria-haspopup="true" aria-expanded={maisAberto}>
              <span className="label">{t('mais')}</span> <ChevronDown size={15} aria-hidden />
            </button>
            {maisAberto && (
              <div className="topnav-dropdown" style={{ top: maisPos.top, left: maisPos.left }}>
                {moreNav.map(({ to, icon: Icon, label }) => (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) => `topnav-drop-item${isActive ? ' active' : ''}`}
                    onClick={fecharTudo}
                  >
                    <Icon size={16} aria-hidden /> {t(label)}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        </nav>

        <div className="appbar-actions">
          <button className="cmdk-trigger" onClick={() => setCmdkAberto(true)} title={t('buscarTitulo')} aria-label={t('buscarTitulo')}>
            <Search size={15} aria-hidden />
            <span>{t('buscar')}</span>
            <kbd>Ctrl K</kbd>
          </button>
          <SeletorIdioma />
          <button
            className="hamburger"
            onClick={() => setMenuAberto(v => !v)}
            aria-label={t('abrirMenu')}
            aria-expanded={menuAberto}
          >
            <Menu size={20} aria-hidden />
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
