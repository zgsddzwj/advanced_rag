import { useNavigate } from 'react-router-dom'
import { Upload, MessageSquare, Cpu, FileStack, Search, Layers, Bot, Zap } from 'lucide-react'

const stats = [
  { icon: Bot, label: 'AI 模型接入', value: '5', color: 'bg-blue-50 text-blue-600' },
  { icon: FileStack, label: '导入流程节点', value: '7', color: 'bg-amber-50 text-amber-600' },
  { icon: Search, label: '检索流程节点', value: '7', color: 'bg-green-50 text-green-600' },
  { icon: Layers, label: '多路检索融合', value: '3', color: 'bg-purple-50 text-purple-600' },
]

const pipelineSteps = [
  '商品名确认', '向量检索', 'HyDE 检索', '网络搜索', 'RRF 融合', 'Rerank 重排', '流式回答',
]

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <div className="p-8 space-y-6">
      {/* Hero */}
      <div className="bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-10 text-white relative overflow-hidden">
        <div className="relative z-10">
          <h1 className="text-3xl font-bold mb-2">📚 掌柜智库 — 高级 RAG 系统</h1>
          <p className="text-white/80">基于 LangGraph 编排 · 混合检索 (Dense + BM25) · 阿里云百炼 AI 全链路接入</p>
        </div>
        <div className="absolute -top-20 -right-10 w-80 h-80 bg-white/10 rounded-full" />
        <div className="absolute -bottom-16 right-32 w-48 h-48 bg-white/5 rounded-full" />
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-5">
        {stats.map(s => {
          const Icon = s.icon
          return (
            <div key={s.label} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-3 ${s.color}`}>
                <Icon size={24} />
              </div>
              <div className="text-2xl font-bold text-gray-800">{s.value}</div>
              <div className="text-sm text-gray-500 mt-1">{s.label}</div>
            </div>
          )
        })}
      </div>

      {/* 功能入口 */}
      <div className="grid grid-cols-2 gap-5">
        <div
          onClick={() => navigate('/import')}
          className="bg-white rounded-xl shadow-sm p-8 border-2 border-transparent hover:border-indigo-400 hover:shadow-md cursor-pointer transition-all"
        >
          <div className="w-14 h-14 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4">
            <Upload size={28} />
          </div>
          <h3 className="text-lg font-semibold mb-2">知识库导入</h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            上传 PDF 或 Markdown 文档，系统自动完成 PDF 解析、图片 VLM 描述、文档切分、商品名识别、向量化并存入 Milvus 向量数据库。
          </p>
          <div className="mt-4 text-sm text-indigo-600 font-medium flex items-center gap-1">
            前往导入 <Zap size={14} />
          </div>
        </div>

        <div
          onClick={() => navigate('/chat')}
          className="bg-white rounded-xl shadow-sm p-8 border-2 border-transparent hover:border-indigo-400 hover:shadow-md cursor-pointer transition-all"
        >
          <div className="w-14 h-14 bg-green-50 text-green-600 rounded-xl flex items-center justify-center mb-4">
            <MessageSquare size={28} />
          </div>
          <h3 className="text-lg font-semibold mb-2">智能问答</h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            基于多路混合检索 (Dense + BM25 + HyDE + 网络搜索)，经 RRF 融合与 gte-rerank 重排后，由 Qwen-Plus 流式生成精准回答。
          </p>
          <div className="mt-4 text-sm text-indigo-600 font-medium flex items-center gap-1">
            开始问答 <Zap size={14} />
          </div>
        </div>
      </div>

      {/* 流程概览 */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-base font-semibold mb-5 text-gray-800">检索流程概览</h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {pipelineSteps.map((step, i) => (
            <div key={step} className="flex items-center gap-2 flex-shrink-0">
              <div className="flex flex-col items-center gap-2">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center text-sm font-bold">
                  {i + 1}
                </div>
                <span className="text-xs text-gray-500 whitespace-nowrap">{step}</span>
              </div>
              {i < pipelineSteps.length - 1 && (
                <div className="w-8 h-0.5 bg-gray-200 mb-6" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
