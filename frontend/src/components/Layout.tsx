import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Upload, MessageSquare, BookOpen, Activity } from 'lucide-react'
import { useEffect, useState } from 'react'
import { healthCheck } from '@/api/client'

const navItems = [
  { to: '/', label: '系统首页', icon: LayoutDashboard },
  { to: '/import', label: '知识库导入', icon: Upload },
  { to: '/chat', label: '智能问答', icon: MessageSquare },
]

export default function Layout() {
  const location = useLocation()
  const [online, setOnline] = useState(true)

  useEffect(() => {
    healthCheck().then(() => setOnline(true)).catch(() => setOnline(false))
  }, [])

  const pageTitle = navItems.find(n => n.to === location.pathname)?.label || '掌柜智库'

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 侧边栏 */}
      <aside className="w-60 bg-slate-900 text-white flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-6 py-7 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <BookOpen size={22} />
            </div>
            <div>
              <div className="font-bold text-lg leading-tight">掌柜智库</div>
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
          <span className={`w-2 h-2 rounded-full ${online ? 'bg-green-400' : 'bg-red-400'}`} />
          {online ? '服务运行中' : '服务离线'}
        </div>
      </aside>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 顶栏 */}
        <header className="bg-white border-b border-gray-200 px-8 py-4 flex items-center justify-between flex-shrink-0">
          <h1 className="text-lg font-semibold text-gray-800">{pageTitle}</h1>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Activity size={16} />
            <span>LangGraph + Milvus + 百炼</span>
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
