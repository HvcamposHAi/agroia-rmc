import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import type { Tom } from '../lib/tons'

interface StatusBadgeProps {
  tom: Tom
  icon?: LucideIcon
  children: ReactNode
  /** 'sm' (padrão) para listas e tabelas; 'lg' para destaque (ex.: semáforo de preço). */
  tamanho?: 'sm' | 'lg'
  title?: string
}

// Selo de estado: ícone + texto na cor do tom (WCAG 1.4.1 — nunca só a cor).
export default function StatusBadge({ tom, icon: Icon, children, tamanho = 'sm', title }: StatusBadgeProps) {
  return (
    <span className={`badge ${tom}${tamanho === 'lg' ? ' badge-lg' : ''}`} title={title}>
      {Icon && <Icon size={tamanho === 'lg' ? 16 : 13} strokeWidth={2.4} aria-hidden />}
      {children}
    </span>
  )
}
