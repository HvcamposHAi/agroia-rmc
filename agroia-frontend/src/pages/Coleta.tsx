import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { streamPost } from '../lib/apiClient'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ConsultaPortal {
  url: string
  orgao: string
  dt_inicio: string
  dt_fim: string
  registros_por_pagina: number
}

interface StatusColeta {
  status: 'idle' | 'running' | 'completed' | 'cancelled' | 'error'
  etapa: string
  processados: number
  novos: number
  pulados: number
  erros: number
  itens_coletados: number
  fornecedores: number
  empenhos: number
  iniciado_em: string | null
  atualizado_em: string
  pid: number | null
  consulta_portal?: ConsultaPortal
}

interface StatsClass {
  timestamp: string
  total_licitacoes: number
  total_agricolas: number
  total_nao_agricolas: number
  cobertura_agricola_pct: number
  total_itens: number
  itens_por_categoria: Record<string, number>
  licitacoes_agricolas_por_ano: Record<string, number>
}

interface ConfigAgendamento {
  dia_semana: number  // 0 = seg, 1 = ter, ..., 6 = dom
  hora: number        // 0-23
  minuto: number      // 0-59
}

const ETAPA_LABELS: Record<string, string> = {
  'iniciando': '🔄 Iniciando...',
  'coletando': '📥 Coletando dados...',
  'finalizado': '✓ Finalizado',
}

const STATUS_LABELS: Record<string, string> = {
  'idle': '⏸️ Parado',
  'running': '🟢 Em andamento',
  'completed': '✅ Concluído',
  'cancelled': '⛔ Cancelado',
  'error': '❌ Erro',
}

const STATUS_COLORS: Record<string, string> = {
  'idle': '#9ca3af',
  'running': '#22c55e',
  'completed': '#10b981',
  'cancelled': '#ef4444',
  'error': '#dc2626',
}

const CATEGORIA_COLORS: Record<string, string> = {
  'HORTIFRUTI': '#059669',
  'FRUTAS': '#fb7185',
  'GRAOS_CEREAIS': '#ca8a04',
  'LATICINIOS': '#f59e0b',
  'PROTEINA_ANIMAL': '#d97706',
  'PROCESSADOS_AF': '#8b5cf6',
  'INSUMOS_NAO_AGRO': '#64748b',
  'OUTRO': '#6b7280',
  'NAO_CLASSIFICADO': '#d1d5db',
}

