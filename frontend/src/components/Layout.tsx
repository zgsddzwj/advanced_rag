import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Upload, FileStack, MessageSquare, BookOpen,
  Activity, Sun, Moon, Menu, X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { getSystemHealth } from '@/api/client'
import { useTheme } from '@/components/ThemeProvider'

const navItems = [
  { to: '/', label: '系统首页', icon: LayoutDashboard },
  { to: '/import', label: '知识库导入', icon: Upload },
  { to: '/documents', label: '文档预览', icon: FileStack },
  { to: '/chat', label: '智能问答', icon: MessageSquare },
]

type HealthState = 'ok' | 'degraded' | 'offline'

const HEALTH_BADGE: Record<HealthState, { dot: string; text: string }> = {
  ok: { dot: 'bg-green-400', text: '系统正常' },
  degraded: { dot: 'bg-amber-400', text: '部分依赖异常' },
  offline: { dot: 'bg-red-400', text: '服务离线' },
}

/** 侧边栏内容：桌面常驻与移动抽屉共用 */
function SidebarContent({ health, onNavigate }: { health: HealthState; onNavigate?: () => void }) {
  return (
    <>
      {/* Logo */}
      <div className="px-6 py-7 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
            <BookOpen size={22} />
          </div>
          <div>
            <div className="font-bold text-lg leading-tight">NexusRAG</div>
            <div className="text-xs text-white/40">Advanced RAG</div>
          </div>
        </div>
      </div>

      {/* 导航 */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map(item => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-500/20 text-white'
                    : 'text-white/50 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <Icon size={18} />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      {/* 底部状态 */}
      <div className="px-6 py-4 border-t border-white/5 text-xs text-white/30 flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${HEALTH_BADGE[health].dot}`} />
        {HEALTH_BADGE[health].text}
      </div>
    </>
  )
}

export default function Layout() {
  const location = useLocation()
  const { theme, toggle } = useTheme()
  const [health, setHealth] = useState<HealthState>('ok')
  const [drawerOpen, setDrawerOpen] = useState(false)

  // 定期健康检查（每 30 秒）：聚合端点探测全部下游依赖
  useEffect(() => {
    const check = () =>
      getSystemHealth()
        .then(r => setHealth(r.status === 'degraded' ? 'degraded' : 'ok'))
        .catch(() => setHealth('offline'))
    check()
    const timer = setInterval(check, 30000)
    return () => clearInterval(timer)
  }, [])

  // 路由变化时收起移动端抽屉
  useEffect(() => {
    setDrawerOpen(false)
  }, [location.pathname])

  // 抽屉打开时支持 Esc 关闭
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  const pageTitle = navItems.find(n => n.to === location.pathname)?.label || 'NexusRAG'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 桌面侧边栏（md 及以上常驻） */}
      <aside className="hidden md:flex w-60 bg-slate-900 text-white flex-col flex-shrink-0">
        <SidebarContent health={health} />
      </aside>

      {/* 移动端抽屉 */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="导航菜单">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="drawer-enter absolute left-0 top-0 h-full w-64 bg-slate-900 text-white flex flex-col shadow-2xl">
            <button
              onClick={() => setDrawerOpen(false)}
              aria-label="关闭菜单"
              className="absolute top-4 right-4 p-1.5 text-white/50 hover:text-white transition-colors"
            >
              <X size={18} />
            </button>
            <SidebarContent health={health} onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* 顶栏 */}
        <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-800 px-4 md:px-8 py-4 flex items-center justify-between flex-shrink-0 transition-colors">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setDrawerOpen(true)}
              aria-label="打开导航菜单"
              className="md:hidden p-2 -m-2 rounded-lg text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors"
            >
              <Menu size={20} />
            </button>
            <div className="md:hidden flex items-center gap-2">
              <div className="w-7 h-7 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <BookOpen size={15} className="text-white" />
              </div>
              <span className="font-bold text-gray-800 dark:text-slate-100">NexusRAG</span>
            </div>
            <h1 className="hidden md:block text-lg font-semibold text-gray-800 dark:text-slate-100 truncate">
              {pageTitle}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-400 dark:text-slate-400 flex-shrink-0">
            <Activity size={16} />
            <span className="hidden md:inline">LangGraph + Milvus + 百炼</span>
            <button
              onClick={toggle}
              aria-label={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
              title={theme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
              className="p-2 rounded-lg text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800 hover:text-gray-700 dark:hover:text-slate-200 transition-colors"
            >
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
