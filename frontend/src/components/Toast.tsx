import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  type: ToastType
  message: string
}

interface ToastContextValue {
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue>({
  success: () => {},
  error: () => {},
  info: () => {},
})

const ICONS: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const ICON_COLORS: Record<ToastType, string> = {
  success: 'text-green-500',
  error: 'text-red-500',
  info: 'text-blue-500',
}

const MAX_VISIBLE = 5
const DEFAULT_DURATION_MS = 4000
const ERROR_DURATION_MS = 6000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const idRef = useRef(0)
  const timersRef = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    const timer = timersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timersRef.current.delete(id)
    }
  }, [])

  const push = useCallback((type: ToastType, message: string) => {
    const id = ++idRef.current
    // 同屏最多保留 MAX_VISIBLE 条，新的挤掉最旧的
    setToasts(prev => [...prev.slice(-(MAX_VISIBLE - 1)), { id, type, message }])
    const duration = type === 'error' ? ERROR_DURATION_MS : DEFAULT_DURATION_MS
    timersRef.current.set(
      id,
      setTimeout(() => dismiss(id), duration),
    )
  }, [dismiss])

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (message: string) => push('success', message),
      error: (message: string) => push('error', message),
      info: (message: string) => push('info', message),
    }),
    [push],
  )

  // 卸载时清理全部定时器
  useEffect(() => () => timersRef.current.forEach(t => clearTimeout(t)), [])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* 通知容器 */}
      <div
        className="fixed top-4 right-4 z-[100] flex flex-col gap-2.5 w-[380px] max-w-[calc(100vw-2rem)]"
        role="status"
        aria-live="polite"
      >
        {toasts.map(t => {
          const Icon = ICONS[t.type]
          return (
            <div
              key={t.id}
              className="toast-enter surface rounded-xl shadow-lg px-4 py-3 flex items-start gap-3"
            >
              <Icon size={19} className={`${ICON_COLORS[t.type]} flex-shrink-0 mt-0.5`} />
              <p className="flex-1 text-sm text-gray-700 dark:text-slate-200 leading-relaxed break-words">
                {t.message}
              </p>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="关闭通知"
                className="text-gray-300 dark:text-slate-500 hover:text-gray-500 dark:hover:text-slate-300 transition-colors"
              >
                <X size={15} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastContext)
}
