import { useState, useEffect, useCallback } from 'react'
import {
  FileText, ChevronLeft, Hash, Tag, Layers, RefreshCw, Loader2, FileStack, AlertCircle,
} from 'lucide-react'
import { getDocumentList, getDocumentChunks } from '@/api/client'
import type { DocumentItem, ChunkItem } from '@/types'

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null)
  const [chunks, setChunks] = useState<ChunkItem[]>([])
  const [chunksLoading, setChunksLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchDocuments = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getDocumentList()
      setDocuments(data.documents || [])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const viewChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc)
    setChunksLoading(true)
    setChunks([])
    try {
      const data = await getDocumentChunks(doc.file_title)
      setChunks(data.chunks || [])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setChunksLoading(false)
    }
  }

  const backToList = () => {
    setSelectedDoc(null)
    setChunks([])
  }

  // 切分详情视图
  if (selectedDoc) {
    return (
      <div className="p-8 space-y-4">
        {/* 返回按钮 */}
        <button
          onClick={backToList}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-indigo-600 border border-gray-200 hover:border-indigo-300 rounded-lg transition-colors"
        >
          <ChevronLeft size={16} /> 返回文档列表
        </button>

        {/* 文档信息卡片 */}
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <FileText size={24} />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-gray-800 break-all">{selectedDoc.file_title}</h2>
              <div className="flex items-center gap-4 mt-2 text-sm">
                <span className="inline-flex items-center gap-1 text-gray-500">
                  <Hash size={14} /> {selectedDoc.chunk_count} 个切片
                </span>
                <span className="inline-flex items-center gap-1 text-gray-500">
                  <Tag size={14} /> {selectedDoc.item_name || '未识别'}
                </span>
                <span className="inline-flex items-center gap-1 text-gray-500">
                  <Layers size={14} /> {selectedDoc.titles.length} 个章节
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 切片列表 */}
        {chunksLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={32} className="animate-spin text-indigo-400" />
            <span className="ml-3 text-gray-400">加载切分详情...</span>
          </div>
        ) : chunks.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 border border-gray-100 text-center text-gray-400">
            暂无切片数据
          </div>
        ) : (
          <div className="space-y-3">
            {chunks.map((chunk, i) => (
              <div key={`${chunk.file_title}_${chunk.part}_${i}`} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                {/* 切片头部 */}
                <div className="px-5 py-3 bg-gray-50/80 border-b border-gray-100 flex items-center gap-3">
                  <span className="w-7 h-7 bg-indigo-500 text-white rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-700 truncate">
                      {chunk.title || '无标题'}
                    </div>
                    {chunk.parent_title && chunk.parent_title !== chunk.title && (
                      <div className="text-xs text-gray-400 truncate">
                        父章节: {chunk.parent_title}
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 px-2 py-0.5 bg-gray-100 rounded">
                    Part {chunk.part}
                  </span>
                </div>
                {/* 切片内容 */}
                <div className="px-5 py-4">
                  <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-6">
                    {chunk.content}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // 文档列表视图
  return (
    <div className="p-8 space-y-6">
      {/* 标题栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">文档管理</h2>
          <p className="text-sm text-gray-400 mt-0.5">查看所有已导入知识库的文档及其切分情况</p>
        </div>
        <button
          onClick={fetchDocuments}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-indigo-600 border border-gray-200 hover:border-indigo-300 rounded-lg transition-colors disabled:opacity-40"
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          刷新
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 text-red-600 rounded-lg text-sm">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* 加载中 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-indigo-400" />
          <span className="ml-3 text-gray-400">加载文档列表...</span>
        </div>
      ) : documents.length === 0 ? (
        /* 空状态 */
        <div className="bg-white rounded-xl shadow-sm p-12 border border-gray-100 text-center">
          <div className="w-16 h-16 bg-gray-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <FileStack size={32} className="text-gray-300" />
          </div>
          <h3 className="text-base font-medium text-gray-600 mb-1">暂无已导入的文档</h3>
          <p className="text-sm text-gray-400">请先前往「知识库导入」页面上传文档</p>
        </div>
      ) : (
        /* 文档卡片列表 */
        <div className="grid grid-cols-2 gap-5">
          {documents.map(doc => (
            <div
              key={doc.file_title}
              onClick={() => viewChunks(doc)}
              className="bg-white rounded-xl shadow-sm p-5 border border-gray-100 hover:border-indigo-300 hover:shadow-md cursor-pointer transition-all"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-indigo-50 text-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
                  <FileText size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-gray-800 line-clamp-2 break-all">
                    {doc.file_title}
                  </h3>
                  <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                    <span className="inline-flex items-center gap-1">
                      <Hash size={12} /> {doc.chunk_count} 切片
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Tag size={12} /> {doc.item_name || '未识别'}
                    </span>
                  </div>
                </div>
              </div>
              {/* 章节标签 */}
              {doc.titles.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-50 flex flex-wrap gap-1.5">
                  {doc.titles.slice(0, 4).map((t, i) => (
                    <span key={`title_${i}`} className="text-xs px-2 py-0.5 bg-gray-50 text-gray-500 rounded line-clamp-1 max-w-[200px]">
                      {t.replace(/^#+\s*/, '')}
                    </span>
                  ))}
                  {doc.titles.length > 4 && (
                    <span className="text-xs px-2 py-0.5 text-gray-400">
                      +{doc.titles.length - 4}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
