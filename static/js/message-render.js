// static/js/message-render.js
// 채팅 메시지를 DOM에 렌더링 (코드 블록 감지 포함)

function rerenderChat() {
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";
    conversationHistory.forEach(m => renderMessage(m));
}

function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.textContent;
        btn.textContent = "✅";
        setTimeout(() => { btn.textContent = original; }, 1200);
    });
}

// ```lang\n코드\n``` 패턴을 찾아서 일반 텍스트와 코드 블록을 분리 렌더링
function renderMessageContent(bubble, text) {
    bubble.innerHTML = "";
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;

    while ((match = codeBlockRegex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            appendPlainText(bubble, text.slice(lastIndex, match.index));
        }
        const lang = match[1] || "";
        const code = match[2].replace(/\n$/, "");
        appendCodeBlock(bubble, lang, code);
        lastIndex = codeBlockRegex.lastIndex;
    }

    if (lastIndex < text.length) {
        appendPlainText(bubble, text.slice(lastIndex));
    }
}

function appendPlainText(bubble, text) {
    if (!text) return;
    const span = document.createElement("span");
    span.className = "plain-text";
    span.textContent = text;
    bubble.appendChild(span);
}

function appendCodeBlock(bubble, lang, code) {
    const wrapper = document.createElement("div");
    wrapper.className = "code-block";

    const header = document.createElement("div");
    header.className = "code-block-header";

    const langLabel = document.createElement("span");
    langLabel.className = "code-lang";
    langLabel.textContent = lang || "code";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "code-copy-btn";
    copyBtn.textContent = "📋 복사";
    copyBtn.onclick = () => {
        navigator.clipboard.writeText(code).then(() => {
            const original = copyBtn.textContent;
            copyBtn.textContent = "✅ 복사됨";
            setTimeout(() => { copyBtn.textContent = original; }, 1200);
        });
    };

    header.appendChild(langLabel);
    header.appendChild(copyBtn);

    const pre = document.createElement("pre");
    const codeEl = document.createElement("code");
    codeEl.textContent = code;
    pre.appendChild(codeEl);

    wrapper.appendChild(header);
    wrapper.appendChild(pre);
    bubble.appendChild(wrapper);
}

function renderMessage(msgObj) {
    const chatBox = document.getElementById("chat-box");
    const row = document.createElement("div");
    row.className = `msg-row ${msgObj.role === "user" ? "user" : "bot"}`;

    const nameLabel = document.createElement("div");
    nameLabel.className = "msg-name";
    nameLabel.textContent = msgObj.role === "user" ? "🧑 나" : "🤖 " + nicknameFor(currentSession().model);

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    renderMessageContent(bubble, msgObj.content);

    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "📋";
    copyBtn.title = "전체 복사";
    copyBtn.onclick = () => copyText(bubble.textContent, copyBtn);
    actions.appendChild(copyBtn);

    if (msgObj.role === "user") {
        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.textContent = "✏️";
        editBtn.title = "수정";
        editBtn.onclick = () => startEdit(msgObj, row, bubble);
        actions.appendChild(editBtn);
    } else {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.textContent = "🔁";
        retryBtn.title = "재시도";
        retryBtn.onclick = () => retryFrom(msgObj, row);
        actions.appendChild(retryBtn);
    }

    row.appendChild(nameLabel);
    row.appendChild(bubble);
    row.appendChild(actions);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;

    return { row, bubble, actions };
}

function removeRowsAfter(row) {
    const chatBox = document.getElementById("chat-box");
    let sibling = row.nextSibling;
    while (sibling) {
        const next = sibling.nextSibling;
        chatBox.removeChild(sibling);
        sibling = next;
    }
}