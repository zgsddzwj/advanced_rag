import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * 路由级错误边界：单个页面渲染崩溃不影响整个应用外壳，
 * 用户可以原地重试或刷新（生产应用标配）
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error('页面渲染异常:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-10 min-h-[70vh] flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-red-50 dark:bg-red-500/10 flex items-center justify-center mb-5">
            <AlertTriangle size={30} className="text-red-500" />
          </div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-slate-100 mb-2">
            页面出了点问题
          </h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mb-7 max-w-md break-all leading-relaxed">
            {this.state.error.message || '渲染时发生未知错误'}
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => this.setState({ error: null })}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-500 text-white rounded-lg text-sm font-medium hover:bg-indigo-600 transition-colors"
            >
              <RotateCcw size={15} /> 重试
            </button>
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 surface text-gray-600 dark:text-slate-300 rounded-lg text-sm font-medium hover:border-indigo-300 transition-colors"
            >
              <RefreshCw size={15} /> 刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
