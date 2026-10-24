import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, ChevronLeft, Hash, Tag, Layers, RefreshCw, Loader2, FileStack,
  AlertCircle, Search, ArrowRight, RotateCcw,
} from 'lucide-react'
import { getDocumentList, getDocumentChunks } from '@/api/client'
import type { DocumentItem, ChunkItem } from '@/types'

/* 列表骨架屏 */
function ListSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 animate-pulse" aria-busy="true" aria-label="文档列表加载中">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="surface rounded-xl p-5">
          <div className="flex gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-200 dark:bg-slate-700" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-slate-700" />
              <div className="h-3 w-1/2 rounded bg-gray-100 dark:bg-slate-800" />
            </div>
          </div>
          <div className="mt-4 flex gap-1.5">
            <div className="h-5 w-24 rounded bg-gray-100 dark:bg-slate-800" />
            <div className="h-5 w-16 rounded bg-gray-100 dark:bg-slate-800" />
          </div>
        </div>
      ))}
    </div>
  )
}

/* 切片骨架屏 */
function ChunksSkeleton() {
  return (
    <div className="space-y-3 animate-pulse" aria-busy="true" aria-label="切片加载中">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="surface rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 dark:border-slate-800 flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gray-200 dark:bg-slate-700" />
            <div className="h-3.5 w-2/5 rounded bg-gray-200 dark:bg-slate-700" />
          </div>
          <div className="px-5 py-4 space-y-2">
            <div className="h-3 w-full rounded bg-gray-100 dark:bg-slate-800" />
            <div className="h-3 w-11/12 rounded bg-gray-100 dark:bg-slate-800" />
            <div className="h-3 w-4/5 rounded bg-gray-100 dark:bg-slate-800" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function DocumentsPage() {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null)
  const [chunks, setChunks] = useState<ChunkItem[]>([])
  const [chunksLoading, setChunksLoading] = useState(false)
  const [error, setError] = useState('')
  // 列表搜索（标题/主题/章节）与切片内容搜索
  const [listQuery, setListQuery] = useState('')
  const [chunkQuery, setChunkQuery] = useState('')

  const fetchDocuments = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getDocumentList()
      // Milvus 返回顺序不稳定，按标题排序保证刷新时列表不跳动
      const docs = [...(data.documents || [])].sort((a, b) =>
        a.file_title.localeCompare(b.file_title, 'zh-Hans-CN'),
      )
      setDocuments(docs)
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
    setChunkQuery('')
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
    setChunkQuery('')
    setError('')
  }

  // 列表过滤：标题 / 主题 / 章节标题 任意命中
  const filteredDocuments = useMemo(() => {
    const q = listQuery.trim().toLowerCase()
    if (!q) return documents
    return documents.filter(
      doc =>
        doc.file_title.toLowerCase().includes(q) ||
        (doc.item_name || '').toLowerCase().includes(q) ||
        doc.titles.some(t => t.toLowerCase().includes(q)),
    )
  }, [documents, listQuery])

  // 切片过滤：标题 / 父章节 / 内容 任意命中
  const filteredChunks = useMemo(() => {
    const q = chunkQuery.trim().toLowerCase()
    if (!q) return chunks
    return chunks.filter(
      chunk =>
        (chunk.title || '').toLowerCase().includes(q) ||
        (chunk.parent_title || '').toLowerCase().includes(q) ||
        (chunk.content || '').toLowerCase().includes(q),
    )
  }, [chunks, chunkQuery])

  // 切分详情视图
  if (selectedDoc) {
    return (
      <div className="p-4 md:p-8 space-y-4">
        {/* 返回按钮 */}
        <button
          onClick={backToList}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 border border-gray-200 dark:border-slate-700 hover:border-indigo-300 rounded-lg transition-colors"
        >
          <ChevronLeft size={16} /> 返回文档列表
        </button>

        {/* 文档信息卡片 */}
        <div className="surface rounded-xl shadow-sm p-6 transition-colors">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 rounded-xl flex items-center justify-center flex-shrink-0">
              <FileText size={24} />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-gray-800 dark:text-slate-100 break-all">{selectedDoc.file_title}</h2>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-sm text-gray-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-1">
                  <Hash size={14} /> {selectedDoc.chunk_count} 个切片
                </span>
                <span className="inline-flex items-center gap-1">
                  <Tag size={14} /> {selectedDoc.item_name || '未识别'}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Layers size={14} /> {selectedDoc.titles.length} 个章节
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 切片搜索 */}
        {!chunksLoading && chunks.length > 0 && (
          <div className="relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={chunkQuery}
              onChange={e => setChunkQuery(e.target.value)}
              placeholder="搜索切片标题或内容…"
              aria-label="搜索切片"
              className="w-full pl-10 pr-4 py-2.5 surface rounded-lg text-sm text-gray-700 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-500/20 transition-colors"
            />
          </div>
        )}

        {/* 切片列表 */}
        {chunksLoading ? (
          <ChunksSkeleton />
        ) : chunks.length === 0 ? (
          <div className="surface rounded-xl p-12 text-center text-gray-400 dark:text-slate-500">
            暂无切片数据
          </div>
        ) : filteredChunks.length === 0 ? (
          <div className="surface rounded-xl p-12 text-center text-gray-400 dark:text-slate-500">
            没有匹配「{chunkQuery}」的切片
          </div>
        ) : (
          <>
            {chunkQuery && (
              <div className="text-xs text-gray-400 dark:text-slate-500">
                匹配 {filteredChunks.length} / {chunks.length} 个切片
              </div>
            )}
            <div className="space-y-3">
              {filteredChunks.map((chunk) => {
                const idx = chunks.indexOf(chunk) + 1
                return (
                  <div key={`${chunk.file_title}_${chunk.part}_${idx}`} className="surface rounded-xl shadow-sm overflow-hidden transition-colors">
                    {/* 切片头部 */}
                    <div className="px-5 py-3 bg-gray-50/80 dark:bg-slate-800/60 border-b border-gray-100 dark:border-slate-800 flex items-center gap-3">
                      <span className="w-7 h-7 bg-indigo-500 text-white rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0">
                        {idx}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-700 dark:text-slate-200 truncate">
                          {chunk.title || '无标题'}
                        </div>
                        {chunk.parent_title && chunk.parent_title !== chunk.title && (
                          <div className="text-xs text-gray-400 dark:text-slate-500 truncate">
                            父章节: {chunk.parent_title}
                          </div>
                        )}
                      </div>
                      <span className="text-xs text-gray-400 dark:text-slate-500 px-2 py-0.5 bg-gray-100 dark:bg-slate-800 rounded">
                        Part {chunk.part}
                      </span>
                    </div>
                    {/* 切片内容 */}
                    <div className="px-5 py-4">
                      <p className="text-sm text-gray-600 dark:text-slate-300 leading-relaxed whitespace-pre-wrap line-clamp-6">
                        {chunk.content}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    )
  }

  // 文档列表视图
  return (
    <div className="p-4 md:p-8 space-y-6">
      {/* 标题栏 */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-slate-100">文档管理</h2>
          <p className="text-sm text-gray-400 dark:text-slate-500 mt-0.5">查看所有已导入知识库的文档及其切分情况</p>
        </div>
        <button
          onClick={fetchDocuments}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 border border-gray-200 dark:border-slate-700 hover:border-indigo-300 rounded-lg transition-colors disabled:opacity-40 flex-shrink-0"
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
          刷新
        </button>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="flex items-center justify-between gap-2 px-4 py-3 bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 rounded-lg text-sm">
          <span className="inline-flex items-center gap-2">
            <AlertCircle size={16} /> {error}
          </span>
          <button
            onClick={fetchDocuments}
            aria-label="重试"
            className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-500/20 transition-colors"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      )}

      {/* 加载中：骨架屏 */}
      {loading ? (
        <ListSkeleton />
      ) : documents.length === 0 ? (
        /* 空状态：引导去导入 */
        <div className="surface rounded-xl p-12 text-center transition-colors">
          <div className="w-16 h-16 bg-gray-50 dark:bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <FileStack size={32} className="text-gray-300 dark:text-slate-600" />
          </div>
          <h3 className="text-base font-medium text-gray-600 dark:text-slate-300 mb-1">暂无已导入的文档</h3>
          <p className="text-sm text-gray-400 dark:text-slate-500 mb-5">上传文档后，这里将展示全部知识库内容</p>
          <button
            onClick={() => navigate('/import')}
            className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            前往知识库导入 <ArrowRight size={15} />
          </button>
        </div>
      ) : (
        <>
          {/* 搜索框 */}
          <div className="relative">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={listQuery}
              onChange={e => setListQuery(e.target.value)}
              placeholder="搜索文档标题、主题或章节…"
              aria-label="搜索文档"
              className="w-full pl-10 pr-4 py-2.5 surface rounded-lg text-sm text-gray-700 dark:text-slate-200 placeholder-gray-400 dark:placeholder-slate-500 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-500/20 transition-colors"
            />
          </div>

          {filteredDocuments.length === 0 ? (
            <div className="surface rounded-xl p-12 text-center text-gray-400 dark:text-slate-500 transition-colors">
              没有匹配「{listQuery}」的文档
            </div>
          ) : (
            /* 文档卡片列表 */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {filteredDocuments.map(doc => (
                <div
                  key={doc.file_title}
                  onClick={() => viewChunks(doc)}
                  className="surface rounded-xl shadow-sm p-5 hover:border-indigo-300 dark:hover:border-indigo-500 hover:shadow-md cursor-pointer transition-all"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileText size={20} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-gray-800 dark:text-slate-100 line-clamp-2 break-all">
                        {doc.file_title}
                      </h3>
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 dark:text-slate-500">
                        <span className="inline-flex items-center gap-1">
                          <Hash size={12} /> {doc.chunk_count} 切片
                        </span>
                        <span className="inline-flex items-center gap-1 truncate">
                          <Tag size={12} /> {doc.item_name || '未识别'}
                        </span>
                      </div>
                    </div>
                  </div>
                  {/* 章节标签 */}
                  {doc.titles.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-50 dark:border-slate-800 flex flex-wrap gap-1.5">
                      {doc.titles.slice(0, 4).map((t, i) => (
                        <span key={`title_${i}`} className="text-xs px-2 py-0.5 bg-gray-50 dark:bg-slate-800 text-gray-500 dark:text-slate-400 rounded line-clamp-1 max-w-[200px]">
                          {t.replace(/^#+\s*/, '')}
                        </span>
                      ))}
                      {doc.titles.length > 4 && (
                        <span className="text-xs px-2 py-0.5 text-gray-400 dark:text-slate-500">
                          +{doc.titles.length - 4}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
