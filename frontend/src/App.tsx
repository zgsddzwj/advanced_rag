import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
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

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><Dashboard /></ErrorBoundary></Suspense>} />
        <Route path="/import" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><ImportPage /></ErrorBoundary></Suspense>} />
        <Route path="/documents" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><DocumentsPage /></ErrorBoundary></Suspense>} />
        <Route path="/chat" element={<Suspense fallback={<PageSkeleton />}><ErrorBoundary><ChatPage /></ErrorBoundary></Suspense>} />
      </Route>
    </Routes>
  )
}
