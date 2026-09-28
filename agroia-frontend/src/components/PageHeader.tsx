import type { ReactNode } from 'react'
import { Database } from 'lucide-react'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  /** Rótulo curto acima do título (seção do portal). */
  eyebrow?: ReactNode
  /** Linha "Fonte: …" — procedência dos dados exibidos (transparência). */
  source?: ReactNode
  /** Botões/ações alinhados à direita. */
  actions?: ReactNode
}

// Cabeçalho padrão das páginas: título + descrição + procedência dos dados.
export default function PageHeader({ title, subtitle, eyebrow, source, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
        {source && (
          <div className="page-source">
            <Database size={13} aria-hidden /> {source}
          </div>
        )}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}
