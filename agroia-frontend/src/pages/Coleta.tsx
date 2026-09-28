import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { streamPost, iniciarColeta as apiIniciarColeta, cancelarColeta as apiCancelarColeta, salvarConfigColeta } from '../lib/apiClient'
import { formatarDataHora } from '../lib/format'
import { defineMessages, useT, useI18n } from '../i18n'
import axios from 'axios'
import {
  Activity, Ban, Calendar, CalendarClock, CircleAlert, CircleCheck, CirclePause, CircleX,
  Clock, Download, History, Info, RefreshCw, Save, Square, TriangleAlert,
} from 'lucide-react'
import { TONS, type Tom } from '../lib/tons'
import PageHeader from '../components/PageHeader'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// Em produção (nuvem/Render) a coleta por navegador não roda — execute localmente.
// Setar VITE_COLETA_ENABLED=false no build do Cloudflare Pages.
const COLETA_ENABLED = (import.meta.env.VITE_COLETA_ENABLED ?? 'true').toString().toLowerCase() !== 'false'

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
  run_id?: string | null
  msg?: string
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

interface ErroDetalhe {
  processo: string
  mensagem: string
}

interface UltimaExecucao {
  id: number
  iniciado_em: string | null
  finalizado_em: string
  duracao_seg: number | null
  status: 'completed' | 'error' | 'cancelled' | string
  etapa: string | null
  origem: string | null
  dt_inicio: string | null
  dt_fim: string | null
  processados: number
  novos: number
  pulados: number
  erros: number
  itens_coletados: number
  fornecedores: number
  empenhos: number
  erro_resumo: string | null
  erro_detalhes: ErroDetalhe[] | null
}

