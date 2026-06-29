/**
 * 知识库导入页面逻辑
 * 文件上传 → 进度轮询 → 结果展示
 */
let selectedFile = null;
let pollTimer = null;

const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const fileCardContainer = document.getElementById('fileCardContainer');
const uploadBtn = document.getElementById('uploadBtn');
const resetBtn = document.getElementById('resetBtn');

// ==================== 文件选择 ====================

uploadZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) selectFile(e.target.files[0]);
});

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
});

function selectFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'md'].includes(ext)) {
        alert('仅支持 PDF 或 Markdown 文件');
        return;
    }
    selectedFile = file;
    renderFileCard(file);
    uploadBtn.disabled = false;
}

function renderFileCard(file) {
    const sizeStr = file.size > 1024 * 1024
        ? (file.size / 1024 / 1024).toFixed(1) + ' MB'
        : (file.size / 1024).toFixed(0) + ' KB';
    fileCardContainer.innerHTML = `
        <div class="file-card">
            <div class="file-icon">${file.name.endsWith('.pdf') ? '📕' : '📝'}</div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${sizeStr}</div>
            </div>
            <div class="file-remove" onclick="clearFile()">✕</div>
        </div>
    `;
}

function clearFile() {
    selectedFile = null;
    fileInput.value = '';
    fileCardContainer.innerHTML = '';
    uploadBtn.disabled = true;
}

// ==================== 渲染节点列表 ====================

function renderNodes(doneList = [], runningList = [], failed = false) {
    const nodeList = document.getElementById('nodeList');
    nodeList.innerHTML = CONFIG.IMPORT_NODES.map(node => {
        let status = 'pending', statusText = '等待中', statusIcon = '⏳';
        if (failed && !doneList.includes(node.id) && !runningList.includes(node.id)) {
            // 如果整体失败，正在运行的节点标记为失败
        }
        if (doneList.includes(node.id)) {
            status = 'done'; statusText = '已完成'; statusIcon = '✅';
        } else if (runningList.includes(node.id)) {
            status = 'running'; statusText = '执行中'; statusIcon = '<span class="spinner"></span>';
        } else if (failed) {
            status = 'failed'; statusText = '未执行'; statusIcon = '⏭️';
        }

        // 计算进度
        const total = CONFIG.IMPORT_NODES.length;
        const completed = doneList.length;
        const percent = Math.round((completed / total) * 100);
        document.getElementById('progressPercent').textContent = percent + '%';
        document.getElementById('progressBarFill').style.width = percent + '%';

        return `
            <div class="node-item ${status}">
                <div class="node-icon">${node.icon}</div>
                <div class="node-content">
                    <div class="node-label">${node.label}</div>
                    <div class="node-id">${node.id}</div>
                </div>
                <div class="node-status ${status}">${statusIcon} ${statusText}</div>
            </div>
        `;
    }).join('');
}

// ==================== 开始导入 ====================

async function startImport() {
    if (!selectedFile) return;
    uploadBtn.disabled = true;
    uploadBtn.textContent = '导入中...';

    try {
        const data = await API.uploadFile(selectedFile);
        if (data.task_id) {
            document.getElementById('importProgress').classList.add('show');
            renderNodes([], []);
            pollStatus(data.task_id);
        }
    } catch (e) {
        showResult('error', `上传失败: ${e.message}`);
        uploadBtn.disabled = false;
        uploadBtn.textContent = '🚀 开始导入';
    }
}

// ==================== 轮询状态 ====================

function pollStatus(taskId) {
    pollTimer = setInterval(async () => {
        try {
            const data = await API.getImportStatus(taskId);
            renderNodes(data.done_list || [], data.running_list || [], data.status === 'failed');

            if (data.status === 'completed') {
                clearInterval(pollTimer);
                uploadBtn.style.display = 'none';
                resetBtn.style.display = 'inline-flex';
                showResult('success', `✅ 导入完成！文件 "${selectedFile.name}" 已成功写入知识库。`);
            } else if (data.status === 'failed') {
                clearInterval(pollTimer);
                uploadBtn.style.display = 'none';
                resetBtn.style.display = 'inline-flex';
                showResult('error', '❌ 导入失败，请检查日志或重试。');
            }
        } catch (e) {
            console.error('轮询失败:', e);
        }
    }, CONFIG.POLL_INTERVAL);
}

// ==================== 结果横幅 ====================

function showResult(type, message) {
    const banner = document.getElementById('resultBanner');
    banner.className = `result-banner show ${type}`;
    banner.textContent = message;
}

// ==================== 重置 ====================

function resetAll() {
    clearFile();
    document.getElementById('importProgress').classList.remove('show');
    document.getElementById('resultBanner').className = 'result-banner';
    uploadBtn.style.display = 'inline-flex';
    uploadBtn.textContent = '🚀 开始导入';
    uploadBtn.disabled = true;
    resetBtn.style.display = 'none';
}
