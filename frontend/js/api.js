/**
 * API 封装层
 * 统一处理后端 API 调用
 */
const API = {

    // ==================== 导入服务 ====================

    /**
     * 上传文件并触发导入
     * @param {File} file
     * @returns {Promise<{task_id, filename, status}>}
     */
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        const resp = await fetch(CONFIG.ENDPOINTS.IMPORT_UPLOAD, {
            method: 'POST',
            body: formData,
        });
        if (!resp.ok) throw new Error(`上传失败: ${resp.status}`);
        return resp.json();
    },

    /**
     * 轮询导入状态
     * @param {string} taskId
     * @returns {Promise<{task_id, status, done_list, running_list}>}
     */
    async getImportStatus(taskId) {
        const resp = await fetch(CONFIG.ENDPOINTS.IMPORT_STATUS(taskId));
        if (!resp.ok) throw new Error(`查询状态失败: ${resp.status}`);
        return resp.json();
    },

    // ==================== 查询服务 ====================

    /**
     * 提交查询
     * @param {string} query
     * @param {string} sessionId
     * @returns {Promise<{session_id, task_id, status}>}
     */
    async ask(query, sessionId = '') {
        const resp = await fetch(CONFIG.ENDPOINTS.QUERY_ASK, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, session_id: sessionId }),
        });
        if (!resp.ok) throw new Error(`查询失败: ${resp.status}`);
        return resp.json();
    },

    /**
     * 建立 SSE 连接接收流式回答
     * @param {string} taskId
     * @param {object} handlers - { onReady, onDelta, onFinal, onError }
     * @returns {EventSource}
     */
    listenStream(taskId, handlers = {}) {
        const es = new EventSource(CONFIG.ENDPOINTS.QUERY_STREAM(taskId));

        es.addEventListener('ready', (e) => {
            if (handlers.onReady) handlers.onReady(JSON.parse(e.data));
        });

        es.addEventListener('delta', (e) => {
            if (handlers.onDelta) handlers.onDelta(JSON.parse(e.data));
        });

        es.addEventListener('final', (e) => {
            const data = JSON.parse(e.data);
            if (handlers.onFinal) handlers.onFinal(data);
            es.close();
        });

        es.addEventListener('error', (e) => {
            // EventSource 在连接关闭时也会触发 error
            if (es.readyState === EventSource.CLOSED) {
                if (handlers.onError) handlers.onError({ message: '连接已关闭' });
            } else {
                if (handlers.onError) handlers.onError({ message: 'SSE 连接错误' });
            }
            es.close();
        });

        return es;
    },

    /**
     * 获取对话历史
     * @param {string} sessionId
     * @returns {Promise<{session_id, messages}>}
     */
    async getHistory(sessionId) {
        const resp = await fetch(CONFIG.ENDPOINTS.QUERY_HISTORY(sessionId));
        if (!resp.ok) throw new Error(`获取历史失败: ${resp.status}`);
        return resp.json();
    },

    /**
     * 清空对话历史
     * @param {string} sessionId
     * @returns {Promise<{session_id, deleted}>}
     */
    async clearHistory(sessionId) {
        const resp = await fetch(CONFIG.ENDPOINTS.QUERY_DEL_HIST(sessionId), { method: 'DELETE' });
        if (!resp.ok) throw new Error(`清空历史失败: ${resp.status}`);
        return resp.json();
    },

    /**
     * 健康检查
     * @returns {Promise<{status, service}>}
     */
    async health() {
        const resp = await fetch(CONFIG.ENDPOINTS.QUERY_HEALTH);
        if (!resp.ok) throw new Error(`健康检查失败: ${resp.status}`);
        return resp.json();
    },
};