const MSG = defineMessages({
  pt: {
    etapaIniciando: 'Iniciando...',
    etapaColetando: 'Coletando dados...',
    etapaFinalizado: 'Finalizado',
    etapaTimeout: 'Sem resposta',
    etapaFalha: 'Falha',
    statusIdle: 'Parado',
    statusRunning: 'Em andamento',
    statusCompleted: 'Concluído',
    statusCancelled: 'Cancelado',
    statusError: 'Erro',
    erroIniciar: 'Erro ao iniciar coleta',
    erroConectar: 'Erro ao conectar ao servidor',
    erroCancelar: 'Erro ao cancelar coleta',
    configSalva: 'Configuração salva com sucesso! A coleta semanal foi atualizada.',
    erroSalvarConfig: 'Erro ao salvar configuração',
    agricolas: 'Agrícolas',
    naoAgricolas: 'Não-Agrícolas',
    proxAbrev: 'Próx. {dia} {hora}',
    eyebrow: 'Gestão',
    titulo: 'Atualização de dados',
    fonte: 'Fonte: Portal da Transparência de Curitiba, órgão FAAC',
    subtitulo: 'Busque novos dados agrícolas do portal com um clique ou configure atualizações automáticas.',
    abaControle: 'Controle',
    abaAgendamento: 'Agendamento',
    lblStatus: 'STATUS',
    lblEtapa: 'ETAPA',
    lblProximaExec: 'PRÓXIMA EXEC.',
    ultimaAtualizacao: 'Última Atualização',
    semExecucoes: 'Sem execuções registradas ainda. Os dados aparecerão aqui após a primeira coleta.',
    lblData: 'DATA',
    lblResultado: 'RESULTADO',
    lblIntervalo: 'INTERVALO CONSULTADO',
    lblDuracao: 'DURAÇÃO',
    duracao: '{min}min {seg}s',
    concluidaSemNovas: 'Concluída — nenhuma licitação nova no período',
    puladaUma: ' ({n} já existente foi pulada).',
    puladasVarias: ' ({n} já existentes foram puladas).',
    coletaExpirou: 'A coleta expirou sem responder (job travado ou Portal da Transparência fora do ar). Tente novamente.',
    coletaErro: 'A coleta terminou com erro — veja o detalhe abaixo.',
    oQueAtualizado: 'O que foi atualizado',
    kpiProcessados: 'PROCESSADOS',
    kpiItens: 'ITENS',
    kpiFornecedores: 'FORNECEDORES',
    kpiEmpenhos: 'EMPENHOS',
    kpiPulados: 'PULADOS',
    kpiNovos: 'LICITAÇÕES NOVAS',
    kpiErros: 'ERROS',
    falhasAtualizacao: 'Falhas na atualização',
    nenhumaFalha: 'Nenhuma falha registrada nesta execução.',
    falhaUma: '{n} falha registrada',
    falhasVarias: '{n} falhas registradas',
    falhaExecucao: 'Falha na execução',
    verDetalhe: 'Ver detalhe ({n})',
    executeLocal: 'Execute a coleta na máquina local',
    buscando: 'Buscando...',
    buscarDados: 'Buscar dados',
    cancelar: 'Cancelar',
    avisoLocal: 'A coleta roda automaticamente todos os dias às 06:00 (Portal da Transparência de Curitiba). Nesta instalação o disparo manual está desativado; esta página exibe o status e as estatísticas mais recentes da base.',
    progressoTitulo: 'Progresso em Tempo Real',
    processando: 'Processando... {n} licitações',
    consultaPortal: 'Consulta ao Portal',
    lblUrl: 'URL:',
    lblOrgao: 'Órgão:',
    lblDataInicial: 'Data Inicial:',
    lblDataFinal: 'Data Final:',
    registrosPorPagina: 'Registros por página:',
    agendamentoTitulo: 'Configurar Agendamento Semanal',
    agendamentoDesc: 'Configure o dia e hora para a coleta automática semanal. O sistema iniciará a coleta automaticamente neste horário.',
    lblDiaSemana: 'Dia da Semana',
    lblHora: 'Hora (0-23)',
    lblMinuto: 'Minuto (0-59)',
    agendadaPara: 'Coleta agendada para:',
    diaAs: '{dia} às {hora}',
    salvando: 'Salvando...',
    salvarConfig: 'Salvar configuração',
    totalLicitacoes: 'TOTAL DE LICITAÇÕES',
    agricolasPct: '{n} agrícolas ({pct}%)',
    totalItens: 'TOTAL DE ITENS',
    itensAgricolas: 'Itens agrícolas',
    coberturaAgricola: 'COBERTURA AGRÍCOLA',
    doTotalLicitacoes: 'Do total de licitações',
    graficoAgroVsNao: 'Licitações: Agrícola vs Não-Agrícola',
    top10Categorias: 'Top 10 Categorias',
    licitacoesPorAno: 'Licitações Agrícolas por Ano',
    serieQuantidade: 'Quantidade',
    serieLicitacoes: 'Licitações',
  },
  en: {
    etapaIniciando: 'Starting...',
    etapaColetando: 'Collecting data...',
    etapaFinalizado: 'Finished',
    etapaTimeout: 'No response',
    etapaFalha: 'Failed',
    statusIdle: 'Idle',
    statusRunning: 'Running',
    statusCompleted: 'Completed',
    statusCancelled: 'Cancelled',
    statusError: 'Error',
    erroIniciar: 'Error starting data collection',
    erroConectar: 'Error connecting to the server',
    erroCancelar: 'Error cancelling data collection',
    configSalva: 'Settings saved successfully! The weekly data collection has been updated.',
    erroSalvarConfig: 'Error saving settings',
    agricolas: 'Agricultural',
    naoAgricolas: 'Non-agricultural',
    proxAbrev: 'Next {dia} {hora}',
    eyebrow: 'Management',
    titulo: 'Data update',
    fonte: 'Source: Curitiba Transparency Portal, agency FAAC',
    subtitulo: 'Fetch new agricultural data from the portal with one click or set up automatic updates.',
    abaControle: 'Control',
    abaAgendamento: 'Schedule',
    lblStatus: 'STATUS',
    lblEtapa: 'STAGE',
    lblProximaExec: 'NEXT RUN',
    ultimaAtualizacao: 'Last Update',
    semExecucoes: 'No runs recorded yet. Data will appear here after the first data collection.',
    lblData: 'DATE',
    lblResultado: 'RESULT',
    lblIntervalo: 'QUERIED RANGE',
    lblDuracao: 'DURATION',
    duracao: '{min}min {seg}s',
    concluidaSemNovas: 'Completed — no new biddings in the period',
    puladaUma: ' ({n} already existing was skipped).',
    puladasVarias: ' ({n} already existing were skipped).',
    coletaExpirou: 'The data collection timed out without responding (job stuck or Transparency Portal offline). Please try again.',
    coletaErro: 'The data collection ended with an error — see the details below.',
    oQueAtualizado: 'What was updated',
    kpiProcessados: 'PROCESSED',
    kpiItens: 'ITEMS',
    kpiFornecedores: 'SUPPLIERS',
    kpiEmpenhos: 'COMMITMENTS',
    kpiPulados: 'SKIPPED',
    kpiNovos: 'NEW TENDERS',
    kpiErros: 'ERRORS',
    falhasAtualizacao: 'Update failures',
    nenhumaFalha: 'No failures recorded in this run.',
    falhaUma: '{n} failure recorded',
    falhasVarias: '{n} failures recorded',
    falhaExecucao: 'Run failed',
    verDetalhe: 'View details ({n})',
    executeLocal: 'Run the data collection on the local machine',
    buscando: 'Fetching...',
    buscarDados: 'Fetch data',
    cancelar: 'Cancel',
    avisoLocal: 'Collection runs automatically every day at 06:00 (Curitiba Transparency Portal). Manual triggering is disabled in this installation; this page shows the latest status and database statistics.',
    progressoTitulo: 'Real-Time Progress',
    processando: 'Processing... {n} biddings',
    consultaPortal: 'Portal Query',
    lblUrl: 'URL:',
    lblOrgao: 'Agency:',
    lblDataInicial: 'Start Date:',
    lblDataFinal: 'End Date:',
    registrosPorPagina: 'Records per page:',
    agendamentoTitulo: 'Configure Weekly Schedule',
    agendamentoDesc: 'Set the day and time for the automatic weekly data collection. The system will start the data collection automatically at this time.',
    lblDiaSemana: 'Day of the Week',
    lblHora: 'Hour (0-23)',
    lblMinuto: 'Minute (0-59)',
    agendadaPara: 'Data collection scheduled for:',
    diaAs: '{dia} at {hora}',
    salvando: 'Saving...',
    salvarConfig: 'Save settings',
    totalLicitacoes: 'TOTAL BIDDINGS',
    agricolasPct: '{n} agricultural ({pct}%)',
    totalItens: 'TOTAL ITEMS',
    itensAgricolas: 'Agricultural items',
    coberturaAgricola: 'AGRICULTURAL COVERAGE',
    doTotalLicitacoes: 'Of all biddings',
    graficoAgroVsNao: 'Biddings: Agricultural vs Non-agricultural',
    top10Categorias: 'Top 10 Categories',
    licitacoesPorAno: 'Agricultural Biddings per Year',
    serieQuantidade: 'Quantity',
    serieLicitacoes: 'Biddings',
  },
  es: {
    etapaIniciando: 'Iniciando...',
    etapaColetando: 'Recolectando datos...',
    etapaFinalizado: 'Finalizado',
    etapaTimeout: 'Sin respuesta',
    etapaFalha: 'Fallo',
    statusIdle: 'Detenido',
    statusRunning: 'En curso',
    statusCompleted: 'Completado',
    statusCancelled: 'Cancelado',
    statusError: 'Error',
    erroIniciar: 'Error al iniciar la recolección de datos',
    erroConectar: 'Error al conectar con el servidor',
    erroCancelar: 'Error al cancelar la recolección de datos',
    configSalva: '¡Configuración guardada con éxito! La recolección de datos semanal fue actualizada.',
    erroSalvarConfig: 'Error al guardar la configuración',
    agricolas: 'Agrícolas',
    naoAgricolas: 'No agrícolas',
    proxAbrev: 'Próx. {dia} {hora}',
    eyebrow: 'Gestión',
    titulo: 'Actualización de datos',
    fonte: 'Fuente: Portal de la Transparencia de Curitiba, órgano FAAC',
    subtitulo: 'Busque nuevos datos agrícolas del portal con un clic o configure actualizaciones automáticas.',
    abaControle: 'Control',
    abaAgendamento: 'Programación',
    lblStatus: 'ESTADO',
    lblEtapa: 'ETAPA',
    lblProximaExec: 'PRÓXIMA EJEC.',
    ultimaAtualizacao: 'Última Actualización',
    semExecucoes: 'Aún no hay ejecuciones registradas. Los datos aparecerán aquí después de la primera recolección de datos.',
    lblData: 'FECHA',
    lblResultado: 'RESULTADO',
    lblIntervalo: 'INTERVALO CONSULTADO',
    lblDuracao: 'DURACIÓN',
    duracao: '{min}min {seg}s',
    concluidaSemNovas: 'Completada — ninguna licitación nueva en el período',
    puladaUma: ' ({n} ya existente fue omitida).',
    puladasVarias: ' ({n} ya existentes fueron omitidas).',
    coletaExpirou: 'La recolección de datos expiró sin responder (job bloqueado o Portal de Transparencia fuera de línea). Inténtelo de nuevo.',
    coletaErro: 'La recolección de datos terminó con error — vea el detalle abajo.',
    oQueAtualizado: 'Qué se actualizó',
    kpiProcessados: 'PROCESADOS',
    kpiItens: 'ÍTEMS',
    kpiFornecedores: 'PROVEEDORES',
    kpiEmpenhos: 'COMPROMISOS',
    kpiPulados: 'OMITIDOS',
    kpiNovos: 'LICITACIONES NUEVAS',
    kpiErros: 'ERRORES',
    falhasAtualizacao: 'Fallos en la actualización',
    nenhumaFalha: 'Ningún fallo registrado en esta ejecución.',
    falhaUma: '{n} fallo registrado',
    falhasVarias: '{n} fallos registrados',
    falhaExecucao: 'Fallo en la ejecución',
    verDetalhe: 'Ver detalle ({n})',
    executeLocal: 'Ejecute la recolección de datos en la máquina local',
    buscando: 'Buscando...',
    buscarDados: 'Buscar datos',
    cancelar: 'Cancelar',
    avisoLocal: 'La recolección se ejecuta automáticamente todos los días a las 06:00 (Portal de Transparencia de Curitiba). En esta instalación el disparo manual está desactivado; esta página muestra el estado y las estadísticas más recientes de la base.',
    progressoTitulo: 'Progreso en Tiempo Real',
    processando: 'Procesando... {n} licitaciones',
    consultaPortal: 'Consulta al Portal',
    lblUrl: 'URL:',
    lblOrgao: 'Órgano:',
    lblDataInicial: 'Fecha Inicial:',
    lblDataFinal: 'Fecha Final:',
    registrosPorPagina: 'Registros por página:',
    agendamentoTitulo: 'Configurar Programación Semanal',
    agendamentoDesc: 'Configure el día y la hora para la recolección de datos automática semanal. El sistema la iniciará automáticamente a esa hora.',
    lblDiaSemana: 'Día de la Semana',
    lblHora: 'Hora (0-23)',
    lblMinuto: 'Minuto (0-59)',
    agendadaPara: 'Recolección de datos programada para:',
    diaAs: '{dia} a las {hora}',
    salvando: 'Guardando...',
    salvarConfig: 'Guardar configuración',
    totalLicitacoes: 'TOTAL DE LICITACIONES',
    agricolasPct: '{n} agrícolas ({pct}%)',
    totalItens: 'TOTAL DE ÍTEMS',
    itensAgricolas: 'Ítems agrícolas',
    coberturaAgricola: 'COBERTURA AGRÍCOLA',
    doTotalLicitacoes: 'Del total de licitaciones',
    graficoAgroVsNao: 'Licitaciones: Agrícola vs No agrícola',
    top10Categorias: 'Top 10 Categorías',
    licitacoesPorAno: 'Licitaciones Agrícolas por Año',
    serieQuantidade: 'Cantidad',
    serieLicitacoes: 'Licitaciones',
  },
})

