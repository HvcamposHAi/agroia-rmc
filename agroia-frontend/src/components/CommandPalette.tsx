import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import { getCache, setCache } from '../lib/sessionCache'
import { useT } from '../i18n'
import { NAV_MSG } from '../i18n/nav'

interface Entry {
  icon: string
  label: string
  to: string
  group: string
}

type NavKey = keyof typeof NAV_MSG.pt

// label = chave de NAV_MSG (traduzida na renderização).
const STATIC_ACTIONS: { icon: string; label: NavKey; to: string }[] = [
  { icon: '🏠', label: 'inicio', to: '/inicio' },
  { icon: '📊', label: 'demandaResumo', to: '/demanda?view=resumo' },
  { icon: '🔍', label: 'demandaLista', to: '/demanda?view=lista' },
  { icon: '💰', label: 'mercadoPrecos', to: '/mercado' },
  { icon: '🧺', label: 'ofertasProdutores', to: '/ofertas' },
  { icon: '🧑‍🌾', label: 'produtorCadastrar', to: '/produtor' },
  { icon: '💬', label: 'assistente', to: '/assistente' },
  { icon: '📄', label: 'documentos', to: '/documentos' },
  { icon: '🚨', label: 'alertas', to: '/alertas' },
  { icon: '🔎', label: 'auditoria', to: '/auditoria' },
  { icon: '⚡', label: 'benchmarkComparacao', to: '/benchmark' },
  { icon: '🔄', label: 'coletaDados', to: '/coleta' },
]

const norm = (s: string) =>
  (s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

const CK_CULTURAS = 'cmdk_culturas_v1'
const CK_PRODUTOS = 'cmdk_produtos_v1'

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const t = useT(NAV_MSG)
  const [query, setQuery] = useState('')
  const [dados, setDados] = useState<{ culturas: string[]; produtos: string[] }>({ culturas: [], produtos: [] })
  const [sel, setSel] = useState(0)
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
        if (ativo) setDados({ culturas: cachedC, produtos: cachedP })
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
      if (ativo) setDados({ culturas, produtos })
    }
    load()
    return () => { ativo = false }
  }, [open])

  const estaticas = useMemo<Entry[]>(
    () => STATIC_ACTIONS.map(a => ({ ...a, label: t(a.label), group: t('grupoNavegar') })),
    [t],
  )
  const all = useMemo<Entry[]>(() => [
    ...estaticas,
    ...dados.culturas.map(c => ({
      icon: '🌱', label: t('demandaDe', { nome: c }), group: t('grupoCulturas'),
      to: `/demanda?view=lista&cultura=${encodeURIComponent(c)}`,
    })),
    ...dados.produtos.map(p => ({
      icon: '🏷️', label: t('precoDe', { nome: p }), group: t('grupoProdutos'),
      to: `/mercado?produto=${encodeURIComponent(p)}`,
    })),
  ], [estaticas, dados, t])
  const results = useMemo(() => {
    const q = norm(query)
    if (!q) return estaticas
    return all.filter(e => norm(e.label).includes(q)).slice(0, 30)
  }, [query, all, estaticas])

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
            placeholder={t('placeholder')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKey}
          />
          <kbd className="cmdk-kbd">Esc</kbd>
        </div>
        <div className="cmdk-list">
          {results.length === 0 && (
            <div className="cmdk-empty">{t('nada', { q: query })}</div>
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
