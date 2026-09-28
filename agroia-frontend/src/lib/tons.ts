/**
 * Tons semânticos do sistema visual — fonte única das cores de estado.
 * Cada tom mapeia para os tokens de index.css (cor do texto/ícone, fundo, borda).
 * Estado nunca é comunicado só pela cor: use sempre com ícone + texto.
 */
export type Tom = 'ok' | 'aviso' | 'erro' | 'info' | 'neutro' | 'marca'

export const TONS: Record<Tom, { cor: string; bg: string; borda: string }> = {
  ok:     { cor: 'var(--ok)',          bg: 'var(--ok-fundo)',    borda: 'var(--ok-borda)' },
  aviso:  { cor: 'var(--aviso)',       bg: 'var(--aviso-fundo)', borda: 'var(--aviso-borda)' },
  erro:   { cor: 'var(--erro)',        bg: 'var(--erro-fundo)',  borda: 'var(--erro-borda)' },
  info:   { cor: 'var(--info)',        bg: 'var(--info-fundo)',  borda: 'var(--info-borda)' },
  neutro: { cor: 'var(--texto-suave)', bg: 'var(--cinza-claro)', borda: 'var(--borda-forte)' },
  marca:  { cor: 'var(--verde)',       bg: 'var(--verde-fundo)', borda: '#c5dccb' },
}
