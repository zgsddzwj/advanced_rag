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
  RetrievalOptions,
  SystemHealth,
} from '@/types'

const API_BASE = '/api'

// 默认请求超时；上传大文件放宽
const DEFAULT_TIMEOUT_MS = 30_000
const UPLOAD_TIMEOUT_MS = 120_000

// ==================== 统一响应信封（演进2） ====================

export interface ApiEnvelope<T> {
  code: string
  message: string
  data: T
}

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}

/**
 * 请求后端并解包统一响应信封 {code, message, data}
 * - 超时（AbortController）或网络中断：抛出 TIMEOUT 类 ApiError
 * - 非 2xx 或 code !== 'OK'：抛出携带后端真实错误消息的 ApiError
 * - 成功：直接返回 data（页面代码无需感知信封结构）
 */
async function request<T>(path: string, init?: RequestInit, timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const resp = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal })
    let body: ApiEnvelope<T>
    try {
      body = await resp.json()
    } catch (e) {
      if (isAbortError(e)) throw e
      throw new ApiError('BAD_RESPONSE', `响应解析失败: ${resp.status}`, resp.status)
    }
    if (!resp.ok || body.code !== 'OK') {
      throw new ApiError(body.code ?? 'HTTP_ERROR', body.message ?? `请求失败: ${resp.status}`, resp.status)
    }
    return body.data
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (isAbortError(e)) {
      throw new ApiError('TIMEOUT', `请求超时（${Math.round(timeoutMs / 1000)}s），请稍后重试`, 408)
    }
    throw e
  } finally {
    clearTimeout(timer)
  }
}

// ==================== 导入 API ====================

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  return request<UploadResponse>('/import/upload', {
    method: 'POST',
    body: formData,
  }, UPLOAD_TIMEOUT_MS)
}

export async function getImportStatus(taskId: string): Promise<ImportStatusResponse> {
  return request<ImportStatusResponse>(`/import/status/${taskId}`)
}

// ==================== 查询 API ====================

export async function ask(query: string, sessionId = '', retrieval?: RetrievalOptions): Promise<AskResponse> {
  const body: Record<string, unknown> = { query, session_id: sessionId }
  if (retrieval && Object.values(retrieval).some(v => v !== undefined)) {
    body.retrieval = retrieval
  }
  return request<AskResponse>('/query/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function getHistory(sessionId: string): Promise<HistoryResponse> {
  return request<HistoryResponse>(`/query/history/${sessionId}`)
}

export async function clearHistory(sessionId: string): Promise<{ session_id: string; deleted: number }> {
  return request<{ session_id: string; deleted: number }>(`/query/history/${sessionId}`, { method: 'DELETE' })
}

export async function healthCheck(): Promise<HealthResponse> {
  return request<HealthResponse>('/query/health')
}

/**
 * 全链路健康聚合：并发探活 Mongo/Milvus/MinIO/Kafka，
 * status 为 ok（全部可达）或 degraded（部分依赖异常）
 */
export async function getSystemHealth(): Promise<SystemHealth> {
  return request<SystemHealth>('/api/health')
}

// ==================== 文档预览 API ====================

export async function getDocumentList(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/documents/list')
}

export async function getDocumentChunks(fileTitle: string): Promise<ChunkListResponse> {
  return request<ChunkListResponse>(`/documents/chunks/${encodeURIComponent(fileTitle)}`)
}

// ==================== SSE 流式监听 ====================

export interface SSEHandlers {
  onReady?: () => void
  onThinking?: (data: SSEThinkingData) => void
  onProgress?: (data: { done_list: string[]; running_list: string[] }) => void
  onDelta?: (data: SSEDeltaData) => void
  onFinal?: (data: SSEFinalData) => void
  onError?: (data: SSEErrorData) => void
}

export function listenStream(taskId: string, handlers: SSEHandlers): EventSource {
  const url = `${API_BASE}/query/stream/${taskId}`
  let es: EventSource
  let reconnectAttempts = 0
  const MAX_RECONNECT = 3
  let reconnectDelay = 1000
  let closed = false

  const connect = () => {
    es = new EventSource(url)

    es.addEventListener('ready', () => {
      reconnectAttempts = 0
      reconnectDelay = 1000
      handlers.onReady?.()
    })

    es.addEventListener('thinking', (e) => {
      const data: SSEThinkingData = JSON.parse(e.data)
      handlers.onThinking?.(data)
    })

    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data)
      handlers.onProgress?.(data)
    })

    es.addEventListener('delta', (e) => {
      const data: SSEDeltaData = JSON.parse(e.data)
      handlers.onDelta?.(data)
    })

    es.addEventListener('final', (e) => {
      const data: SSEFinalData = JSON.parse(e.data)
      handlers.onFinal?.(data)
      closed = true
      es.close()
    })

    es.addEventListener('error', () => {
      if (es.readyState === EventSource.CLOSED) {
        if (!closed && reconnectAttempts < MAX_RECONNECT) {
          reconnectAttempts += 1
          setTimeout(() => {
            if (!closed) connect()
          }, reconnectDelay)
          reconnectDelay = Math.min(reconnectDelay * 2, 5000)
        } else {
          handlers.onError?.({ message: '连接已关闭' })
          closed = true
        }
      } else {
        handlers.onError?.({ message: 'SSE 连接错误' })
      }
      if (closed) es.close()
    })
  }

  connect()

  // 返回一个可控制的 EventSource-like 对象
  return {
    close: () => {
      closed = true
      es?.close()
    },
    readyState: EventSource.CLOSED,
  } as EventSource
}
