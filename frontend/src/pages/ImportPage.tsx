import { useState, useRef, useCallback } from 'react'
import {
  DoorOpen, FileText, Image as ImageIcon, Scissors, Tag, Hash, Database,
  Upload, CheckCircle2, Loader2, XCircle, FileUp, RefreshCw,
  type LucideIcon,
} from 'lucide-react'
import { uploadFile, getImportStatus } from '@/api/client'
import { IMPORT_NODES, POLL_INTERVAL, type ImportStatusResponse } from '@/types'

const iconMap: Record<string, LucideIcon> = {
  DoorOpen, FileText, ImageIcon, Scissors, Tag, Hash, Database,
}

type NodeStatus = 'pending' | 'running' | 'done' | 'failed'

export default function ImportPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [taskId, setTaskId] = useState<string>('')
  const [status, setStatus] = useState<ImportStatusResponse | null>(null)
  const [resultBanner, setResultBanner] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const handleFileSelect = useCallback((file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'md'].includes(ext || '')) {
      alert('仅支持 PDF 或 Markdown 文件')
      return
    }
    setSelectedFile(file)
    setResultBanner(null)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0])
  }, [handleFileSelect])

  const getNodeStatus = (nodeId: string): NodeStatus => {
    if (!status) return 'pending'
    if (status.done_list.includes(nodeId)) return 'done'
    if (status.running_list.includes(nodeId)) return 'running'
    if (status.status === 'failed') return 'failed'
    return 'pending'
  }

  const completedCount = status?.done_list.length || 0
  const percent = Math.round((completedCount / IMPORT_NODES.length) * 100)

  const startImport = async () => {
    if (!selectedFile) return
    setUploading(true)
    setResultBanner(null)
    try {
      const data = await uploadFile(selectedFile)
      setTaskId(data.task_id)
      setStatus({ task_id: data.task_id, status: 'processing', done_list: [], running_list: [] })
      pollRef.current = setInterval(async () => {
        try {
          const s = await getImportStatus(data.task_id)
          setStatus(s)
          if (s.status === 'completed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setResultBanner({ type: 'success', msg: `导入完成！文件 "${selectedFile.name}" 已成功写入知识库。` })
          } else if (s.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current)
            setResultBanner({ type: 'error', msg: '导入失败，请检查日志或重试。' })
          }
        } catch (e) {
          console.error('轮询失败:', e)
        }
      }, POLL_INTERVAL)
    } catch (e) {
      setResultBanner({ type: 'error', msg: `上传失败: ${(e as Error).message}` })
    } finally {
      setUploading(false)
    }
  }

  const resetAll = () => {
    setSelectedFile(null)
    setTaskId('')
    setStatus(null)
    setResultBanner(null)
    if (pollRef.current) clearInterval(pollRef.current)
  }

  return (
    <div className="p-8 space-y-6">
      {/* 上传卡片 */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-base font-semibold mb-4 text-gray-800">上传文档</h3>

        {/* 拖拽区域 */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
            dragOver ? 'border-indigo-400 bg-indigo-50/50' : 'border-gray-200 hover:border-indigo-300 bg-gray-50/50'
          }`}
        >
          <FileUp size={48} className="mx-auto text-gray-300 mb-3" />
          <div className="text-gray-700 font-medium">点击或拖拽文件到此处上传</div>
          <div className="text-sm text-gray-400 mt-1">支持 PDF / Markdown 格式</div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.md"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
          />
        </div>

        {/* 已选文件 */}
        {selectedFile && (
          <div className="mt-4 flex items-center gap-3 p-4 bg-blue-50/50 border border-blue-100 rounded-lg">
            <span className="text-2xl">{selectedFile.name.endsWith('.pdf') ? '📕' : '📝'}</span>
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-800">{selectedFile.name}</div>
              <div className="text-xs text-gray-400">
                {selectedFile.size > 1024 * 1024
                  ? (selectedFile.size / 1024 / 1024).toFixed(1) + ' MB'
                  : (selectedFile.size / 1024).toFixed(0) + ' KB'}
              </div>
            </div>
            {!taskId && (
              <button onClick={() => setSelectedFile(null)} className="text-gray-300 hover:text-red-400 p-1">
                <XCircle size={18} />
              </button>
            )}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 mt-5">
          <button
            onClick={startImport}
            disabled={!selectedFile || uploading || !!taskId}
            className="inline-flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? '导入中...' : '开始导入'}
          </button>
          {taskId && (
            <button
              onClick={resetAll}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:border-indigo-300 hover:text-indigo-600"
            >
              <RefreshCw size={16} /> 重新导入
            </button>
          )}
        </div>
      </div>

      {/* 导入进度 */}
      {status && (
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-gray-800">导入进度</h3>
            <span className="text-sm font-semibold text-indigo-600">{percent}%</span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden mb-6">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-500" style={{ width: `${percent}%` }} />
          </div>

          <div className="space-y-1">
            {IMPORT_NODES.map(node => {
              const nodeStatus = getNodeStatus(node.id)
              const Icon = iconMap[node.icon] || FileText
              return (
                <div
                  key={node.id}
                  className={`flex items-center gap-4 px-4 py-3 rounded-lg transition-colors ${
                    nodeStatus === 'running' ? 'bg-amber-50' :
                    nodeStatus === 'done' ? 'bg-green-50' :
                    nodeStatus === 'failed' ? 'bg-red-50' : ''
                  }`}
                >
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-sm flex-shrink-0 ${
                    nodeStatus === 'pending' ? 'bg-gray-100 text-gray-400' :
                    nodeStatus === 'running' ? 'bg-amber-100 text-amber-600' :
                    nodeStatus === 'done' ? 'bg-green-100 text-green-600' :
                    'bg-red-100 text-red-400'
                  }`}>
                    <Icon size={16} />
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">{node.label}</div>
                    <div className="text-xs text-gray-400 font-mono">{node.id}</div>
                  </div>
                  <div className="flex items-center gap-1.5 text-sm font-medium">
                    {nodeStatus === 'pending' && <span className="text-gray-400">⏳ 等待中</span>}
                    {nodeStatus === 'running' && <Loader2 size={14} className="text-amber-500 animate-spin" />}
                    {nodeStatus === 'running' && <span className="text-amber-600">执行中</span>}
                    {nodeStatus === 'done' && <CheckCircle2 size={16} className="text-green-500" />}
                    {nodeStatus === 'done' && <span className="text-green-600">已完成</span>}
                    {nodeStatus === 'failed' && <span className="text-red-400">⏭️ 跳过</span>}
                  </div>
                </div>
              )
            })}
          </div>

          {resultBanner && (
            <div className={`mt-5 px-4 py-3 rounded-lg text-sm font-medium ${
              resultBanner.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {resultBanner.msg}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
