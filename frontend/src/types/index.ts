// ==================== 导入流程 ====================

export interface ImportNode {
  id: string
  label: string
  icon: string
}

export interface ImportStatusResponse {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  done_list: string[]
  running_list: string[]
}

export interface UploadResponse {
  task_id: string
  filename: string
  status: string
}

// ==================== 查询流程 ====================

export interface AskResponse {
  session_id: string
  task_id: string
  status: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  rewritten_query?: string
  item_names?: string[]
  image_urls?: string[]
  ts?: number
}

export interface HistoryResponse {
  session_id: string
  messages: ChatMessage[]
}

// SSE 事件数据
export interface SSEDeltaData {
  text: string
}

export interface SSEFinalData {
  answer: string
  image_urls?: string[]
  item_names?: string[]
}

export interface SSEErrorData {
  message: string
}

export interface HealthResponse {
  status: string
  service: string
}

// ==================== 常量 ====================

export const IMPORT_NODES: ImportNode[] = [
  { id: 'node_entry', label: '入口判断', icon: 'DoorOpen' },
  { id: 'node_pdf_to_md', label: 'PDF转Markdown', icon: 'FileText' },
  { id: 'node_md_img', label: '图片处理', icon: 'Image' },
  { id: 'node_document_split', label: '文档切分', icon: 'Scissors' },
  { id: 'node_item_name_recognition', label: '商品名识别', icon: 'Tag' },
  { id: 'node_bge_embedding', label: '向量化', icon: 'Hash' },
  { id: 'node_import_milvus', label: '入库Milvus', icon: 'Database' },
]

export const POLL_INTERVAL = 2000
