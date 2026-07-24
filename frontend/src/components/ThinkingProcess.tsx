import { useState, useEffect } from 'react'
import { Brain, CheckCircle2, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import type { SSEThinkingData } from '@/types'

interface ThinkingStep {
  node: string
  message: string
  detail?: string
  done?: boolean
}

export default function ThinkingProcess() {
  const [steps, setSteps] = useState<ThinkingStep[]>([])
  const [collapsed, setCollapsed] = useState(false)

  // 暴露给父组件的方法：通过自定义事件接收思考过程
  useEffect(() => {
    const handler = (e: Event) => {
      const data = (e as CustomEvent<SSEThinkingData>).detail
      setSteps(prev => {
        // 如果同节点已存在，更新它
        const existing = prev.find(s => s.node === data.node)
        if (existing) {
          return prev.map(s =>
            s.node === data.node
              ? { ...s, message: data.message, detail: data.detail, done: (data as any).done }
              : s
          )
        }
        return [...prev, { node: data.node, message: data.message, detail: data.detail, done: (data as any).done }]
      })
    }
    window.addEventListener('thinking-step', handler)
    return () => window.removeEventListener('thinking-step', handler)
  }, [])

  // 监听重置事件
  useEffect(() => {
    const handler = () => setSteps([])
    window.addEventListener('thinking-reset', handler)
    return () => window.removeEventListener('thinking-reset', handler)
  }, [])

  if (steps.length === 0) return null

  const allDone = steps.length > 0 && steps.every(s => s.done)
  const currentStep = steps.find(s => !s.done)

  return (
    <div className="flex justify-start mb-2">
      <div className="max-w-[80%] bg-white border border-indigo-100 rounded-2xl rounded-bl-md shadow-sm overflow-hidden">
        {/* 头部 */}
        <div
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer hover:bg-gray-50/80 transition-colors"
        >
          <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
            allDone ? 'bg-green-100' : 'bg-indigo-100'
          }`}>
            {allDone ? (
              <CheckCircle2 size={14} className="text-green-600" />
            ) : (
              <Loader2 size={14} className="text-indigo-500 animate-spin" />
            )}
          </div>
          <span className="text-xs font-medium text-gray-600 flex-1">
            {allDone ? '思考完成' : currentStep?.message || '思考中...'}
          </span>
          {collapsed ? (
            <ChevronDown size={14} className="text-gray-400" />
          ) : (
            <ChevronUp size={14} className="text-gray-400" />
          )}
        </div>

        {/* 展开的步骤列表 */}
        {!collapsed && (
          <div className="px-4 pb-3 space-y-1.5">
            {steps.map((step, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
                  step.done ? 'bg-green-50' : 'bg-amber-50'
                }`}>
                  {step.done ? (
                    <CheckCircle2 size={10} className="text-green-500" />
                  ) : (
                    <Loader2 size={10} className="text-amber-500 animate-spin" />
                  )}
                </div>
                <span className={`flex items-center gap-1 ${
                  step.done ? 'text-gray-400' : 'text-gray-700 font-medium'
                }`}>
                  <Brain size={11} className={step.done ? 'text-gray-300' : 'text-indigo-400'} />
                  {step.detail || step.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
