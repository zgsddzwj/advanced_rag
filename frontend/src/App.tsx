import { Suspense, lazy } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { Compass } from 'lucide-react'
import Layout from '@/components/Layout'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// 路由级代码分割：每个页面独立 chunk，首屏只加载当前页
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ImportPage = lazy(() => import('@/pages/ImportPage'))
const DocumentsPage = lazy(() => import('@/pages/DocumentsPage'))
const ChatPage = lazy(() => import('@/pages/ChatPage'))

/** 路由切换时的骨架屏占位 */
function PageSkeleton() {
  return (
    <div className="p-8 space-y-5 animate-pulse" aria-busy="true" aria-label="页面加载中">
      <div className="h-36 rounded-2xl bg-gray-200/70 dark:bg-slate-800" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[0, 1, 2, 3].map(i => (
          <div key={i} className="h-28 rounded-xl bg-gray-200/70 dark:bg-slate-800" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-gray-200/70 dark:bg-slate-800" />
    </div>
  )
}

/** 404 兜底页：未知路径不再渲染空白主区 */
function NotFound() {
  const navigate = useNavigate()
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center gap-4">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-500/15 flex items-center justify-center">
        <Compass size={30} className="text-indigo-500" />
      </div>
      <div>
        <h2 className="text-2xl font-bold text-gray-800 dark:text-slate-100 mb-1">404</h2>
        <p className="text-sm text-gray-400 dark:text-slate-500">页面不存在或已被移动</p>
      </div>
      <button
        onClick={() => navigate('/')}
        className="px-5 py-2.5 bg-indigo-500 text-white rounded-lg text-sm font-medium hover:bg-indigo-600 transition-colors"
      >
        返回系统首页
      </button>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><Dashboard /></ErrorBoundary></Suspense>} />
        <Route path="/import" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><ImportPage /></ErrorBoundary></Suspense>} />
        <Route path="/documents" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><DocumentsPage /></ErrorBoundary></Suspense>} />
        <Route path="/chat" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><ChatPage /></ErrorBoundary></Suspense>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
