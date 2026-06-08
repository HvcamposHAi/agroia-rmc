// Formatadores de data/hora compartilhados (pt-BR). Centralizados aqui para evitar duplicação
// entre páginas (ex.: Coleta e Mercado usam o mesmo "Última atualização").

/** Timestamp ISO (com hora) → "8 de jun. de 2026 06:30". Vazio/ inválido → "—". */
export function formatarDataHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(d)
}

/** Data ISO "yyyy-mm-dd" (sem hora) → "06/06/2026", sem deslocamento de fuso. Vazio → "—". */
export function formatarDataCurta(iso: string | null | undefined): string {
  if (!iso) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (m) return `${m[3]}/${m[2]}/${m[1]}`
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(d)
}
