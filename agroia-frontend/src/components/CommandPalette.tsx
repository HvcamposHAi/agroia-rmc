import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import { getCache, setCache } from '../lib/sessionCache'

interface Entry {
  icon: string
  label: string
  to: string
  group: string
}

const STATIC_ACTIONS: Entry[] = [
  { icon: '🏠', label: 'Início', to: '/inicio', group: 'Navegar' },
  { icon: '📊', label: 'Demanda — Resumo', to: '/demanda?view=resumo', group: 'Navegar' },
  { icon: '🔍', label: 'Demanda — Lista', to: '/demanda?view=lista', group: 'Navegar' },
  { icon: '💰', label: 'Mercado (preços)', to: '/mercado', group: 'Navegar' },
  { icon: '🧺', label: 'Ofertas de produtores', to: '/ofertas', group: 'Navegar' },
  { icon: '🧑‍🌾', label: 'Sou Produtor — cadastrar oferta', to: '/produtor', group: 'Navegar' },
  { icon: '💬', label: 'Assistente', to: '/assistente', group: 'Navegar' },
  { icon: '📄', label: 'Documentos', to: '/documentos', group: 'Navegar' },
  { icon: '🚨', label: 'Alertas IA', to: '/alertas', group: 'Navegar' },
  { icon: '🔎', label: 'Auditoria', to: '/auditoria', group: 'Navegar' },
  { icon: '🔄', label: 'Atualização de dados', to: '/coleta', group: 'Navegar' },
]

const norm = (s: string) =>
  (s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

const CK_CULTURAS = 'cmdk_culturas_v1'
const CK_PRODUTOS = 'cmdk_produtos_v1'

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0)
  const [dynamic, setDynamic] = useState<Entry[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  // Carrega culturas (Demanda) e produtos (Mercado) uma vez, cacheado na sessão.
  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    let ativo = true
    async function load() {
      const cachedC = getCache<string[]>(CK_CULTURAS)
      const cachedP = getCache<string[]>(CK_PRODUTOS)
      if (cachedC && cachedP) {
        if (ativo) setDynamic(montar(cachedC, cachedP))
        return
      }
      const [c, p] = await Promise.all([
        supabase.from('vw_itens_agro').select('cultura').limit(2000),
        supabase.from('v_prohort_analise').select('produto_norm').eq('ceasa', 'CURITIBA').limit(2000),
      ])
      const culturas = [...new Set((c.data ?? []).map((r: any) => r.cultura).filter(Boolean))].sort() as string[]
      const produtos = [...new Set((p.data ?? []).map((r: any) => r.produto_norm).filter(Boolean))].sort() as string[]
      setCache(CK_CULTURAS, culturas)
      setCache(CK_PRODUTOS, produtos)
      if (ativo) setDynamic(montar(culturas, produtos))
    }
    load()
    return () => { ativo = false }
  }, [open])

  function montar(culturas: string[], produtos: string[]): Entry[] {
    const ec: Entry[] = culturas.map(c => ({
      icon: '🌱', label: `Demanda: ${c}`, group: 'Culturas',
      to: `/demanda?view=lista&cultura=${encodeURIComponent(c)}`,
    }))
    const ep: Entry[] = produtos.map(p => ({
      icon: '🏷️', label: `Preço: ${p}`, group: 'Produtos (CEASA)',
      to: `/mercado?produto=${encodeURIComponent(p)}`,
    }))
    return [...ec, ...ep]
  }

  const all = useMemo(() => [...STATIC_ACTIONS, ...dynamic], [dynamic])
  const results = useMemo(() => {
    const q = norm(query)
    if (!q) return STATIC_ACTIONS
    return all.filter(e => norm(e.label).includes(q)).slice(0, 30)
  }, [query, all])

  useEffect(() => { setSel(0) }, [query, open])

  if (!open) return null

  const go = (e?: Entry) => {
    const target = e ?? results[sel]
    if (!target) return
    onClose()
    navigate(target.to)
  }

  const onKey = (ev: React.KeyboardEvent) => {
    if (ev.key === 'ArrowDown') { ev.preventDefault(); setSel(s => Math.min(results.length - 1, s + 1)) }
    else if (ev.key === 'ArrowUp') { ev.preventDefault(); setSel(s => Math.max(0, s - 1)) }
    else if (ev.key === 'Enter') { ev.preventDefault(); go() }
    else if (ev.key === 'Escape') { ev.preventDefault(); onClose() }
  }

  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk-panel" onClick={e => e.stopPropagation()}>
        <div className="cmdk-input-row">
          <span style={{ fontSize: 16 }}>🔎</span>
          <input
            ref={inputRef}
            className="cmdk-input"
            placeholder="Buscar páginas, culturas, produtos…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKey}
          />
          <kbd className="cmdk-kbd">Esc</kbd>
        </div>
        <div className="cmdk-list">
          {results.length === 0 && (
            <div className="cmdk-empty">Nada encontrado para “{query}”.</div>
          )}
          {results.map((e, i) => (
            <button
              key={`${e.to}-${i}`}
              className={`cmdk-item${i === sel ? ' active' : ''}`}
              onMouseEnter={() => setSel(i)}
              onClick={() => go(e)}
            >
              <span className="cmdk-item-icon">{e.icon}</span>
              <span className="cmdk-item-label">{e.label}</span>
              <span className="cmdk-item-group">{e.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
