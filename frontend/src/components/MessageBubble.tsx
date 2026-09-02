import { useEffect, useRef, useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'
import { Tag, Copy, Check } from 'lucide-react'
import type { ChatMessage } from '@/types'

function CodeBlockCopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-gray-700/80 hover:bg-gray-600 text-gray-200 opacity-0 group-hover:opacity-100 transition-opacity"
      title="复制代码"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  )
}

// memo 化：流式输出期间 ChatPage 每个 token 都会重渲，
// 历史消息的 msg 对象引用不变，跳过 ReactMarkdown 重复解析
function MessageBubble({ msg, streaming }: { msg: ChatMessage; streaming?: boolean }) {
  const isUser = msg.role === 'user'
  const textRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (streaming && textRef.current) {
      textRef.current.scrollTop = textRef.current.scrollHeight
    }
  }, [msg.text, streaming])

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] px-5 py-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
          isUser
            ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-br-md'
            : 'bg-white text-gray-800 rounded-bl-md border border-gray-100'
        }`}
      >
        {/* 文本内容 */}
        {isUser ? (
          <div className="whitespace-pre-wrap">{msg.text}</div>
        ) : (
          <div className="markdown-body" ref={textRef}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                pre({ children, ...props }) {
                  // 提取代码文本用于复制
                  let codeText = ''
                  if (children && typeof children === 'object' && 'props' in (children as any)) {
                    const childProps = (children as any).props
                    codeText = typeof childProps?.children === 'string'
                      ? childProps.children
                      : Array.isArray(childProps?.children)
                        ? childProps.children.filter((c: any) => typeof c === 'string').join('')
                        : ''
                  }
                  return (
                    <div className="group relative">
                      <CodeBlockCopyButton code={codeText} />
                      <pre {...props}>{children}</pre>
                    </div>
                  )
                },
              }}
            >
              {msg.text || ' '}
            </ReactMarkdown>
          </div>
        )}

        {/* 图片 */}
        {msg.image_urls && msg.image_urls.length > 0 && (
          <div className="mt-2 space-y-2">
            {msg.image_urls.map((url, i) => (
              <img key={i} src={url} alt="" className="max-w-full rounded-lg shadow-sm" />
            ))}
          </div>
        )}

        {/* 文档主题标签 */}
        {msg.item_names && msg.item_names.length > 0 && (
          <div className={`mt-3 pt-3 border-t flex items-center gap-2 flex-wrap ${isUser ? 'border-white/20' : 'border-gray-100'}`}>
            <Tag size={14} className={isUser ? 'text-white/60' : 'text-gray-400'} />
            {msg.item_names.map((name, i) => (
              <span
                key={i}
                className={`text-xs px-2 py-0.5 rounded ${
                  isUser ? 'bg-white/20 text-white/90' : 'bg-indigo-50 text-indigo-600'
                }`}
              >
                {name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default memo(MessageBubble)
