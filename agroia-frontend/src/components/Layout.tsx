import { NavLink, Outlet, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

const navItems = [
  { to: '/', icon: '💬', label: 'Assistente' },
  { to: '/dashboard', icon: '📊', label: 'Dashboard' },
  { to: '/consultas', icon: '🔍', label: 'Consultas' },
]

export default function Layout({ children }: { children?: ReactNode }) {
  const location = useLocation()

  const titles: Record<string, string> = {
    '/': 'Assistente Agrícola',
    '/dashboard': 'Painel de Dados',
    '/consultas': 'Consultas de Licitações',
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>
            <div className="logo-icon">🌾</div>
            AgroIA-RMC
          </h1>
          <p>Agricultura Familiar</p>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Menu</div>
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <span className="icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-card">
            <div className="user-avatar">AG</div>
            <div className="user-info">
              <p>Gestor SMSAN</p>
              <span>Curitiba – PR</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <h2>{titles[location.pathname] ?? 'AgroIA-RMC'}</h2>
          <span className="topbar-badge">🌱 Sistema Ativo</span>
        </header>

        {children ?? <Outlet />}
      </div>
    </div>
  )
}
