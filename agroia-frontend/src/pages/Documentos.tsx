import { useEffect, useState, useMemo } from 'react'
import { supabase } from '../lib/supabaseClient'
import { useUrlState } from '../lib/useUrlState'
import { getCache, setCache } from '../lib/sessionCache'
import { defineMessages, useI18n, useT, fmtData } from '../i18n'
import {
  FileText, ClipboardList, Calendar, Tag, Download, X, Search, SlidersHorizontal, FolderOpen, Eye,
} from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import type { Tom } from '../lib/tons'
import PageHeader from '../components/PageHeader'

interface DocComLic {
  id: number
  licitacao_id: number
  nome_arquivo: string
  nome_doc: string
  url_publica: string
  tamanho_bytes: number
  coletado_em: string
  processo: string
  modalidade: string  // tipo_processo
  objeto: string
  dt_abertura: string
  situacao: string
  canal: string
}

const toEmbedUrl = (url: string): string => {
  const matchView = url.match(/drive\.google\.com\/file\/d\/([^/]+)\//)
  if (matchView) return `https://drive.google.com/file/d/${matchView[1]}/preview`
  const matchUc = url.match(/drive\.google\.com\/uc\?id=([^&]+)/)
  if (matchUc) return `https://drive.google.com/file/d/${matchUc[1]}/preview`
  return url
}

const toDownloadUrl = (url: string): string => {
  const matchView = url.match(/drive\.google\.com\/file\/d\/([^/]+)\//)
  if (matchView) return `https://drive.google.com/uc?id=${matchView[1]}&export=download`
  return url
}

const fmtBytes = (b: number) =>
  b > 1_000_000 ? `${(b / 1_000_000).toFixed(1)} MB`
  : b > 1_000 ? `${(b / 1_000).toFixed(0)} KB`
  : `${b} B`

const PAGE_SIZE = 15

const MSG = defineMessages({
  pt: {
    titulo: 'Documentos das licitações',
    subtitulo: 'Editais, termos de referência e anexos das licitações de agricultura familiar. Clique em um documento para visualizar ou baixar.',
    fonte: 'Fonte: Portal da Transparência de Curitiba — editais SMSAN/FAAC',
    carregando: 'Carregando documentos...',
    baixar: 'Baixar',
    fechar: 'Fechar',
    buscarPlaceholder: 'Buscar por nome, processo ou objeto...',
    limparBusca: 'Limpar busca',
    filtros: 'Filtros',
    limpar: 'Limpar',
    nDocumentos: '{n} documentos',
    ano: 'ANO',
    mes: 'MÊS',
    modalidade: 'MODALIDADE',
    situacao: 'SITUAÇÃO',
    canal: 'CANAL',
    todos: 'Todos',
    todas: 'Todas',
    nenhum: 'Nenhum documento encontrado',
    ajustar: 'Tente ajustar os filtros',
    visualizar: 'Visualizar',
    primeira: 'Primeira página',
    anterior: 'Página anterior',
    proxima: 'Próxima página',
    ultima: 'Última página',
  },
  en: {
    titulo: 'Tender documents',
    subtitulo: 'Calls for bids, terms of reference and attachments of family-farming tenders. Click a document to view or download it.',
    fonte: 'Source: Curitiba Transparency Portal — SMSAN/FAAC calls for bids',
    carregando: 'Loading documents...',
    baixar: 'Download',
    fechar: 'Close',
    buscarPlaceholder: 'Search by name, process or object...',
    limparBusca: 'Clear search',
    filtros: 'Filters',
    limpar: 'Clear',
    nDocumentos: '{n} documents',
    ano: 'YEAR',
    mes: 'MONTH',
    modalidade: 'MODALITY',
    situacao: 'STATUS',
    canal: 'CHANNEL',
    todos: 'All',
    todas: 'All',
    nenhum: 'No documents found',
    ajustar: 'Try adjusting the filters',
    visualizar: 'View',
    primeira: 'First page',
    anterior: 'Previous page',
    proxima: 'Next page',
    ultima: 'Last page',
  },
  es: {
    titulo: 'Documentos de las licitaciones',
    subtitulo: 'Pliegos, términos de referencia y anexos de las licitaciones de agricultura familiar. Haga clic en un documento para verlo o descargarlo.',
    fonte: 'Fuente: Portal de la Transparencia de Curitiba — pliegos SMSAN/FAAC',
    carregando: 'Cargando documentos...',
    baixar: 'Descargar',
    fechar: 'Cerrar',
    buscarPlaceholder: 'Buscar por nombre, proceso u objeto...',
    limparBusca: 'Limpiar búsqueda',
    filtros: 'Filtros',
    limpar: 'Limpiar',
    nDocumentos: '{n} documentos',
    ano: 'AÑO',
    mes: 'MES',
    modalidade: 'MODALIDAD',
    situacao: 'SITUACIÓN',
    canal: 'CANAL',
    todos: 'Todos',
    todas: 'Todas',
    nenhum: 'Ningún documento encontrado',
    ajustar: 'Intente ajustar los filtros',
    visualizar: 'Ver',
    primeira: 'Primera página',
    anterior: 'Página anterior',
    proxima: 'Página siguiente',
    ultima: 'Última página',
  },
})
const CACHE_KEY = 'documentos_agro_v1'

export default function Documentos() {
  const [docs, setDocs] = useState<DocComLic[]>([])
  const [loading, setLoading] = useState(true)
  const [pdfAberto, setPdfAberto] = useState<DocComLic | null>(null)
  const { locale } = useI18n()
  const t = useT(MSG)

  // Filtros (persistidos na URL)
  const [busca, setBusca] = useUrlState('q')
  const [filAno, setFilAno] = useUrlState('ano')
  const [filMes, setFilMes] = useUrlState('mes')
  const [filModalidade, setFilModalidade] = useUrlState('modalidade')
  const [filSituacao, setFilSituacao] = useUrlState('situacao')
  const [filCanal, setFilCanal] = useUrlState('canal')
  const [showFilters, setShowFilters] = useState(false)
  const [pageRaw, setPageRaw] = useUrlState('page', '1')
  const page = Math.max(1, parseInt(pageRaw || '1', 10) || 1)
  const setPage = (p: number) => setPageRaw(String(p))

  useEffect(() => {
    async function load() {
      try {
        const cached = getCache<DocComLic[]>(CACHE_KEY)
        if (cached) { setDocs(cached); setLoading(false); return }
        const { data } = await supabase
          .from('vw_licitacoes_agro_documentos')
          .select('*')
          .limit(500)

        if (data) {
          const flat = data.map((d: any) => ({
            id: d.id,
            licitacao_id: d.licitacao_id,
            nome_arquivo: d.nome_arquivo,
            nome_doc: d.nome_doc,
            url_publica: d.url_publica,
            tamanho_bytes: d.tamanho_bytes,
            coletado_em: d.coletado_em,
            processo: d.processo ?? '',
            modalidade: d.tipo_processo ?? '',
            objeto: d.objeto ?? '',
            dt_abertura: d.dt_abertura ?? '',
            situacao: d.situacao ?? '',
            canal: d.canal ?? '',
          }))
          setDocs(flat)
          setCache(CACHE_KEY, flat)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const anos = useMemo(() =>
    [...new Set(docs.map(d => d.dt_abertura?.slice(0, 4)).filter(Boolean))].sort().reverse(), [docs])
  const modalidades = useMemo(() =>
    [...new Set(docs.map(d => d.modalidade).filter(Boolean))].sort(), [docs])
  const situacoes = useMemo(() =>
    [...new Set(docs.map(d => d.situacao).filter(Boolean))].sort(), [docs])
  const canais = useMemo(() =>
    [...new Set(docs.map(d => d.canal).filter(Boolean))].sort(), [docs])

  const MESES = useMemo(() => {
    const f = new Intl.DateTimeFormat(locale, { month: 'short' })
    return Array.from({ length: 12 }, (_, i) => {
      const m = f.format(new Date(2020, i, 15)).replace('.', '')
      return m.charAt(0).toUpperCase() + m.slice(1)
    })
  }, [locale])

  const filtered = useMemo(() => {
    let f = docs
    if (busca) {
      const q = busca.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      f = f.filter(d => {
        const nome = (d.nome_doc ?? d.nome_arquivo ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const obj = (d.objeto ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const proc = (d.processo ?? '').toLowerCase()
        return nome.includes(q) || obj.includes(q) || proc.includes(q)
      })
    }
    if (filAno) f = f.filter(d => d.dt_abertura?.slice(0, 4) === filAno)
    if (filMes) f = f.filter(d => d.dt_abertura?.slice(5, 7) === filMes)
    if (filModalidade) f = f.filter(d => d.modalidade === filModalidade)
    if (filSituacao) f = f.filter(d => d.situacao === filSituacao)
    if (filCanal) f = f.filter(d => d.canal === filCanal)
    return f
  }, [docs, busca, filAno, filMes, filModalidade, filSituacao, filCanal])

  const hasFilters = busca || filAno || filMes || filModalidade || filSituacao || filCanal
  const clearFilters = () => {
    setBusca(''); setFilAno(''); setFilMes('')
    setFilModalidade(''); setFilSituacao(''); setFilCanal(''); setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Esc fecha o visualizador de PDF
  useEffect(() => {
    if (!pdfAberto) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPdfAberto(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pdfAberto])

  // Situação da licitação → tom do selo (o texto da situação vai junto; nunca só a cor).
  const situacaoTom = (s: string): Tom => {
    if (!s) return 'neutro'
    const sl = s.toLowerCase()
    if (sl.includes('vencedor') || sl.includes('empenhado') || sl.includes('conclu')) return 'ok'
    if (sl.includes('fracassado') || sl.includes('cancelado') || sl.includes('deserto')) return 'erro'
    return 'aviso'
  }

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>{t('carregando')}</p>
      </div>
    </div>
  )

  return (
    <div className="page">
      <PageHeader title={t('titulo')} subtitle={t('subtitulo')} source={t('fonte')} />

      {/* ── Modal PDF ── */}
      {pdfAberto && (
        <div
          role="dialog" aria-modal="true" aria-label={pdfAberto.nome_doc || pdfAberto.nome_arquivo}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}
        >
          <div style={{ background: 'var(--branco)', padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--borda)', flexShrink: 0, gap: 16 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--texto)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'flex', alignItems: 'center', gap: 8 }}>
                <FileText size={18} aria-hidden style={{ flexShrink: 0, color: 'var(--verde)' }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{pdfAberto.nome_doc || pdfAberto.nome_arquivo}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 3, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {pdfAberto.processo && <span style={META}><ClipboardList size={13} aria-hidden /> {pdfAberto.processo}</span>}
                {pdfAberto.dt_abertura && <span style={META}><Calendar size={13} aria-hidden /> {fmtData(pdfAberto.dt_abertura)}</span>}
                {pdfAberto.modalidade && <span style={META}><Tag size={13} aria-hidden /> {pdfAberto.modalidade}</span>}
              </div>
              {pdfAberto.objeto && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {pdfAberto.objeto.slice(0, 100)}...
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <a href={toDownloadUrl(pdfAberto.url_publica)} target="_blank" rel="noopener noreferrer"
                className="btn btn-primario btn-sm">
                <Download size={15} aria-hidden /> {t('baixar')}
              </a>
              <button onClick={() => setPdfAberto(null)} className="btn btn-secundario btn-sm" autoFocus>
                <X size={15} aria-hidden /> {t('fechar')}
              </button>
            </div>
          </div>
          <iframe src={toEmbedUrl(pdfAberto.url_publica)}
            style={{ flex: 1, border: 'none', width: '100%', background: 'var(--cinza)' }}
            title={pdfAberto.nome_doc} />
        </div>
      )}

      {/* ── Barra de busca + filtros ── */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8, background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '8px 14px' }}>
            <Search size={16} aria-hidden style={{ color: 'var(--texto-suave)', flexShrink: 0 }} />
            <input
              style={{ flex: 1, border: 'none', background: 'transparent', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder={t('buscarPlaceholder')}
              aria-label={t('buscarPlaceholder')}
              value={busca}
              onChange={e => { setBusca(e.target.value); setPage(1) }}
            />
            {busca && (
              <button onClick={() => setBusca('')} aria-label={t('limparBusca')} title={t('limparBusca')}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--texto-suave)', display: 'flex', padding: 2 }}>
                <X size={16} aria-hidden />
              </button>
            )}
          </div>
          <button onClick={() => setShowFilters(v => !v)} className="btn btn-secundario btn-sm" aria-expanded={showFilters}
            style={showFilters ? { background: 'var(--verde-fundo)', borderColor: 'var(--verde)', color: 'var(--verde)' } : undefined}>
            <SlidersHorizontal size={15} aria-hidden /> {t('filtros')}{hasFilters ? ` (${[filAno,filMes,filModalidade,filSituacao,filCanal].filter(Boolean).length})` : ''}
          </button>
          {hasFilters && (
            <button onClick={clearFilters} className="btn btn-sutil btn-sm">
              <X size={15} aria-hidden /> {t('limpar')}
            </button>
          )}
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
            {t('nDocumentos', { n: filtered.length })}
          </span>
        </div>

        {showFilters && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--borda)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
            <div>
              <label htmlFor="fil-ano" style={LABEL}>{t('ano')}</label>
              <select id="fil-ano" className="filter-select" style={{ width: '100%' }} value={filAno} onChange={e => { setFilAno(e.target.value); setPage(1) }}>
                <option value="">{t('todos')}</option>
                {anos.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="fil-mes" style={LABEL}>{t('mes')}</label>
              <select id="fil-mes" className="filter-select" style={{ width: '100%' }} value={filMes} onChange={e => { setFilMes(e.target.value); setPage(1) }}>
                <option value="">{t('todos')}</option>
                {MESES.map((m, i) => <option key={i} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="fil-modalidade" style={LABEL}>{t('modalidade')}</label>
              <select id="fil-modalidade" className="filter-select" style={{ width: '100%' }} value={filModalidade} onChange={e => { setFilModalidade(e.target.value); setPage(1) }}>
                <option value="">{t('todas')}</option>
                {modalidades.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="fil-situacao" style={LABEL}>{t('situacao')}</label>
              <select id="fil-situacao" className="filter-select" style={{ width: '100%' }} value={filSituacao} onChange={e => { setFilSituacao(e.target.value); setPage(1) }}>
                <option value="">{t('todas')}</option>
                {situacoes.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="fil-canal" style={LABEL}>{t('canal')}</label>
              <select id="fil-canal" className="filter-select" style={{ width: '100%' }} value={filCanal} onChange={e => { setFilCanal(e.target.value); setPage(1) }}>
                <option value="">{t('todos')}</option>
                {canais.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* ── Lista ── */}
      {pageItems.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={44} aria-hidden />
          <strong>{t('nenhum')}</strong>
          <span style={{ fontSize: 14 }}>{t('ajustar')}</span>
        </div>
      ) : pageItems.map(doc => {
        const sc = situacaoTom(doc.situacao)
        return (
          <div key={doc.id} className="item-card" style={{ cursor: 'pointer', alignItems: 'flex-start' }}
            role="button" tabIndex={0}
            onClick={() => setPdfAberto(doc)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPdfAberto(doc) } }}>
            <div aria-hidden style={{ width: 44, height: 44, background: 'var(--verde-fundo)', color: 'var(--verde)', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <FileText size={22} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="item-title" style={{ marginBottom: 6 }}>{doc.nome_doc || doc.nome_arquivo}</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 6 }}>
                {doc.processo && (
                  <span style={{ ...META, background: 'var(--cinza-claro)', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
                    <ClipboardList size={12} aria-hidden /> {doc.processo}
                  </span>
                )}
                {doc.dt_abertura && (
                  <span style={{ ...META, fontSize: 11, color: 'var(--texto-suave)' }}>
                    <Calendar size={12} aria-hidden /> {fmtData(doc.dt_abertura)}
                  </span>
                )}
                {doc.modalidade && (
                  <StatusBadge tom="info">{doc.modalidade}</StatusBadge>
                )}
                {doc.situacao && (
                  <StatusBadge tom={sc}>{doc.situacao}</StatusBadge>
                )}
              </div>
              {doc.objeto && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', lineHeight: 1.4 }}>
                  {doc.objeto.slice(0, 130)}{doc.objeto.length > 130 ? '...' : ''}
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              {doc.tamanho_bytes > 0 && (
                <span style={{ fontSize: 11, color: 'var(--texto-suave)', fontWeight: 600 }}>{fmtBytes(doc.tamanho_bytes)}</span>
              )}
              <span style={{ ...META, background: 'var(--verde-fundo)', color: 'var(--verde)', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 7, border: '1px solid var(--borda)', whiteSpace: 'nowrap' }}>
                <Eye size={13} aria-hidden /> {t('visualizar')}
              </span>
            </div>
          </div>
        )
      })}

      {/* ── Paginação ── */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="page-btn" onClick={() => setPage(1)} disabled={page === 1} aria-label={t('primeira')} title={t('primeira')}>«</button>
          <button className="page-btn" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} aria-label={t('anterior')} title={t('anterior')}>‹</button>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const start = Math.max(1, Math.min(page - 2, totalPages - 4))
            const p = start + i
            return <button key={p} className={`page-btn${page === p ? ' active' : ''}`} onClick={() => setPage(p)}>{p}</button>
          })}
          <button className="page-btn" onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} aria-label={t('proxima')} title={t('proxima')}>›</button>
          <button className="page-btn" onClick={() => setPage(totalPages)} disabled={page === totalPages} aria-label={t('ultima')} title={t('ultima')}>»</button>
        </div>
      )}
    </div>
  )
}

// Metadado com ícone (processo, data, modalidade)
const META = { display: 'inline-flex', alignItems: 'center', gap: 4 } as const
const LABEL = {
  fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4,
  textTransform: 'uppercase', letterSpacing: '0.04em',
} as const