type MsgKey = keyof typeof MSG.pt

const ETAPA_LABELS: Record<string, MsgKey | null> = {
  'nenhuma': null,
  'iniciando': 'etapaIniciando',
  'coletando': 'etapaColetando',
  'finalizado': 'etapaFinalizado',
  'timeout': 'etapaTimeout',
  'falha': 'etapaFalha',
}

const STATUS_LABELS: Record<string, MsgKey> = {
  'idle': 'statusIdle',
  'running': 'statusRunning',
  'completed': 'statusCompleted',
  'cancelled': 'statusCancelled',
  'error': 'statusError',
}

// Dia 0 = segunda-feira. 1/jan/2024 foi uma segunda; nomes vêm do Intl no idioma atual.
function nomeDiaSemana(idx: number, locale: string, formato: 'long' | 'short'): string {
  const nome = new Date(2024, 0, 1 + idx).toLocaleDateString(locale, { weekday: formato })
  return formato === 'long' ? nome.charAt(0).toLocaleUpperCase(locale) + nome.slice(1) : nome
}

// Status: cor (tokens de status do index.css) + ícone — nunca só a cor (WCAG 1.4.1).
const STATUS_CFG: Record<string, { tom: Tom; cor: string; Icon: typeof CircleCheck }> = {
  'idle': { tom: 'neutro', cor: TONS.neutro.cor, Icon: CirclePause },
  'running': { tom: 'info', cor: TONS.info.cor, Icon: RefreshCw },
  'completed': { tom: 'ok', cor: TONS.ok.cor, Icon: CircleCheck },
  'cancelled': { tom: 'aviso', cor: TONS.aviso.cor, Icon: Ban },
  'error': { tom: 'erro', cor: TONS.erro.cor, Icon: CircleX },
}

