import axios from 'axios'
import type { AxiosInstance } from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_API_SECRET_KEY || 'LP6xuqjxv0_vKeGvpakYF7Avba8h6qQDACcml0GuUnY'

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
})

export interface SSEEvent {
  tipo: 'status' | 'token' | 'fim'
  msg?: string
  texto?: string
  tools_usadas?: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  tools_usadas?: string[]
}

export interface ChatRequest {
  pergunta: string
  session_id?: string
  historico?: ChatMessage[]
}

export interface ChatResponse {
  resposta: string
  tools_usadas: string[]
  session_id: string
}

export async function sendChat(request: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/chat', request)
  return response.data
}

export async function loadConversationHistory(sessionId: string): Promise<ChatMessage[]> {
  const response = await apiClient.get<ChatMessage[]>(`/conversas/${sessionId}`)
  return response.data
}

export async function deleteConversation(sessionId: string): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/conversas/${sessionId}`)
  return response.data
}

export async function healthCheck(): Promise<{ status: string }> {
  const response = await apiClient.get<{ status: string }>('/health')
  return response.data
}

export interface UploadOfertasResult {
  total: number
  inseridas: number
  erros: { linha: number; motivo: string }[]
}

export async function uploadOfertasPlanilha(file: File): Promise<UploadOfertasResult> {
  const form = new FormData()
  form.append('arquivo', file)
  const response = await apiClient.post<UploadOfertasResult>('/produtor/ofertas/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

// ─── Coleta (Atualização de Dados) ──────────────────────────────────────────
// Usam o apiClient compartilhado (injeta X-API-Key e baseURL corretos),
// evitando o drift de nome de env var (VITE_API_KEY vs VITE_API_SECRET_KEY).

export interface ConfigAgendamento {
  dia_semana: number
  hora: number
  minuto: number
}

export async function iniciarColeta(): Promise<any> {
  const response = await apiClient.post('/coleta/iniciar', {})
  return response.data
}

export async function cancelarColeta(): Promise<any> {
  const response = await apiClient.post('/coleta/cancelar', {})
  return response.data
}

export async function salvarConfigColeta(config: ConfigAgendamento): Promise<any> {
  const response = await apiClient.post('/coleta/config', config)
  return response.data
}

export async function* streamPost<T = any>(endpoint: string, body?: any): AsyncGenerator<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    // Em HTTP/2 statusText é sempre vazio — incluir o código garante mensagem útil.
    const detalhe = response.statusText ? `: ${response.statusText}` : ''
    throw new Error(`Stream error ${response.status}${detalhe}`)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const json = line.slice(6)
        if (json === '[DONE]') return
        try {
          yield JSON.parse(json) as T
        } catch (e) {
          console.error('Failed to parse SSE event:', json, e)
        }
      }
    }
  }
}

export async function* streamChat(request: ChatRequest): AsyncGenerator<SSEEvent> {
  yield* streamPost<SSEEvent>('/chat/stream', request)
}

// ─── Switch de motor LLM + comparador ao vivo ───────────────────────────────
export interface MotorInfo {
  motor: string
  rotulo: string
  disponivel: boolean
  baseline: boolean
}

export interface ConfigMotor {
  motor_ativo: string
  motores: MotorInfo[]
}

export interface ComparadorEvent {
  tipo: 'inicio' | 'motor'
  motores?: string[]
  pergunta?: string
  motor?: string
  rotulo?: string
  resposta?: string
  latencia_ms?: number
  tokens_entrada?: number
  tokens_saida?: number
  custo_usd?: number
  tools_usadas?: string[]
  iteracoes?: number
  erro?: string | null
}

export async function getConfigMotor(): Promise<ConfigMotor> {
  const r = await apiClient.get<ConfigMotor>('/config/motor')
  return r.data
}

export async function setMotorAtivo(motor: string): Promise<ConfigMotor> {
  const r = await apiClient.post<ConfigMotor>('/config/motor', { motor })
  return r.data
}

export async function* compararMotores(pergunta: string, motores: string[]): AsyncGenerator<ComparadorEvent> {
  yield* streamPost<ComparadorEvent>('/benchmark/comparar/stream', { pergunta, motores })
}
