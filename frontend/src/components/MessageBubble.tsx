import { useEffect, useRef, useState, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/github-dark.css'
import { Tag, Copy, Check, X } from 'lucide-react'
import type { ChatMessage } from '@/types'
import CodeBlock, { copyText, extractText } from '@/components/CodeBlock'

function CopyMessageButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    if (await copyText(text)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      aria-label="复制回答全文"
      title="复制全文"
      className="absolute -bottom-7 right-1 p-1 text-gray-300 hover:text-indigo-400 dark:text-slate-600 dark:hover:text-indigo-400 opacity-0 group-hover:opacity-100 transition-all"
    >
      {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
    </button>
  )
}

// memo 化：流式输出期间 ChatPage 每个 token 都会重渲，
// 历史消息的 msg 对象引用不变，跳过 ReactMarkdown 重复解析
function MessageBubble({ msg, streaming }: { msg: ChatMessage; streaming?: boolean }) {
  const isUser = msg.role === 'user'
  const textRef = useRef<HTMLDivElement>(null)
  const [preview, setPreview] = useState<string | null>(null)

  useEffect(() => {
    if (streaming && textRef.current) {
      textRef.current.scrollTop = textRef.current.scrollHeight
    }
  }, [msg.text, streaming])

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`group relative max-w-[75%] px-5 py-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
          isUser
            ? 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-br-md'
            : 'bg-white dark:bg-slate-900 text-gray-800 dark:text-slate-100 rounded-bl-md border border-gray-100 dark:border-slate-700'
        } transition-colors`}
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
                // 自定义代码块：语言标签 + 复制按钮（保留 hljs 高亮 span）
                pre({ node, children }) {
                  const codeNode = (node as { children?: Array<{ tagName?: string; properties?: { className?: string[] } }> })
                    ?.children?.find(n => n.tagName === 'code')
                  const classNames = codeNode?.properties?.className ?? []
                  const lang = /language-([\w-]+)/.exec(classNames.join(' '))?.[1] ?? 'text'
                  return (
                    <CodeBlock language={lang} rawText={extractText(codeNode)}>
                      {children}
                    </CodeBlock>
                  )
                },
                // 外链安全：新窗口打开 + 隔离 opener
                a({ node, children, ...props }) {
                  return (
                    <a {...props} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  )
                },
                // 回答配图：点击放大预览
                img({ node, ...props }) {
                  return (
                    <img
                      {...props}
                      loading="lazy"
                      decoding="async"
                      onClick={e => setPreview((e.target as HTMLImageElement).src)}
                      className="max-w-full rounded-lg shadow-sm cursor-zoom-in"
                      alt=""
                    />
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
              <img
                key={i}
                src={url}
                alt=""
                loading="lazy"
                decoding="async"
                onClick={() => setPreview(url)}
                className="max-w-full rounded-lg shadow-sm cursor-zoom-in"
              />
            ))}
          </div>
        )}

        {/* 文档主题标签 */}
        {msg.item_names && msg.item_names.length > 0 && (
          <div className={`mt-3 pt-3 border-t flex items-center gap-2 flex-wrap ${isUser ? 'border-white/20' : 'border-gray-100 dark:border-slate-700'}`}>
            <Tag size={14} className={isUser ? 'text-white/60' : 'text-gray-400'} />
            {msg.item_names.map((name, i) => (
              <span
                key={i}
                className={`text-xs px-2 py-0.5 rounded ${
                  isUser ? 'bg-white/20 text-white/90' : 'bg-indigo-50 text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300'
                }`}
              >
                {name}
              </span>
            ))}
          </div>
        )}

        {/* 复制全文（悬停显现） */}
        {!isUser && !streaming && msg.text && <CopyMessageButton text={msg.text} />}

        {/* 图片放大预览 */}
        {preview && (
          <div
            className="fixed inset-0 z-[90] bg-black/80 backdrop-blur-sm flex items-center justify-center p-8 cursor-zoom-out"
            onClick={() => setPreview(null)}
            role="dialog"
            aria-modal="true"
            aria-label="图片预览"
          >
            <img src={preview} alt="" className="max-w-full max-h-full rounded-lg shadow-2xl" />
            <button
              aria-label="关闭预览"
              className="absolute top-5 right-5 p-2 text-white/70 hover:text-white transition-colors"
            >
              <X size={22} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default memo(MessageBubble)
