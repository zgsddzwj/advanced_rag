/**
 * 全局配置
 * API 基础路径，前端通过相对路径访问后端 API
 */
const CONFIG = {
    API_BASE: '/api',
    ENDPOINTS: {
        // 导入服务
        IMPORT_UPLOAD:  '/api/import/upload',
        IMPORT_STATUS:  (taskId) => `/api/import/status/${taskId}`,
        // 查询服务
        QUERY_ASK:      '/api/query/ask',
        QUERY_STREAM:   (taskId) => `/api/query/stream/${taskId}`,
        QUERY_HISTORY:  (sid) => `/api/query/history/${sid}`,
        QUERY_DEL_HIST: (sid) => `/api/query/history/${sid}`,
        QUERY_HEALTH:   '/api/query/health',
        QUERY_STATUS:   (taskId) => `/api/query/status/${taskId}`,
    },
    // 导入流程节点定义
    IMPORT_NODES: [
        { id: 'node_entry',                 label: '入口判断',     icon: '🚪' },
        { id: 'node_pdf_to_md',             label: 'PDF转Markdown', icon: '📄' },
        { id: 'node_md_img',                label: '图片处理',     icon: '🖼️' },
        { id: 'node_document_split',        label: '文档切分',     icon: '✂️' },
        { id: 'node_item_name_recognition', label: '商品名识别',   icon: '🏷️' },
        { id: 'node_bge_embedding',         label: '向量化',       icon: '🔢' },
        { id: 'node_import_milvus',         label: '入库Milvus',   icon: '🗄️' },
    ],
    // 轮询间隔（毫秒）
    POLL_INTERVAL: 2000,
};