export default function Coleta() {
  const t = useT(MSG)
  const { locale } = useI18n()
  const [status, setStatus] = useState<StatusColeta | null>(null)
  const [stats, setStats] = useState<StatsClass | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'controle' | 'agendamento'>('controle')
  const [config, setConfig] = useState<ConfigAgendamento>({ dia_semana: 0, hora: 6, minuto: 0 })
  const [savingConfig, setSavingConfig] = useState(false)
  const [ultimaExec, setUltimaExec] = useState<UltimaExecucao | null>(null)
  const [proximaExec, setProximaExec] = useState<string | null>(null)

  // Uma coleta em andamento (possivelmente disparada em outra máquina) precisa
  // de sondagem rápida; o estado ocioso não.
  const emAndamento = status?.status === 'running'

  // Carregar stats iniciais (uma vez)
  useEffect(() => {
    loadStats()
    loadStatus()
    loadConfig()
    loadUltimaExecucao()
    loadProximaExec()
  }, [])

  // Sondagem adaptativa: 5s enquanto a coleta roda, 30s no ocioso.
  // Eram 4 requisições a cada 5s sem parar — ~0,94 GB/mês com uma aba aberta,
  // 19% da cota de banda do Render. O progresso durante a coleta vem do SSE
  // (streamarProgresso), então aqui só precisamos detectar mudança de estado.
  useEffect(() => {
    const intervaloMs = emAndamento ? 5000 : 30000
    const interval = setInterval(() => {
      if (!loading) {
        loadStatus()
        loadStats()
        loadUltimaExecucao()
        loadProximaExec()
      }
    }, intervaloMs)
    return () => clearInterval(interval)
  }, [loading, emAndamento])

  const loadUltimaExecucao = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/coleta/ultima-execucao`)
      setUltimaExec(resp.data && resp.data.id ? resp.data : null)
    } catch (e) {
      console.error('Erro ao carregar última execução:', e)
    }
  }

  const loadProximaExec = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/coleta/proxima-execucao`)
      setProximaExec(resp.data?.proxima ?? null)
    } catch (e) {
      console.error('Erro ao carregar próxima execução:', e)
    }
  }

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
      const data = await apiIniciarColeta()
      setStatus(data.status)
      streamarProgresso()
    } catch (e: any) {
      setError(e.response?.data?.detail || t('erroIniciar'))
      setLoading(false)
    }
  }

  const streamarProgresso = async () => {
    // Aguardar um pouco para o subprocess ser iniciado
    await new Promise(resolve => setTimeout(resolve, 1000))

    try {
      for await (const event of streamPost<StatusColeta & { msg?: string }>('/coleta/stream')) {
        setStatus(event)
        if (event.status === 'completed' || event.status === 'cancelled' || event.status === 'error') {
          if (event.status === 'error' && event.msg) {
            setError(event.msg)
          }
          setLoading(false)
          loadStats()
          break
        }
      }
    } catch (e: any) {
      setError(e.message || t('erroConectar'))
      setLoading(false)
    }
  }

  const cancelarColeta = async () => {
    try {
      await apiCancelarColeta()
      setLoading(false)
      loadStatus()
    } catch (e: any) {
      setError(e.response?.data?.detail || t('erroCancelar'))
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
      await salvarConfigColeta(config)
      setError('')
      alert(t('configSalva'))
      loadConfig()
    } catch (e: any) {
      setError(e.response?.data?.detail || t('erroSalvarConfig'))
    } finally {
      setSavingConfig(false)
    }
  }

  // ── Preparar dados para charts ──
  const piechartData = stats ? [
    { name: t('agricolas'), value: stats.total_agricolas, color: 'var(--chart-marca)' },
    { name: t('naoAgricolas'), value: stats.total_nao_agricolas, color: 'var(--cinza)' }
  ] : []

  const categoriasData = stats && stats.itens_por_categoria
    ? Object.entries(stats.itens_por_categoria)
      .map(([cat, count]) => ({
        categoria: cat,
        quantidade: count,
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

  const diasSemana = [0, 1, 2, 3, 4, 5, 6].map(i => nomeDiaSemana(i, locale, 'long'))
  const diasAbrev = [0, 1, 2, 3, 4, 5, 6].map(i => nomeDiaSemana(i, locale, 'short'))
  const horaMinuto = `${config.hora.toString().padStart(2, '0')}:${config.minuto.toString().padStart(2, '0')}`

  // Rótulo da próxima execução: prioriza o ISO do backend (mesma base do
  // APScheduler); cai para um rótulo derivado do config salvo se indisponível.
  const proximaExecLabel = proximaExec
    ? formatarDataHora(proximaExec)
    : t('proxAbrev', { dia: diasAbrev[config.dia_semana], hora: horaMinuto })

  const statusAtual = STATUS_CFG[status?.status || 'idle'] ?? STATUS_CFG.idle
  const StatusIcon = statusAtual.Icon
  const statusUltima = ultimaExec ? STATUS_CFG[ultimaExec.status] : undefined
  const UltimaIcon = statusUltima?.Icon

  // Caixas de KPI (tokens de status do index.css).
  const kpiBox = (familia: 'ok' | 'aviso' | 'erro' | 'neutro') => {
    const neutro = familia === 'neutro'
    return {
      box: {
        background: neutro ? 'var(--cinza-claro)' : `var(--${familia}-fundo)`,
        border: `1px solid ${neutro ? 'var(--borda)' : `var(--${familia}-borda)`}`,
        borderRadius: 'var(--raio-sm)', padding: 10,
      },
      label: { fontSize: 11, fontWeight: 600, color: neutro ? 'var(--texto-suave)' : `var(--${familia})`, marginBottom: 4 },
      valor: { fontSize: 18, fontWeight: 700, color: neutro ? 'var(--texto)' : `var(--${familia})`, fontVariantNumeric: 'tabular-nums' as const },
    }
  }
  const rotulo = { fontSize: 11, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 4 }
  const campo = {
    width: '100%', padding: '10px 12px', border: '1px solid var(--borda)', borderRadius: 'var(--raio-sm)',
    fontSize: 14, fontFamily: 'Inter', background: 'var(--branco)', color: 'var(--texto)',
  }

  return (
    <div className="page" style={{ maxWidth: 1400 }}>
      {/* ─── CABEÇALHO ───────────────────────────────────────────────── */}
      <PageHeader
        eyebrow={t('eyebrow')}
        title={t('titulo')}
        subtitle={t('subtitulo')}
        source={t('fonte')}
        actions={
          <>
            <button
              className="btn btn-primario"
              onClick={iniciarColeta}
              disabled={loading || !COLETA_ENABLED}
              title={!COLETA_ENABLED ? t('executeLocal') : undefined}
            >
              {loading
                ? <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('buscando')}</>
                : <><Download size={16} aria-hidden /> {t('buscarDados')}</>}
            </button>
            {loading && (
              <button className="btn btn-secundario" onClick={cancelarColeta} style={{ color: 'var(--erro)', borderColor: 'var(--erro-borda)' }}>
                <Square size={14} aria-hidden /> {t('cancelar')}
              </button>
            )}
          </>
        }
      />

      {/* Abas */}
      <div className="seg-control" role="tablist" style={{ marginBottom: 20 }}>
        <button
          role="tab"
          aria-selected={activeTab === 'controle'}
          className={`seg-btn${activeTab === 'controle' ? ' active' : ''}`}
          onClick={() => setActiveTab('controle')}
        >
          <Activity size={16} aria-hidden /> {t('abaControle')}
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'agendamento'}
          className={`seg-btn${activeTab === 'agendamento' ? ' active' : ''}`}
          onClick={() => setActiveTab('agendamento')}
        >
          <CalendarClock size={16} aria-hidden /> {t('abaAgendamento')}
        </button>
      </div>

      {/* ─── ABA 1: Controle ─────────────────────────────────────────── */}
      {activeTab === 'controle' && (
      <div className="card" style={{ marginBottom: 24 }}>
        {/* Status card */}
        <div style={{
          background: 'var(--cinza-claro)',
          border: '1px solid var(--borda)',
          borderLeft: `4px solid ${statusAtual.cor}`,
          borderRadius: 'var(--raio)',
          padding: 16,
          marginBottom: 16
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            <div>
              <p style={{ ...rotulo, fontSize: 12 }}>{t('lblStatus')}</p>
              <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 16, fontWeight: 700, color: statusAtual.cor }}>
                <StatusIcon size={18} aria-hidden />
                {t(STATUS_LABELS[status?.status || 'idle'] ?? 'statusIdle')}
              </p>
            </div>
            <div>
              <p style={{ ...rotulo, fontSize: 12 }}>{t('lblEtapa')}</p>
              <p style={{ fontSize: 16, fontWeight: 700, color: 'var(--texto)' }}>
                {(() => {
                  const etapa = status?.etapa || 'nenhuma'
                  const k = ETAPA_LABELS[etapa]
                  return k ? t(k) : (k === null ? '—' : etapa)
                })()}
              </p>
            </div>
            <div>
              <p style={{ ...rotulo, fontSize: 12 }}>{t('lblProximaExec')}</p>
              <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 16, fontWeight: 700, color: 'var(--texto)' }}>
                <Clock size={16} aria-hidden style={{ color: 'var(--texto-suave)' }} />
                {proximaExecLabel}
              </p>
            </div>
          </div>
        </div>

        {/* ── Última Atualização (histórico persistido) ── */}
        <div style={{
          background: 'var(--cinza-claro)',
          border: '1px solid var(--borda)',
          borderLeft: `4px solid ${statusUltima ? statusUltima.cor : 'var(--borda)'}`,
          borderRadius: 'var(--raio)',
          padding: 16,
          marginBottom: 16,
        }}>
          <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700, color: 'var(--texto)', marginBottom: 12 }}>
            <History size={16} aria-hidden style={{ color: 'var(--texto-suave)' }} /> {t('ultimaAtualizacao')}
          </p>

          {!ultimaExec ? (
            <p style={{ fontSize: 14, color: 'var(--texto-suave)', margin: 0 }}>
              {t('semExecucoes')}
            </p>
          ) : (
            <>
              {/* Cabeçalho: data, status, intervalo, duração */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 16 }}>
                <div>
                  <p style={rotulo}>{t('lblData')}</p>
                  <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--texto)' }}>{formatarDataHora(ultimaExec.finalizado_em)}</p>
                </div>
                <div>
                  <p style={rotulo}>{t('lblResultado')}</p>
                  <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 15, fontWeight: 700, color: statusUltima?.cor || 'var(--texto)' }}>
                    {UltimaIcon && <UltimaIcon size={16} aria-hidden />}
                    {STATUS_LABELS[ultimaExec.status] ? t(STATUS_LABELS[ultimaExec.status]) : ultimaExec.status}
                  </p>
                </div>
                <div>
                  <p style={rotulo}>{t('lblIntervalo')}</p>
                  <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--texto)' }}>
                    {ultimaExec.dt_inicio || '—'} → {ultimaExec.dt_fim || '—'}
                  </p>
                </div>
                {ultimaExec.duracao_seg != null && (
                  <div>
                    <p style={rotulo}>{t('lblDuracao')}</p>
                    <p style={{ fontSize: 15, fontWeight: 700, color: 'var(--texto)' }}>
                      {t('duracao', { min: Math.floor(ultimaExec.duracao_seg / 60), seg: ultimaExec.duracao_seg % 60 })}
                    </p>
                  </div>
                )}
              </div>

              {/* Resumo legível — distingue "concluída sem novidades" de falha real,
                  evitando que KPIs zerados pareçam erro. */}
              {ultimaExec.status === 'completed'
                && ultimaExec.novos === 0
                && ultimaExec.itens_coletados === 0
                && ultimaExec.erros === 0 && (
                <div className="aviso-box ok" style={{ marginBottom: 16, fontSize: 13 }}>
                  <CircleCheck size={16} aria-hidden />
                  <span>
                    {t('concluidaSemNovas')}
                    {ultimaExec.pulados > 0
                      ? t(ultimaExec.pulados === 1 ? 'puladaUma' : 'puladasVarias', { n: ultimaExec.pulados })
                      : '.'}
                  </span>
                </div>
              )}
              {(ultimaExec.status === 'error' || ultimaExec.etapa === 'timeout') && (
                <div className="aviso-box aviso" style={{ marginBottom: 16, fontSize: 13 }}>
                  {ultimaExec.etapa === 'timeout' ? <Clock size={16} aria-hidden /> : <TriangleAlert size={16} aria-hidden />}
                  <span>
                    {ultimaExec.etapa === 'timeout'
                      ? t('coletaExpirou')
                      : t('coletaErro')}
                  </span>
                </div>
              )}

              {/* O que foi atualizado */}
              <p style={{ ...rotulo, marginBottom: 8, textTransform: 'uppercase' }}>
                {t('oQueAtualizado')}
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
                {[
                  { label: t('kpiNovos'), value: ultimaExec.novos },
                  { label: t('kpiProcessados'), value: ultimaExec.processados },
                  { label: t('kpiItens'), value: ultimaExec.itens_coletados },
                  { label: t('kpiFornecedores'), value: ultimaExec.fornecedores },
                  { label: t('kpiEmpenhos'), value: ultimaExec.empenhos },
                  { label: t('kpiPulados'), value: ultimaExec.pulados },
                ].map((kpi) => {
                  const k = kpiBox('neutro')
                  return (
                    <div key={kpi.label} style={{ ...k.box, background: 'var(--branco)' }}>
                      <p style={k.label}>{kpi.label}</p>
                      <p style={k.valor}>{kpi.value}</p>
                    </div>
                  )
                })}
              </div>

              {/* Falhas */}
              <p style={{ ...rotulo, marginBottom: 8, textTransform: 'uppercase' }}>
                {t('falhasAtualizacao')}
              </p>
              {ultimaExec.erros === 0 && !ultimaExec.erro_resumo ? (
                <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, color: 'var(--ok)', margin: 0 }}>
                  <CircleCheck size={16} aria-hidden /> {t('nenhumaFalha')}
                </p>
              ) : (
                <div className="aviso-box erro">
                  <CircleX size={16} aria-hidden />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <p style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>
                      {ultimaExec.erros > 0
                        ? t(ultimaExec.erros === 1 ? 'falhaUma' : 'falhasVarias', { n: ultimaExec.erros })
                        : t('falhaExecucao')}
                    </p>
                    {ultimaExec.erro_resumo && (
                      <pre style={{ fontSize: 12, color: 'var(--texto)', margin: '8px 0 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', maxHeight: 160, overflow: 'auto' }}>
                        {ultimaExec.erro_resumo}
                      </pre>
                    )}
                    {ultimaExec.erro_detalhes && ultimaExec.erro_detalhes.length > 0 && (
                      <details style={{ marginTop: 8 }}>
                        <summary style={{ fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                          {t('verDetalhe', { n: ultimaExec.erro_detalhes.length })}
                        </summary>
                        <ul style={{ margin: '8px 0 0 0', paddingLeft: 18, fontSize: 13, color: 'var(--texto)', lineHeight: 1.6 }}>
                          {ultimaExec.erro_detalhes.map((d, idx) => (
                            <li key={idx}><strong>{d.processo}</strong>: {d.mensagem}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!COLETA_ENABLED && (
          <div className="aviso-box" style={{ marginTop: 16 }}>
            <Info size={16} aria-hidden />
            <span>{t('avisoLocal')}</span>
          </div>
        )}

        {error && (
          <div className="aviso-box erro" role="alert" style={{ marginTop: 16 }}>
            <CircleAlert size={16} aria-hidden />
            <span>{error}</span>
          </div>
        )}
      </div>
      )}

      {/* ─── SEÇÃO 2: Progresso em Tempo Real ─────────────────────────────── */}
      {loading && status && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 18, fontWeight: 700, color: 'var(--texto)', marginBottom: 16 }}>
            <Activity size={18} aria-hidden style={{ color: 'var(--verde)' }} /> {t('progressoTitulo')}
          </h3>

          {/* Barra de progresso estimada */}
          <div style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              {t('processando', { n: status.processados })}
            </p>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.min(status.processados, 100)}
              style={{
                background: 'var(--borda)',
                borderRadius: 'var(--raio-sm)',
                height: 24,
                overflow: 'hidden',
                position: 'relative'
              }}
            >
              <div style={{
                background: 'var(--verde)',
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
            {([
              { label: t('kpiProcessados'), value: status.processados, familia: 'ok' },
              { label: t('kpiNovos'), value: status.novos, familia: 'ok' },
              { label: t('kpiPulados'), value: status.pulados, familia: 'aviso' },
              { label: t('kpiErros'), value: status.erros, familia: 'erro' },
            ] as const).map(kpi => {
              const k = kpiBox(kpi.familia)
              return (
                <div key={kpi.label} style={{ ...k.box, padding: 12 }}>
                  <p style={{ ...k.label, fontSize: 12 }}>{kpi.label}</p>
                  <p style={k.valor}>{kpi.value}</p>
                </div>
              )
            })}
          </div>

          {/* Informações de Consulta ao Portal */}
          {status.consulta_portal && (
            <div style={{ marginTop: 20, padding: 16, background: 'var(--cinza-claro)', border: '1px solid var(--borda)', borderRadius: 'var(--raio-sm)' }}>
              <p style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 12, textTransform: 'uppercase' }}>
                <Info size={14} aria-hidden /> {t('consultaPortal')}
              </p>
              <div className="grid-2" style={{ gap: 12, fontSize: 13, lineHeight: 1.6, color: 'var(--texto)', fontFamily: 'monospace' }}>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t('lblUrl')}</p>
                  <p style={{ margin: '4px 0 0 0', wordBreak: 'break-all', fontSize: 12 }}>{status.consulta_portal.url}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t('lblOrgao')}</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.orgao}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t('lblDataInicial')}</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.dt_inicio}</p>
                </div>
                <div>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t('lblDataFinal')}</p>
                  <p style={{ margin: '4px 0 0 0' }}>{status.consulta_portal.dt_fim}</p>
                </div>
              </div>
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--borda)', fontSize: 12, color: 'var(--texto-suave)' }}>
                <p style={{ margin: 0 }}>{t('registrosPorPagina')} <strong>{status.consulta_portal.registros_por_pagina}</strong></p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── ABA 2: Agendamento ──────────────────────────────────────── */}
      {activeTab === 'agendamento' && (
      <div className="card" style={{ marginBottom: 24 }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 18, fontWeight: 700, color: 'var(--texto)', marginBottom: 20 }}>
          <CalendarClock size={18} aria-hidden style={{ color: 'var(--verde)' }} /> {t('agendamentoTitulo')}
        </h3>

        <p style={{ fontSize: 14, color: 'var(--texto-suave)', marginBottom: 16 }}>
          {t('agendamentoDesc')}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 24 }}>
          {/* Dia da Semana */}
          <div>
            <label htmlFor="coleta-dia" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              {t('lblDiaSemana')}
            </label>
            <select
              id="coleta-dia"
              value={config.dia_semana}
              onChange={(e) => setConfig({ ...config, dia_semana: parseInt(e.target.value) })}
              style={campo}
            >
              {diasSemana.map((dia, idx) => (
                <option key={idx} value={idx}>{dia}</option>
              ))}
            </select>
          </div>

          {/* Hora */}
          <div>
            <label htmlFor="coleta-hora" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              {t('lblHora')}
            </label>
            <input
              id="coleta-hora"
              type="number"
              min="0"
              max="23"
              value={config.hora}
              onChange={(e) => setConfig({ ...config, hora: parseInt(e.target.value) || 0 })}
              style={campo}
            />
          </div>

          {/* Minuto */}
          <div>
            <label htmlFor="coleta-minuto" style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--texto-suave)', marginBottom: 8 }}>
              {t('lblMinuto')}
            </label>
            <input
              id="coleta-minuto"
              type="number"
              min="0"
              max="59"
              value={config.minuto}
              onChange={(e) => setConfig({ ...config, minuto: parseInt(e.target.value) || 0 })}
              style={campo}
            />
          </div>
        </div>

        {/* Preview */}
        <div className="aviso-box ok" style={{ marginBottom: 24 }}>
          <Calendar size={16} aria-hidden />
          <span style={{ fontWeight: 600 }}>
            {t('agendadaPara')} <strong>{t('diaAs', { dia: diasSemana[config.dia_semana], hora: horaMinuto })}</strong>
          </span>
        </div>

        {/* Botão Salvar */}
        <button className="btn btn-primario" onClick={salvarConfig} disabled={savingConfig}>
          {savingConfig
            ? <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('salvando')}</>
            : <><Save size={16} aria-hidden /> {t('salvarConfig')}</>}
        </button>

        {error && (
          <div className="aviso-box erro" role="alert" style={{ marginTop: 16 }}>
            <CircleAlert size={16} aria-hidden />
            <span>{error}</span>
          </div>
        )}
      </div>
      )}

      {/* ─── SEÇÃO 3: Estatísticas de Classificação ──────────────────────── */}
      <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(250px, 100%), 1fr))' }}>
        <div className="metric-card verde">
          <div className="metric-label">{t('totalLicitacoes')}</div>
          <div className="metric-value">{stats?.total_licitacoes || '—'}</div>
          <div className="metric-sub">
            {stats ? t('agricolasPct', { n: stats.total_agricolas, pct: stats.cobertura_agricola_pct }) : '—'}
          </div>
        </div>

        <div className="metric-card ceu">
          <div className="metric-label">{t('totalItens')}</div>
          <div className="metric-value">{stats?.total_itens || '—'}</div>
          <div className="metric-sub">{t('itensAgricolas')}</div>
        </div>

        <div className="metric-card terra">
          <div className="metric-label">{t('coberturaAgricola')}</div>
          <div className="metric-value">{stats?.cobertura_agricola_pct || '—'}%</div>
          <div className="metric-sub">{t('doTotalLicitacoes')}</div>
        </div>
      </div>

      {/* Gráficos */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(400px, 100%), 1fr))', gap: 20, marginBottom: 4 }}>
        {/* Pie: Agrícola vs Não-Agrícola */}
        {stats && piechartData.length > 0 && (
          <div className="chart-card" style={{ margin: 0 }}>
            <h3>{t('graficoAgroVsNao')}</h3>
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

        {/* Bar: Itens por Categoria (série única → uma cor; categorias no eixo) */}
        {stats && categoriasData.length > 0 && (
          <div className="chart-card" style={{ margin: 0 }}>
            <h3>{t('top10Categorias')}</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={categoriasData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grade)" />
                <XAxis dataKey="categoria" angle={-45} textAnchor="end" height={100} tick={{ fontSize: 12, fill: 'var(--chart-eixo)' }} />
                <YAxis tick={{ fontSize: 12, fill: 'var(--chart-eixo)' }} />
                <Tooltip />
                <Bar dataKey="quantidade" name={t('serieQuantidade')} fill="var(--chart-marca)" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Bar: Licitações Agrícolas por Ano */}
      {stats && anosData.length > 0 && (
        <div className="chart-card" style={{ marginTop: 20 }}>
          <h3>{t('licitacoesPorAno')}</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={anosData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grade)" />
              <XAxis dataKey="ano" tick={{ fontSize: 12, fill: 'var(--chart-eixo)' }} />
              <YAxis tick={{ fontSize: 12, fill: 'var(--chart-eixo)' }} />
              <Tooltip />
              <Bar dataKey="licitacoes" name={t('serieLicitacoes')} fill="var(--chart-marca)" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
