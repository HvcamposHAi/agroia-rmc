import { ArrowDown, ArrowUp, Minus, CircleHelp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import StatusBadge from './StatusBadge'
import type { Tom } from '../lib/tons'

export type SemaforoCor = 'verde' | 'amarelo' | 'vermelho' | 'cinza'

interface Props {
  semaforo: SemaforoCor
  texto: string
}

// Estado de preço: cor + ícone + texto (WCAG 1.4.1 — nunca só a cor).
// verde = abaixo da média (seta p/ baixo), amarelo = dentro (traço),
// vermelho = acima (seta p/ cima), cinza = sem histórico (interrogação).
const ESTADOS: Record<SemaforoCor, { tom: Tom; Icone: LucideIcon }> = {
  verde:    { tom: 'ok',     Icone: ArrowDown },
  amarelo:  { tom: 'aviso',  Icone: Minus },
  vermelho: { tom: 'erro',   Icone: ArrowUp },
  cinza:    { tom: 'neutro', Icone: CircleHelp },
}

export function SemaforoPreco({ semaforo, texto }: Props) {
  const { tom, Icone } = ESTADOS[semaforo]
  return <StatusBadge tom={tom} icon={Icone} tamanho="lg">{texto}</StatusBadge>
}
