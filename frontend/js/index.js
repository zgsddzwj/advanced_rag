/**
 * 首页逻辑
 * 健康检查 + 服务状态显示
 */
(async function() {
    // 健康检查
    try {
        const data = await API.health();
        const footer = document.getElementById('footerStatus');
        if (data.status === 'ok') {
            footer.textContent = '服务运行中';
        } else {
            footer.textContent = '服务异常';
        }
    } catch (e) {
        const footer = document.getElementById('footerStatus');
        const dot = document.querySelector('.sidebar-footer .status-dot');
        footer.textContent = '服务离线';
        if (dot) dot.style.background = 'var(--error)';
    }
})();
