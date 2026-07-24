import type {
  UploadResponse,
  ImportStatusResponse,
  AskResponse,
  HistoryResponse,
  HealthResponse,
  SSEDeltaData,
  SSEFinalData,
  SSEErrorData,
  SSEThinkingData,
  DocumentListResponse,
  ChunkListResponse,
} from '@/types'

const API_BASE = '/api'

// ==================== 导入 API ====================

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch(`${API_BASE}/import/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!resp.ok) throw new Error(`上传失败: ${resp.status}`)
  return resp.json()
}

export async function getImportStatus(taskId: string): Promise<ImportStatusResponse> {
  const resp = await fetch(`${API_BASE}/import/status/${taskId}`)
  if (!resp.ok) throw new Error(`查询状态失败: ${resp.status}`)
  return resp.json()
}

// ==================== 查询 API ====================

export async function ask(query: string, sessionId = ''): Promise<AskResponse> {
  const resp = await fetch(`${API_BASE}/query/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, session_id: sessionId }),
  })
  if (!resp.ok) throw new Error(`查询失败: ${resp.status}`)
  return resp.json()
}

export async function getHistory(sessionId: string): Promise<HistoryResponse> {
  const resp = await fetch(`${API_BASE}/query/history/${sessionId}`)
  if (!resp.ok) throw new Error(`获取历史失败: ${resp.status}`)
  return resp.json()
}

export async function clearHistory(sessionId: string): Promise<{ session_id: string; deleted: number }> {
  const resp = await fetch(`${API_BASE}/query/history/${sessionId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`清空历史失败: ${resp.status}`)
  return resp.json()
}

export async function healthCheck(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE}/query/health`)
  if (!resp.ok) throw new Error(`健康检查失败: ${resp.status}`)
  return resp.json()
}

// ==================== 文档预览 API ====================

export async function getDocumentList(): Promise<DocumentListResponse> {
  const resp = await fetch(`${API_BASE}/documents/list`)
  if (!resp.ok) throw new Error(`获取文档列表失败: ${resp.status}`)
  return resp.json()
}

export async function getDocumentChunks(fileTitle: string): Promise<ChunkListResponse> {
  const resp = await fetch(`${API_BASE}/documents/chunks/${encodeURIComponent(fileTitle)}`)
  if (!resp.ok) throw new Error(`获取切分详情失败: ${resp.status}`)
  return resp.json()
}

// ==================== SSE 流式监听 ====================

export interface SSEHandlers {
  onReady?: () => void
  onThinking?: (data: SSEThinkingData) => void
  onDelta?: (data: SSEDeltaData) => void
  onFinal?: (data: SSEFinalData) => void
  onError?: (data: SSEErrorData) => void
}

export function listenStream(taskId: string, handlers: SSEHandlers): EventSource {
  const es = new EventSource(`${API_BASE}/query/stream/${taskId}`)

  es.addEventListener('ready', () => {
    handlers.onReady?.()
  })

  es.addEventListener('thinking', (e) => {
    const data: SSEThinkingData = JSON.parse(e.data)
    handlers.onThinking?.(data)
  })

  es.addEventListener('delta', (e) => {
    const data: SSEDeltaData = JSON.parse(e.data)
    handlers.onDelta?.(data)
  })

  es.addEventListener('final', (e) => {
    const data: SSEFinalData = JSON.parse(e.data)
    handlers.onFinal?.(data)
    es.close()
  })

  es.addEventListener('error', () => {
    if (es.readyState === EventSource.CLOSED) {
      handlers.onError?.({ message: '连接已关闭' })
    } else {
      handlers.onError?.({ message: 'SSE 连接错误' })
    }
    es.close()
  })

  return es
}
