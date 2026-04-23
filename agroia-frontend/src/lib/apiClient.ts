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

export async function* streamChat(request: ChatRequest): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    throw new Error(`Stream error: ${response.statusText}`)
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
          yield JSON.parse(json) as SSEEvent
        } catch (e) {
          console.error('Failed to parse SSE event:', json, e)
        }
      }
    }
  }
}
