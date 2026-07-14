// static/js/message-render.js
// 채팅 메시지를 DOM에 렌더링 (코드 블록 + 마크다운 테이블 지원)

function rerenderChat() {
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";
    conversationHistory.forEach(m => renderMessage(m));
}

function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => { btn.textContent = original; }, 1200);
    });
}

function renderMessageContent(container, text) {
    container.innerHTML = "";
    const blockRegex = /```(\w+)?\n([\s\S]*?)```|((?:^\|.+\|\s*$\n?)+)/gm;
    let lastIndex = 0;
    let match;

    while ((match = blockRegex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            appendPlainText(container, text.slice(lastIndex, match.index));
        }

        if (match[0].startsWith("```")) {
            const lang = match[1] || "";
            const code = match[2].replace(/\n$/, "");
            appendCodeBlock(container, lang, code);
        } else if (isMarkdownTable(match[3])) {
            appendTable(container, match[3]);
        } else {
            appendPlainText(container, match[0]);
        }

        lastIndex = blockRegex.lastIndex;
    }

    if (lastIndex < text.length) {
        appendPlainText(container, text.slice(lastIndex));
    }
}

function isMarkdownTable(block) {
    if (!block) return false;
    const lines = block.trim().split("\n");
    return lines.length >= 2 && /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(lines[1].trim());
}

function appendTable(container, block) {
    const lines = block.trim().split("\n").map(l => l.trim());
    const parseCells = (line) => line.replace(/^\||\|$/g, "").split("|").map(c => c.trim());

    const headerCells = parseCells(lines[0]);
    const bodyLines = lines.slice(2);

    const table = document.createElement("table");
    table.className = "md-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headerCells.forEach(cellText => {
        const th = document.createElement("th");
        th.textContent = cellText;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    bodyLines.forEach(line => {
        if (!line.startsWith("|")) return;
        const row = document.createElement("tr");
        parseCells(line).forEach(cellText => {
            const td = document.createElement("td");
            td.textContent = cellText;
            row.appendChild(td);
        });
        tbody.appendChild(row);
    });
    table.appendChild(tbody);

    container.appendChild(table);
}

function appendPlainText(container, text) {
    if (!text) return;
    const span = document.createElement("span");
    span.className = "plain-text";
    span.textContent = text;
    container.appendChild(span);
}

function appendCodeBlock(container, lang, code) {
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
    copyBtn.textContent = "Copy";
    copyBtn.onclick = () => {
        navigator.clipboard.writeText(code).then(() => {
            const original = copyBtn.textContent;
            copyBtn.textContent = "Copied";
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
    container.appendChild(wrapper);
}

function ensureContentArea(bubble) {
    let contentArea = bubble.querySelector(".content-area");
    if (!contentArea) {
        contentArea = document.createElement("div");
        contentArea.className = "content-area";
        bubble.appendChild(contentArea);
    }
    return contentArea;
}

function ensureThinkingBlock(bubble) {
    let block = bubble.querySelector(".thinking-block");
    if (!block) {
        block = document.createElement("details");
        block.className = "thinking-block";
        block.open = true;

        const summary = document.createElement("summary");
        summary.textContent = "Thinking...";

        const textDiv = document.createElement("div");
        textDiv.className = "thinking-text";

        block.appendChild(summary);
        block.appendChild(textDiv);
        bubble.insertBefore(block, bubble.firstChild);
    }
    return block;
}

function renderMessage(msgObj) {
    const chatBox = document.getElementById("chat-box");
    const row = document.createElement("div");
    row.className = `msg-row ${msgObj.role === "user" ? "user" : "bot"}`;

    const nameLabel = document.createElement("div");
    nameLabel.className = "msg-name";

    // 이모지 제거 + 안전한 모델 이름 표시 (Bug 1 방어)
    if (msgObj.role === "user") {
        nameLabel.textContent = "나";
    } else {
        const session = (typeof currentSession === "function") ? currentSession() : null;
        let modelName = "";

        if (session && session.model) {
            modelName = nicknameFor(session.model);
        } else {
            const modelSelect = document.getElementById("model-select");
            if (modelSelect && modelSelect.value) {
                modelName = nicknameFor(modelSelect.value);
            }
        }
        nameLabel.textContent = modelName ? `Bot · ${modelName}` : "Bot";
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    renderMessageContent(ensureContentArea(bubble), msgObj.content);

    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "Copy";
    copyBtn.title = "Copy";
    copyBtn.onclick = () => copyText(bubble.textContent, copyBtn);
    actions.appendChild(copyBtn);

    if (msgObj.role === "user") {
        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.textContent = "Edit";
        editBtn.title = "Edit";
        editBtn.onclick = () => startEdit(msgObj, row, bubble);
        actions.appendChild(editBtn);
    } else {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.textContent = "Retry";
        retryBtn.title = "Retry";
        retryBtn.onclick = () => retryFrom(msgObj);
        actions.appendChild(retryBtn);
    }

    row.appendChild(nameLabel);
    row.appendChild(bubble);
    row.appendChild(actions);
    chatBox.appendChild(row);
    chatBox.scrollTop = chatBox.scrollHeight;

    return { row, bubble, actions };
}