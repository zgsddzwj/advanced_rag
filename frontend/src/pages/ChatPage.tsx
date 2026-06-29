import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Plus, MessageCircle } from 'lucide-react'
import { ask, listenStream, getHistory, clearHistory } from '@/api/client'
import type { ChatMessage } from '@/types'
import MessageBubble from '@/components/MessageBubble'
import TypingIndicator from '@/components/TypingIndicator'

const SUGGESTIONS = [
  '这个产品的使用方法是什么？',
  '设备的技术参数有哪些？',
  '常见的故障及排除方法？',
]

export default function ChatPage() {
  const [sessionId, setSessionId] = useState(() => localStorage.getItem('kb_session_id') || '')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [waiting, setWaiting] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [showTyping, setShowTyping] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // 加载历史
  useEffect(() => {
    if (sessionId) {
      getHistory(sessionId).then(data => {
        if (data.messages?.length > 0) setMessages(data.messages)
      }).catch(console.error)
    }
  }, [sessionId])

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingText, showTyping, scrollToBottom])

  const newSession = () => {
    setSessionId('')
    setMessages([])
    localStorage.removeItem('kb_session_id')
  }

  const sendQuery = async (query?: string) => {
    const q = (query || input).trim()
    if (!q || waiting) return

    setWaiting(true)
    setShowTyping(true)
    setInput('')

    // 添加用户消息
    setMessages(prev => [...prev, { role: 'user', text: q }])

    try {
      const data = await ask(q, sessionId)
      setSessionId(data.session_id)
      localStorage.setItem('kb_session_id', data.session_id)

      // SSE 流式接收
      let accText = ''
      listenStream(data.task_id, {
        onDelta(d) {
          setShowTyping(false)
          accText += d.text
          setStreamingText(accText)
        },
        onFinal(d) {
          setShowTyping(false)
          setStreamingText('')
          setMessages(prev => [...prev, {
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
          setMessages(prev => [...prev, { role: 'assistant', text: `⚠️ ${d.message || '生成回答时出现错误'}` }])
          setWaiting(false)
        },
      })
    } catch (e) {
      setShowTyping(false)
      setMessages(prev => [...prev, { role: 'assistant', text: '⚠️ 网络错误，请稍后重试' }])
      setWaiting(false)
    }
  }

  const quickAsk = (q: string) => {
    setInput(q)
    sendQuery(q)
  }

  const isEmpty = messages.length === 0 && !streamingText && !showTyping

  return (
    <div className="flex flex-col h-full">
      {/* 顶部操作 */}
      <div className="flex items-center justify-between px-8 py-3 bg-white border-b border-gray-100">
        <span className="text-sm text-gray-400">
          {sessionId ? `Session: ${sessionId}` : '新对话'}
        </span>
        <button
          onClick={newSession}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-indigo-600 border border-gray-200 hover:border-indigo-300 rounded-lg transition-colors"
        >
          <Plus size={15} /> 新对话
        </button>
      </div>

      {/* 聊天区域 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-6 space-y-4">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-4">
            <div className="w-16 h-16 bg-indigo-50 rounded-2xl flex items-center justify-center">
              <MessageCircle size={32} className="text-indigo-500" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">欢迎使用掌柜智库</h2>
              <p className="text-sm text-gray-400 max-w-md">
                基于多路混合检索 (Dense + BM25 + HyDE + 网络搜索)，为您提供精准的智能问答服务。
              </p>
            </div>
            <div className="flex gap-3 flex-wrap justify-center mt-2">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => quickAsk(s)}
                  className="px-4 py-2 text-sm bg-white border border-gray-200 rounded-full text-gray-500 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            {showTyping && <TypingIndicator />}
            {streamingText && (
              <MessageBubble msg={{ role: 'assistant', text: streamingText }} streaming />
            )}
          </>
        )}
      </div>

      {/* 输入区域 */}
      <div className="px-8 py-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 items-center">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery() } }}
            placeholder="输入你的问题..."
            disabled={waiting}
            className="flex-1 px-4 py-3 border border-gray-200 rounded-lg text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-gray-50"
          />
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
