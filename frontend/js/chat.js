/**
 * 智能问答页面逻辑
 * 提交查询 → SSE 流式接收 → 渲染回答
 */
let sessionId = localStorage.getItem('kb_session_id') || '';
let isWaiting = false;

const chatContainer = document.getElementById('chatContainer');
const welcomeScreen = document.getElementById('welcomeScreen');
const queryInput = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
const sessionInfo = document.getElementById('sessionInfo');

// 回车发送
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQuery();
    }
});

// 页面加载时恢复历史
window.onload = async function() {
    updateSessionInfo();
    if (sessionId) {
        await loadHistory(sessionId);
    }
};

function updateSessionInfo() {
    sessionInfo.textContent = sessionId ? `Session: ${sessionId}` : '';
}

// ==================== 历史记录 ====================

async function loadHistory(sid) {
    try {
        const data = await API.getHistory(sid);
        if (data.messages && data.messages.length > 0) {
            hideWelcome();
            data.messages.forEach(msg => {
                appendMessage(msg.role, msg.text, msg.image_urls || [], msg.item_names || []);
            });
        }
    } catch (e) {
        console.error('加载历史失败:', e);
    }
}

// ==================== 新建对话 ====================

function newSession() {
    sessionId = '';
    localStorage.removeItem('kb_session_id');
    updateSessionInfo();
    showWelcome();
}

// ==================== 快速提问 ====================

function quickAsk(question) {
    queryInput.value = question;
    sendQuery();
}

// ==================== 发送查询 ====================

async function sendQuery() {
    const query = queryInput.value.trim();
    if (!query || isWaiting) return;

    isWaiting = true;
    sendBtn.disabled = true;
    queryInput.value = '';

    hideWelcome();
    appendMessage('user', query);
    showTypingIndicator();

    try {
        const data = await API.ask(query, sessionId);
        sessionId = data.session_id;
        localStorage.setItem('kb_session_id', sessionId);
        updateSessionInfo();

        await listenStream(data.task_id);
    } catch (e) {
        removeTypingIndicator();
        appendMessage('assistant', '⚠️ 网络错误，请稍后重试');
    } finally {
        isWaiting = false;
        sendBtn.disabled = false;
    }
}

// ==================== SSE 流式监听 ====================

function listenStream(taskId) {
    return new Promise((resolve) => {
        let assistantDiv = null;
        let answerText = '';

        API.listenStream(taskId, {
            onReady(data) {
                // SSE 连接已建立
            },
            onDelta(data) {
                removeTypingIndicator();
                if (!assistantDiv) {
                    assistantDiv = appendMessage('assistant', '');
                }
                answerText += data.text;
                assistantDiv.querySelector('.text-content').textContent = answerText;
                scrollBottom();
            },
            onFinal(data) {
                removeTypingIndicator();
                const finalText = data.answer || answerText;
                if (!assistantDiv) {
                    assistantDiv = appendMessage('assistant', finalText);
                } else {
                    assistantDiv.querySelector('.text-content').textContent = finalText;
                }

                // 显示图片
                if (data.image_urls && data.image_urls.length > 0) {
                    const imgBox = document.createElement('div');
                    imgBox.style.marginTop = '10px';
                    data.image_urls.forEach(url => {
                        const img = document.createElement('img');
                        img.src = url;
                        imgBox.appendChild(img);
                    });
                    assistantDiv.appendChild(imgBox);
                }

                // 显示商品名标签
                if (data.item_names && data.item_names.length > 0) {
                    const tagBox = document.createElement('div');
                    tagBox.className = 'item-names';
                    tagBox.innerHTML = '🏷️ ' + data.item_names
                        .map(n => `<span class="tag">${n}</span>`).join('');
                    assistantDiv.appendChild(tagBox);
                }

                scrollBottom();
                resolve();
            },
            onError(data) {
                removeTypingIndicator();
                if (!assistantDiv) {
                    appendMessage('assistant', `⚠️ ${data.message || '生成回答时出现错误'}`);
                }
                resolve();
            },
        });
    });
}

// ==================== DOM 辅助 ====================

function appendMessage(role, text, imageUrls = [], itemNames = []) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const textSpan = document.createElement('span');
    textSpan.className = 'text-content';
    textSpan.textContent = text;
    div.appendChild(textSpan);

    if (imageUrls && imageUrls.length > 0) {
        imageUrls.forEach(url => {
            const img = document.createElement('img');
            img.src = url;
            div.appendChild(img);
        });
    }

    if (itemNames && itemNames.length > 0) {
        const tagBox = document.createElement('div');
        tagBox.className = 'item-names';
        tagBox.innerHTML = '🏷️ ' + itemNames
            .map(n => `<span class="tag">${n}</span>`).join('');
        div.appendChild(tagBox);
    }

    chatContainer.appendChild(div);
    scrollBottom();
    return div;
}

function showTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.id = 'typingIndicator';
    div.innerHTML = '<span></span><span></span><span></span>';
    chatContainer.appendChild(div);
    scrollBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

function hideWelcome() {
    if (welcomeScreen) welcomeScreen.style.display = 'none';
}

function showWelcome() {
    chatContainer.innerHTML = '';
    // 重建欢迎页
    const welcome = document.createElement('div');
    welcome.className = 'welcome-screen';
    welcome.id = 'welcomeScreen';
    welcome.innerHTML = `
        <div class="welcome-icon">💬</div>
        <div class="welcome-title">欢迎使用掌柜智库</div>
        <div class="welcome-desc">基于多路混合检索 (Dense + BM25 + HyDE + 网络搜索)，为您提供精准的智能问答服务。</div>
        <div class="suggestions">
            <div class="suggestion-chip" onclick="quickAsk('这个产品的使用方法是什么？')">📋 产品使用方法</div>
            <div class="suggestion-chip" onclick="quickAsk('设备的技术参数有哪些？')">⚙️ 设备技术参数</div>
            <div class="suggestion-chip" onclick="quickAsk('常见的故障及排除方法？')">🔧 故障排除</div>
        </div>
    `;
    chatContainer.appendChild(welcome);
}

function scrollBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
