import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload, MessageSquare, Cpu, FileStack, Search, Layers, Bot, Zap,
  Database, Server, HardDrive, Radio, RefreshCw, Loader2,
} from 'lucide-react'
import { getSystemHealth } from '@/api/client'
import type { SystemHealth } from '@/types'

const stats = [
  { icon: Bot, label: 'AI 模型接入', value: '5', color: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400' },
  { icon: FileStack, label: '导入流程节点', value: '7', color: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400' },
  { icon: Search, label: '检索流程节点', value: '7', color: 'bg-green-50 text-green-600 dark:bg-green-500/15 dark:text-green-400' },
  { icon: Layers, label: '多路检索融合', value: '3', color: 'bg-purple-50 text-purple-600 dark:bg-purple-500/15 dark:text-purple-400' },
]

const pipelineSteps = [
  '主题确认', '向量检索', 'HyDE 检索', '网络搜索', 'RRF 融合', 'Rerank 重排', '流式回答',
]

/* 下游依赖元数据：与 /api/health 的 checks 键一一对应 */
const DEPENDENCIES = [
  { key: 'mongo', label: 'MongoDB', desc: '对话历史 · 文档元数据', icon: Database },
  { key: 'milvus', label: 'Milvus', desc: '向量混合检索', icon: Cpu },
  { key: 'minio', label: 'MinIO', desc: 'PDF / 图片存储', icon: HardDrive },
  { key: 'kafka', label: 'Kafka', desc: '文档事件同步', icon: Radio },
] as const

function HealthCard({ health, refreshing, onRefresh }: {
  health: SystemHealth | null
  refreshing: boolean
  onRefresh: () => void
}) {
  return (
    <div className="surface rounded-xl shadow-sm p-6 transition-colors">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-base font-semibold text-gray-800 dark:text-slate-100">系统依赖状态</h3>
          <p className="text-xs text-gray-400 dark:text-slate-500 mt-0.5">
            {health?.cached ? '10s 内缓存 · ' : ''}每 30 秒自动探活
          </p>
        </div>
        <button
          onClick={onRefresh}
          aria-label="立即探活"
          disabled={refreshing}
          className="p-2 rounded-lg text-gray-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 transition-colors disabled:opacity-40"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
        </button>
      </div>

      {!health ? (
        /* 首次加载骨架 */
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse" aria-busy="true">
          {DEPENDENCIES.map(d => (
            <div key={d.key} className="rounded-xl border border-gray-100 dark:border-slate-800 p-4">
              <div className="h-4 w-20 rounded bg-gray-200 dark:bg-slate-700" />
              <div className="h-3 w-14 rounded bg-gray-100 dark:bg-slate-800 mt-3" />
              <div className="h-3 w-24 rounded bg-gray-100 dark:bg-slate-800 mt-2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {DEPENDENCIES.map(dep => {
            const check = health.checks[dep.key]
            const ok = check?.ok
            const Icon = dep.icon
            return (
              <div
                key={dep.key}
                className={`rounded-xl border p-4 transition-colors ${
                  ok
                    ? 'border-green-200 bg-green-50/50 dark:border-green-500/25 dark:bg-green-500/5'
                    : 'border-red-200 bg-red-50/50 dark:border-red-500/25 dark:bg-red-500/5'
                }`}
                title={check?.detail}
              >
                <div className="flex items-center justify-between">
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-gray-700 dark:text-slate-200">
                    <Icon size={15} className="text-gray-400 dark:text-slate-500" />
                    {dep.label}
                  </span>
                  {refreshing ? (
                    <Loader2 size={13} className="animate-spin text-gray-300" />
                  ) : (
                    <span className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-400' : 'bg-red-400'}`} />
                  )}
                </div>
                <div className="text-xs text-gray-400 dark:text-slate-500 mt-1.5">{dep.desc}</div>
                <div className={`text-xs mt-2 truncate ${ok ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                  {check ? (ok ? check.detail : check.detail.slice(0, 40)) : '未探活'}
                  {check?.elapsed_ms != null && (
                    <span className="text-gray-300 dark:text-slate-600"> · {check.elapsed_ms}ms</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const fetchHealth = async () => {
    setRefreshing(true)
    try {
      setHealth(await getSystemHealth())
    } catch {
      setHealth(null)
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    const timer = setInterval(fetchHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="p-4 md:p-8 space-y-6">
      {/* Hero */}
      <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-8 md:p-10 text-white relative overflow-hidden">
        <div className="relative z-10">
          <h1 className="text-2xl md:text-3xl font-bold mb-2">📚 NexusRAG — 智能知识检索引擎</h1>
          <p className="text-white/80 text-sm md:text-base">基于 LangGraph 编排 · 混合检索 (Dense + BM25) · 阿里云百炼 AI 全链路接入</p>
        </div>
        <div className="absolute -top-20 -right-10 w-80 h-80 bg-white/10 rounded-full" />
        <div className="absolute -bottom-16 right-32 w-48 h-48 bg-white/5 rounded-full" />
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {stats.map(s => {
          const Icon = s.icon
          return (
            <div key={s.label} className="surface rounded-xl shadow-sm p-6 transition-colors">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${s.color}`}>
                <Icon size={24} />
              </div>
              <div className="text-2xl font-bold text-gray-800 dark:text-slate-100">{s.value}</div>
              <div className="text-sm text-gray-500 dark:text-slate-400 mt-1">{s.label}</div>
            </div>
          )
        })}
      </div>

      {/* 系统依赖状态（真实探活） */}
      <HealthCard health={health} refreshing={refreshing} onRefresh={fetchHealth} />

      {/* 功能入口 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div
          onClick={() => navigate('/import')}
          className="surface rounded-xl shadow-sm p-8 border-2 border-transparent hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-md cursor-pointer transition-all"
        >
          <div className="w-14 h-14 bg-blue-50 dark:bg-blue-500/15 text-blue-600 dark:text-blue-400 rounded-xl flex items-center justify-center mb-4">
            <Upload size={28} />
          </div>
          <h3 className="text-lg font-semibold mb-2 text-gray-800 dark:text-slate-100">知识库导入</h3>
          <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">
            上传 PDF 或 Markdown 文档，系统自动完成 PDF 解析、图片 VLM 描述、文档切分、主题识别、向量化并存入 Milvus 向量数据库。
          </p>
          <div className="mt-4 text-sm text-indigo-600 dark:text-indigo-400 font-medium flex items-center gap-1">
            前往导入 <Zap size={14} />
          </div>
        </div>

        <div
          onClick={() => navigate('/chat')}
          className="surface rounded-xl shadow-sm p-8 border-2 border-transparent hover:border-indigo-400 dark:hover:border-indigo-500 hover:shadow-md cursor-pointer transition-all"
        >
          <div className="w-14 h-14 bg-green-50 dark:bg-green-500/15 text-green-600 dark:text-green-400 rounded-xl flex items-center justify-center mb-4">
            <MessageSquare size={28} />
          </div>
          <h3 className="text-lg font-semibold mb-2 text-gray-800 dark:text-slate-100">智能问答</h3>
          <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">
            基于多路混合检索 (Dense + BM25 + HyDE + 网络搜索)，经 RRF 融合与 gte-rerank 重排后，由 Qwen-Plus 流式生成精准回答。
          </p>
          <div className="mt-4 text-sm text-indigo-600 dark:text-indigo-400 font-medium flex items-center gap-1">
            开始问答 <Zap size={14} />
          </div>
        </div>
      </div>

      {/* 流程概览 */}
      <div className="surface rounded-xl shadow-sm p-6 transition-colors">
        <h3 className="text-base font-semibold mb-5 text-gray-800 dark:text-slate-100">检索流程概览</h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {pipelineSteps.map((step, i) => (
            <div key={step} className="flex items-center gap-2 flex-shrink-0">
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center text-sm font-bold">
                  {i + 1}
                </div>
                <span className="text-xs text-gray-500 dark:text-slate-400 whitespace-nowrap">{step}</span>
              </div>
              {i < pipelineSteps.length - 1 && (
                <div className="w-8 h-0.5 bg-gray-200 dark:bg-slate-700 mb-6" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