export default function Coleta() {
  const [status, setStatus] = useState<StatusColeta | null>(null)
  const [stats, setStats] = useState<StatsClass | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'controle' | 'agendamento'>('controle')
  const [config, setConfig] = useState<ConfigAgendamento>({ dia_semana: 0, hora: 6, minuto: 0 })
  const [savingConfig, setSavingConfig] = useState(false)

  // Carregar stats iniciais
  useEffect(() => {
    loadStats()
    loadStatus()
    loadConfig()
    const interval = setInterval(() => {
      if (!loading) {
        loadStatus()
        loadStats()
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [loading])

  const loadStatus = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/coleta/status`)
      setStatus(resp.data)
      if (resp.data.status === 'running') {
        setLoading(true)
      }
    } catch (e) {
      console.error('Erro ao carregar status:', e)
    }
  }

  const loadStats = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/coleta/stats`)
      setStats(resp.data)
    } catch (e) {
      console.error('Erro ao carregar stats:', e)
    }
  }

  const iniciarColeta = async () => {
    setLoading(true)
    setError('')
    try {
      const resp = await axios.post(`${API_BASE}/coleta/iniciar`, {}, {
        headers: { 'X-API-Key': import.meta.env.VITE_API_KEY || '' }
      })
      setStatus(resp.data.status)
      streamarProgresso()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erro ao iniciar coleta')
      setLoading(false)
    }
  }

  const streamarProgresso = async () => {
    // Aguardar um pouco para o subprocess ser iniciado
    await new Promise(resolve => setTimeout(resolve, 1000))

    try {
      for await (const event of streamPost<StatusColeta>('/coleta/stream')) {
        setStatus(event)
        if (event.status === 'completed' || event.status === 'cancelled' || event.status === 'error') {
          setLoading(false)
          loadStats()
          break
        }
      }
    } catch (e: any) {
      setError(e.message || 'Erro ao conectar ao servidor')
      setLoading(false)
    }
  }

  const cancelarColeta = async () => {
    try {
      await axios.post(`${API_BASE}/coleta/cancelar`, {}, {
        headers: { 'X-API-Key': import.meta.env.VITE_API_KEY || '' }
      })
      setLoading(false)
      loadStatus()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erro ao cancelar coleta')
    }
  }

  const loadConfig = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/coleta/config`)
      setConfig(resp.data)
    } catch (e) {
      console.error('Erro ao carregar configuração:', e)
    }
  }

  const salvarConfig = async () => {
    setSavingConfig(true)
    try {
      await axios.post(`${API_BASE}/coleta/config`, config, {
        headers: { 'X-API-Key': import.meta.env.VITE_API_KEY || '' }
      })
      setError('')
      alert('Configuração salva com sucesso! A coleta semanal foi atualizada.')
      loadConfig()
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Erro ao salvar configuração')
    } finally {
      setSavingConfig(false)
    }
  }

  // ── Preparar dados para charts ──
  const piechartData = stats ? [
    { name: 'Agrícolas', value: stats.total_agricolas, color: '#059669' },
    { name: 'Não-Agrícolas', value: stats.total_nao_agricolas, color: '#9ca3af' }
  ] : []

  const categoriasData = stats && stats.itens_por_categoria
    ? Object.entries(stats.itens_por_categoria)
      .map(([cat, count]) => ({
        categoria: cat,
        quantidade: count,
        color: CATEGORIA_COLORS[cat] || '#6b7280'
      }))
      .sort((a, b) => b.quantidade - a.quantidade)
      .slice(0, 10)
    : []

  const anosData = stats && stats.licitacoes_agricolas_por_ano
    ? Object.entries(stats.licitacoes_agricolas_por_ano)
      .map(([year, count]) => ({
        ano: year,
        licitacoes: count
      }))
      .sort((a, b) => parseInt(a.ano) - parseInt(b.ano))
    : []

  const diasSemana = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

  return (
    <div className="page" style={{ maxWidth: 1400 }}>
      {/* ─── HEADER COM ABAS ─────────────────────────────────────────── */}
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px', marginBottom: 24 }}>
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontFamily: 'Fraunces, serif', fontSize: 22, fontWeight: 700, color: 'var(--texto)', marginBottom: 8 }}>
            📊 Atualização de Dados
          </h2>
          <p style={{ fontSize: 14, color: 'var(--texto-suave)', lineHeight: 1.6, margin: 0 }}>
            Busque novos dados agrícolas do portal com um clique ou configure atualizações automáticas.
          </p>
        </div>

        {/* Abas */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid var(--borda)' }}>
          <button
            onClick={() => setActiveTab('controle')}
            style={{
              background: activeTab === 'controle' ? 'var(--verde)' : 'transparent',
              color: activeTab === 'controle' ? '#fff' : 'var(--texto)',
              border: 'none',
              padding: '12px 20px',
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              marginBottom: -2,
            }}
          >
            🎮 Controle
          </button>
          <button
            onClick={() => setActiveTab('agendamento')}
            style={{
              background: activeTab === 'agendamento' ? 'var(--verde)' : 'transparent',
              color: activeTab === 'agendamento' ? '#fff' : 'var(--texto)',
              border: 'none',
              padding: '12px 20px',
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
              borderRadius: '8px 8px 0 0',
              marginBottom: -2,
              marginLeft: 8,
            }}
          >
            ⏰ Agendamento
          </button>
        </div>
      </div>

      {/* ─── ABA 1: Controle ─────────────────────────────────────────── */}
      {activeTab === 'controle' && (
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px', marginBottom: 24 }}>
        <div></div>

        {/* Status card */}
        <div style={{
          background: '#f9fafb',
          border: `2px solid ${STATUS_COLORS[status?.status || 'idle']}`,
          borderRadius: 12,
          padding: 16,
          marginBottom: 16
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 4 }}>STATUS</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: STATUS_COLORS[status?.status || 'idle'] }}>
                {STATUS_LABELS[status?.status || 'idle']}
              </p>
            </div>
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 4 }}>ETAPA</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)' }}>
                {ETAPA_LABELS[status?.etapa || 'nenhuma'] || status?.etapa || '—'}
              </p>
            </div>
            <div>
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 4 }}>PRÓXIMA EXEC.</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)' }}>
                Próx. seg. 06:00
              </p>
            </div>
          </div>
        </div>

        {/* Botões de controle */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button
            onClick={iniciarColeta}
            disabled={loading}
            style={{
              background: loading ? 'var(--borda)' : '#059669',
              color: '#fff',
              border: 'none',
              borderRadius: 12,
              padding: '14px 24px',
              fontFamily: 'Nunito',
              fontSize: 15,
              fontWeight: 800,
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1
            }}
          >
            {loading ? '🔄 Buscando...' : '🔍 Buscar Dados'}
          </button>
          {loading && (
            <button
              onClick={cancelarColeta}
              style={{
                background: '#ef4444',
                color: '#fff',
                border: 'none',
                borderRadius: 12,
                padding: '14px 24px',
                fontFamily: 'Nunito',
                fontSize: 15,
                fontWeight: 800,
                cursor: 'pointer'
              }}
            >
              ⛔ Cancelar
            </button>
          )}
        </div>

        {error && (
          <div style={{ marginTop: 16, padding: 12, background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#b91c1c' }}>
            <p style={{ fontSize: 14, margin: 0 }}>❌ {error}</p>
          </div>
        )}
      </div>
      )}

      {/* ─── SEÇÃO 2: Progresso em Tempo Real ─────────────────────────────── */}
      {loading && status && (
        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px', marginBottom: 24 }}>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--texto)', marginBottom: 16 }}>
            📈 Progresso em Tempo Real
          </h3>

          {/* Barra de progresso estimada */}
          <div style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              Processando... {status.processados} licitações
            </p>
            <div style={{
              background: '#e5e7eb',
              borderRadius: 8,
              height: 24,
              overflow: 'hidden',
              position: 'relative'
            }}>
              <div style={{
                background: '#059669',
                width: `${Math.min((status.processados / 100) * 100, 100)}%`,
                height: '100%',
                transition: 'width 0.3s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <span style={{ color: '#fff', fontSize: 12, fontWeight: 700 }}>
                  {Math.min(status.processados, 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* KPIs em tempo real */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#15803d', marginBottom: 4 }}>PROCESSADOS</p>
              <p style={{ fontSize: 18, fontWeight: 700, color: '#15803d' }}>{status.processados}</p>
            </div>
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#15803d', marginBottom: 4 }}>NOVOS</p>
              <p style={{ fontSize: 18, fontWeight: 700, color: '#15803d' }}>{status.novos}</p>
            </div>
            <div style={{ background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#92400e', marginBottom: 4 }}>PULADOS</p>
              <p style={{ fontSize: 18, fontWeight: 700, color: '#92400e' }}>{status.pulados}</p>
            </div>
            <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: 12 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#b91c1c', marginBottom: 4 }}>ERROS</p>
              <p style={{ fontSize: 18, fontWeight: 700, color: '#b91c1c' }}>{status.erros}</p>
            </div>
          </div>

          {/* Informações de Consulta ao Portal */}
          {status.consulta_portal && (
            <div style={{ marginTop: 20, padding: 16, background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 8 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#4b5563', marginBottom: 12, textTransform: 'uppercase' }}>
                ℹ️ Consulta ao Portal
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13, lineHeight: 1.6, color: '#374151', fontFamily: 'monospace' }}>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>URL:</p>
                  <p style={{ margin: '4px 0 0 0', wordBreak: 'break-all', fontSize: 12 }}>{status.consulta_portal.url}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>Órgão:</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.orgao}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>Data Inicial:</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.dt_inicio}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>Data Final:</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.dt_fim}</p>
                </div>
              </div>
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #d1d5db', fontSize: 12, color: '#6b7280' }}>
                <p style={{ margin: 0 }}>Registros por página: <strong>{status.consulta_portal.registros_por_pagina}</strong></p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── ABA 2: Agendamento ──────────────────────────────────────── */}
      {activeTab === 'agendamento' && (
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px', marginBottom: 24 }}>
        <h3 style={{ fontSize: 18, fontWeight: 700, color: 'var(--texto)', marginBottom: 20 }}>
          ⏰ Configurar Agendamento Semanal
        </h3>

        <p style={{ fontSize: 14, color: 'var(--texto-suave)', marginBottom: 16 }}>
          Configure o dia e hora para a coleta automática semanal. O sistema iniciará a coleta automaticamente neste horário.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 24 }}>
          {/* Dia da Semana */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              Dia da Semana
            </label>
            <select
              value={config.dia_semana}
              onChange={(e) => setConfig({ ...config, dia_semana: parseInt(e.target.value) })}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid var(--borda)',
                borderRadius: 8,
                fontSize: 14,
                fontFamily: 'Nunito',
              }}
            >
              {diasSemana.map((dia, idx) => (
                <option key={idx} value={idx}>{dia}</option>
              ))}
            </select>
          </div>

          {/* Hora */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              Hora (0-23)
            </label>
            <input
              type="number"
              min="0"
              max="23"
              value={config.hora}
              onChange={(e) => setConfig({ ...config, hora: parseInt(e.target.value) || 0 })}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid var(--borda)',
                borderRadius: 8,
                fontSize: 14,
                fontFamily: 'Nunito',
              }}
            />
          </div>

          {/* Minuto */}
          <div>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              Minuto (0-59)
            </label>
            <input
              type="number"
              min="0"
              max="59"
              value={config.minuto}
              onChange={(e) => setConfig({ ...config, minuto: parseInt(e.target.value) || 0 })}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid var(--borda)',
                borderRadius: 8,
                fontSize: 14,
                fontFamily: 'Nunito',
              }}
            />
          </div>
        </div>

        {/* Preview */}
        <div style={{
          background: '#f0fdf4',
          border: '1px solid #86efac',
          borderRadius: 12,
          padding: 16,
          marginBottom: 24
        }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: '#15803d', margin: 0 }}>
            ✓ Coleta agendada para: <strong>{diasSemana[config.dia_semana]} às {config.hora.toString().padStart(2, '0')}:{config.minuto.toString().padStart(2, '0')}</strong>
          </p>
        </div>

        {/* Botão Salvar */}
        <button
          onClick={salvarConfig}
          disabled={savingConfig}
          style={{
            background: savingConfig ? 'var(--borda)' : 'var(--verde)',
            color: '#fff',
            border: 'none',
            borderRadius: 12,
            padding: '14px 28px',
            fontFamily: 'Nunito',
            fontSize: 15,
            fontWeight: 800,
            cursor: savingConfig ? 'not-allowed' : 'pointer',
            opacity: savingConfig ? 0.6 : 1,
          }}
        >
          {savingConfig ? '💾 Salvando...' : '💾 Salvar Configuração'}
        </button>

        {error && (
          <div style={{ marginTop: 16, padding: 12, background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, color: '#b91c1c' }}>
            <p style={{ fontSize: 14, margin: 0 }}>❌ {error}</p>
          </div>
        )}
      </div>
      )}

      {/* ─── SEÇÃO 3: Estatísticas de Classificação ──────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 20, marginBottom: 24 }}>
        {/* KPIs principais */}
        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>TOTAL DE LICITAÇÕES</p>
          <h3 style={{ fontSize: 28, fontWeight: 700, color: 'var(--texto)', margin: 0, marginBottom: 4 }}>
            {stats?.total_licitacoes || '—'}
          </h3>
          <p style={{ fontSize: 13, color: 'var(--texto-suave)', margin: 0 }}>
            {stats ? `${stats.total_agricolas} agrícolas (${stats.cobertura_agricola_pct}%)` : '—'}
          </p>
        </div>

        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>TOTAL DE ITENS</p>
          <h3 style={{ fontSize: 28, fontWeight: 700, color: 'var(--texto)', margin: 0, marginBottom: 4 }}>
            {stats?.total_itens || '—'}
          </h3>
          <p style={{ fontSize: 13, color: 'var(--texto-suave)', margin: 0 }}>Produtos e serviços</p>
        </div>

        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>COBERTURA AGRÍCOLA</p>
          <h3 style={{ fontSize: 28, fontWeight: 700, color: 'var(--texto)', margin: 0, marginBottom: 4 }}>
            {stats?.cobertura_agricola_pct || '—'}%
          </h3>
          <p style={{ fontSize: 13, color: 'var(--texto-suave)', margin: 0 }}>Do total de licitações</p>
        </div>
      </div>

      {/* Gráficos */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20, marginBottom: 24 }}>
        {/* Pie: Agrícola vs Não-Agrícola */}
        {stats && piechartData.length > 0 && (
          <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)', marginBottom: 16, margin: '0 0 16px 0' }}>
              Licitações: Agrícola vs Não-Agrícola
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={piechartData} cx="50%" cy="50%" labelLine={false} label={({ name, value }) => `${name}: ${value}`} outerRadius={80}>
                  {piechartData.map((entry, idx) => (
                    <Cell key={`cell-${idx}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Bar: Itens por Categoria */}
        {stats && categoriasData.length > 0 && (
          <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)', marginBottom: 16, margin: '0 0 16px 0' }}>
              Top 10 Categorias
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={categoriasData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--borda)" />
                <XAxis dataKey="categoria" angle={-45} textAnchor="end" height={100} tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="quantidade" radius={[8, 8, 0, 0]}>
                  {categoriasData.map((entry, idx) => (
                    <Cell key={`cell-${idx}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Bar: Licitações Agrícolas por Ano */}
      {stats && anosData.length > 0 && (
        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px' }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)', marginBottom: 16, margin: '0 0 16px 0' }}>
            Licitações Agrícolas por Ano
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={anosData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--borda)" />
              <XAxis dataKey="ano" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="licitacoes" fill="#059669" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
