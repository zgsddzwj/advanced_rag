import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Plus, MessageCircle, Loader2, ArrowDown } from 'lucide-react'
import { ask, listenStream, getHistory } from '@/api/client'
import type { ChatMessage, SSEThinkingData } from '@/types'
import MessageBubble from '@/components/MessageBubble'
import TypingIndicator from '@/components/TypingIndicator'
import ThinkingProcess from '@/components/ThinkingProcess'

const SUGGESTIONS = [
  '这个产品的使用方法是什么？',
  '设备的技术参数有哪些？',
  '常见的故障及排除方法？',
]

const QUERY_NODE_LABELS: Record<string, string> = {
  node_item_name_confirm: '商品名确认',
  node_search_embedding: '向量检索',
  node_search_embedding_hyde: 'HyDE 检索',
  node_web_search_mcp: '网络搜索',
  node_rrf: 'RRF 融合',
  node_rerank: 'Rerank 重排',
  node_answer_output: '生成回答',
}

// 全局消息 ID 计数器（保证唯一性）
let _msgIdCounter = 0
function nextMsgId(): string {
  _msgIdCounter += 1
  return `msg_${Date.now()}_${_msgIdCounter}`
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('kb_session_id') || '')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [waiting, setWaiting] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [showTyping, setShowTyping] = useState(false)
  const [progressNodes, setProgressNodes] = useState<{ done: string[]; running: string[] }>({ done: [], running: [] })
  // 检索策略（演进7）：HyDE 开关 + 联网搜索三态（auto=按结果数自动判断）
  const [enableHyde, setEnableHyde] = useState(true)
  const [webSearchMode, setWebSearchMode] = useState<'auto' | 'on' | 'off'>('auto')
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const sseRef = useRef<EventSource | null>(null)
  // 用户是否停留在底部附近：不在底部时暂停自动滚动并显示「回到底部」按钮
  const [atBottom, setAtBottom] = useState(true)

  // 加载历史
  useEffect(() => {
    if (sessionId) {
      getHistory(sessionId).then(data => {
        if (data.messages?.length > 0) {
          // 为历史消息补充唯一 ID
          setMessages(data.messages.map((m: ChatMessage) => ({ ...m, id: nextMsgId() })))
        }
      }).catch(console.error)
    }
  }, [sessionId])

  // 智能滚动：仅在用户接近底部时自动滚动
  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (distanceFromBottom < 120) {
      el.scrollTop = el.scrollHeight
    }
  }, [])

  // 「回到底部」按钮：无视当前滚动位置强制置底
  const forceScrollToBottom = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    setAtBottom(true)
  }, [])

  const handleChatScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 120)
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingText, showTyping, progressNodes, scrollToBottom])

  // 自动聚焦输入框
  useEffect(() => {
    inputRef.current?.focus()
  }, [sessionId, waiting])

  // 组件卸载时关闭 SSE 连接
  useEffect(() => {
    return () => {
      sseRef.current?.close()
    }
  }, [])

  const newSession = () => {
    sseRef.current?.close()
    setSessionId('')
    setMessages([])
    localStorage.removeItem('kb_session_id')
    inputRef.current?.focus()
  }

  const sendQuery = async (query?: string) => {
    const q = (query || input).trim()
    if (!q || waiting) return

    setWaiting(true)
    setShowTyping(true)
    setProgressNodes({ done: [], running: [] })
    setInput('')

    // 重置思考过程
    window.dispatchEvent(new CustomEvent('thinking-reset'))

    // 添加用户消息（带唯一 ID）
    setMessages(prev => [...prev, { id: nextMsgId(), role: 'user', text: q }])

    try {
      const retrieval = {
        enable_hyde: enableHyde,
        enable_web_search: webSearchMode === 'auto' ? undefined : webSearchMode === 'on',
      }
      const data = await ask(q, sessionId, retrieval)
      setSessionId(data.session_id)
      localStorage.setItem('kb_session_id', data.session_id)

      // SSE 流式接收
      let accText = ''
      sseRef.current = listenStream(data.task_id, {
        onThinking(d: SSEThinkingData) {
          setShowTyping(false)
          window.dispatchEvent(new CustomEvent('thinking-step', { detail: d }))
        },
        onProgress(d) {
          setProgressNodes({ done: d.done_list || [], running: d.running_list || [] })
        },
        onDelta(d) {
          setShowTyping(false)
          accText += d.text
          setStreamingText(accText)
        },
        onFinal(d) {
          setShowTyping(false)
          setStreamingText('')
          // 延迟清除思考过程
          setTimeout(() => window.dispatchEvent(new CustomEvent('thinking-reset')), 500)
          setProgressNodes({ done: [], running: [] })
          setMessages(prev => [...prev, {
            id: nextMsgId(),
            role: 'assistant',
            text: d.answer || accText,
            image_urls: d.image_urls || [],
            item_names: d.item_names || [],
          }])
          setWaiting(false)
        },
        onError(d) {
          setShowTyping(false)
          setStreamingText('')
          setTimeout(() => window.dispatchEvent(new CustomEvent('thinking-reset')), 500)
          setProgressNodes({ done: [], running: [] })
          setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', text: `⚠️ ${d.message || '生成回答时出现错误'}` }])
          setWaiting(false)
        },
      })
    } catch (e) {
      setShowTyping(false)
      setTimeout(() => window.dispatchEvent(new CustomEvent('thinking-reset')), 500)
      setProgressNodes({ done: [], running: [] })
      setMessages(prev => [...prev, { id: nextMsgId(), role: 'assistant', text: '⚠️ 网络错误，请稍后重试' }])
      setWaiting(false)
    }
  }

  const quickAsk = (q: string) => {
    sendQuery(q)
  }

  // textarea 自适应高度
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }

  const isEmpty = messages.length === 0 && !streamingText && !showTyping

  return (
    <div className="flex flex-col h-full">
      {/* 顶部操作 */}
      <div className="flex items-center justify-between px-8 py-3 bg-white dark:bg-slate-900 border-b border-gray-100 dark:border-slate-800 transition-colors">
        <span className="text-sm text-gray-400 dark:text-slate-500">
          {sessionId ? `Session: ${sessionId}` : '新对话'}
        </span>
        <button
          onClick={newSession}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 border border-gray-200 dark:border-slate-700 hover:border-indigo-300 rounded-lg transition-colors"
        >
          <Plus size={15} /> 新对话
        </button>
      </div>

      {/* 聊天区域 */}
      <div className="relative flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleChatScroll}
          className="h-full overflow-y-auto px-4 md:px-8 py-6 space-y-4"
        >
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <MessageCircle size={30} className="text-white" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-700 dark:text-slate-200 mb-2">欢迎使用 NexusRAG</h2>
                <p className="text-sm text-gray-400 dark:text-slate-500 max-w-md">
                  基于多路混合检索 (Dense + BM25 + HyDE + 网络搜索)，为您提供精准的智能问答服务。
                </p>
              </div>
              <div className="flex gap-3 flex-wrap justify-center mt-2">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => quickAsk(s)}
                    className="px-4 py-2 text-sm bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-full text-gray-500 dark:text-slate-400 hover:border-indigo-300 dark:hover:border-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-300 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble key={msg.id || nextMsgId()} msg={msg} />
              ))}
              {(showTyping || waiting) && <ThinkingProcess />}
              {showTyping && <TypingIndicator />}
              {progressNodes.running.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-slate-500 px-2">
                  <Loader2 size={12} className="animate-spin" />
                  {progressNodes.running.map(n => QUERY_NODE_LABELS[n] || n).join(' · ')}
                </div>
              )}
              {streamingText && (
                <MessageBubble msg={{ id: 'streaming', role: 'assistant', text: streamingText }} streaming />
              )}
            </>
          )}
        </div>

        {/* 回到底部按钮：用户上滑查看历史时显示 */}
        {!atBottom && !isEmpty && (
          <button
            onClick={forceScrollToBottom}
            aria-label="回到底部"
            className="absolute bottom-4 right-6 p-2.5 rounded-full bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-600 shadow-lg text-gray-500 dark:text-slate-300 hover:text-indigo-500 dark:hover:text-indigo-400 hover:border-indigo-300 transition-colors"
          >
            <ArrowDown size={17} />
          </button>
        )}
      </div>

      {/* 输入区域 */}
      <div className="px-4 md:px-8 py-4 bg-white dark:bg-slate-900 border-t border-gray-100 dark:border-slate-800 transition-colors">
        {/* 检索策略开关（演进7） */}
        <div className="flex items-center gap-4 mb-2 text-xs text-gray-500 dark:text-slate-400">
          <label className="inline-flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={enableHyde}
              onChange={e => setEnableHyde(e.target.checked)}
              className="accent-indigo-500"
            />
            HyDE 补充检索
          </label>
          <label className="inline-flex items-center gap-1.5 select-none">
            联网搜索
            <select
              value={webSearchMode}
              onChange={e => setWebSearchMode(e.target.value as 'auto' | 'on' | 'off')}
              className="border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 rounded px-1 py-0.5 text-xs text-gray-600 dark:text-slate-300 focus:outline-none focus:border-indigo-300"
            >
              <option value="auto">自动判断</option>
              <option value="on">强制开启</option>
              <option value="off">关闭</option>
            </select>
          </label>
        </div>
        <div className="flex gap-3 items-end">
          <div className="relative flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInput}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendQuery()
                }
              }}
              maxLength={2000}
              placeholder="输入你的问题... (Shift+Enter 换行)"
              disabled={waiting}
              rows={1}
              className="w-full px-4 py-3 border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-gray-800 dark:text-slate-200 rounded-lg text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-500/20 disabled:bg-gray-50 dark:disabled:bg-slate-800 resize-none transition-colors"
              style={{ maxHeight: '120px' }}
            />
            {/* 接近后端 2000 字上限时显示计数 */}
            {input.length > 1800 && (
              <span className={`absolute right-3 bottom-2 text-xs ${input.length >= 2000 ? 'text-red-500' : 'text-gray-400'}`}>
                {input.length}/2000
              </span>
            )}
          </div>
          <button
            onClick={() => sendQuery()}
            disabled={waiting || !input.trim()}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send size={16} /> 发送
          </button>
        </div>
      </div>
    </div>
  )
}
