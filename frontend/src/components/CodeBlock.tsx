import { useState } from 'react'
import { Check, Copy } from 'lucide-react'

/** 从 hast 节点递归提取纯文本（rehype-highlight 会把代码拆成 span，不能直接取字符串） */
export function extractText(node: unknown): string {
  if (!node) return ''
  if (Array.isArray(node)) return node.map(extractText).join('')
  const n = node as { type?: string; value?: string; children?: unknown[] }
  if (n.type === 'text') return n.value ?? ''
  return extractText(n.children)
}

/** 剪贴板复制：优先 Clipboard API，非安全上下文（http）回退 execCommand */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      return ok
    } catch {
      return false
    }
  }
}

interface CodeBlockProps {
  language: string
  rawText: string
  children: React.ReactNode
}

/**
 * Markdown 代码块容器：语言标签 + 复制按钮 + 横向滚动。
 * children 为 react-markdown 渲染的原始 <code> 元素（保留 hljs 高亮）。
 */
export default function CodeBlock({ language, rawText, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    if (await copyText(rawText)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="code-block my-3 rounded-lg overflow-hidden border border-slate-700/50 bg-[#1e1e2e]">
      <div className="flex items-center justify-between px-4 py-1.5 bg-slate-800/60 border-b border-slate-700/40">
        <span className="text-xs text-slate-400 font-mono lowercase">{language}</span>
        <button
          onClick={handleCopy}
          aria-label="复制代码"
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-100 transition-colors"
        >
          {copied ? (
            <>
              <Check size={13} className="text-green-400" />
              <span className="text-green-400">已复制</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              复制
            </>
          )}
        </button>
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  )
}
