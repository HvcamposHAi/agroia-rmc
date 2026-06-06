/**
 * Cache simples em sessionStorage com TTL, para evitar refetch dos datasets
 * a cada montagem de página (Consultas, Documentos, etc.). Some ao fechar a aba.
 */
const DEFAULT_TTL = 10 * 60 * 1000 // 10 min

export function getCache<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return null
    const parsed = JSON.parse(raw) as { data: T; exp: number }
    if (parsed.exp && Date.now() > parsed.exp) {
      sessionStorage.removeItem(key)
      return null
    }
    return parsed.data
  } catch {
    return null
  }
}

export function setCache<T>(key: string, data: T, ttlMs: number = DEFAULT_TTL): void {
  try {
    sessionStorage.setItem(key, JSON.stringify({ data, exp: Date.now() + ttlMs }))
  } catch {
    // sessionStorage cheio/indisponível — segue sem cache
  }
}

export function clearCache(key: string): void {
  try {
    sessionStorage.removeItem(key)
  } catch {
    /* noop */
  }
}
