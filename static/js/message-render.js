// static/js/message-render.js
//
// 메시지를 DOM으로 조립한다.
// 모델 출력은 전부 textContent 로만 들어가고, 코드 블록·표도 DOM API 로 만든다.
// 이 파일에 innerHTML 은 한 번도 안 나온다.


// ── 스크롤 고정 ──────────────────────────────────────────
//
// "사용자가 바닥 근처에 있으면 새 내용이 와도 계속 바닥에 붙이고,
//  위로 올려 옛 내용을 보고 있으면 건드리지 않는다."
//
// 무조건 scrollTop = scrollHeight 로 끌어내리면, 스트리밍 중 위를 볼 수 없다.
// 핵심은 판단 시점: 새 토큰이 들어와 scrollHeight 가 커진 *뒤에* 거리를 재면
// 방금 늘어난 만큼 항상 "바닥에서 멀어진" 걸로 나온다. 그래서 내용을 넣기 *전에*
// isNearBottom() 으로 판단하고, 넣은 *뒤에* 그 판단이 참이었을 때만 스크롤한다.

const SCROLL_STICK_THRESHOLD = 80; // 바닥에서 이 픽셀 이내면 "바닥에 있다"로 본다

function isNearBottom(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_STICK_THRESHOLD;
}

// 콘텐츠를 바꾸기 전에 스냅샷을 찍고, 바꾼 뒤 stick() 을 부른다.
//   const atBottom = scrollAnchor(chatBox);
//   ...DOM 변경...
//   atBottom.stick();
function scrollAnchor(el) {
    const wasNearBottom = isNearBottom(el);
    return {
        stick() {
            if (wasNearBottom) el.scrollTop = el.scrollHeight;
        },
    };
}

// 판단 없이 무조건 바닥으로 (세션 전환·전체 리렌더처럼 "방금 이 대화를 연" 경우).
function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}


function rerenderChat() {
    const chatBox = document.getElementById("chat-box");
    chatBox.replaceChildren();
    conversationHistory.forEach(m => renderMessage(m));
    scrollToBottom(chatBox);   // 대화를 새로 열면 항상 최신 메시지부터 보여준다
}

function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.textContent;
        btn.textContent = "복사됨";
        setTimeout(() => { btn.textContent = original; }, 1200);
    });
}


// ── 본문 파싱 ───────────────────────────────────────────────

function renderMessageContent(container, text) {
    container.replaceChildren();

    const blockRegex = /```(\w+)?\n([\s\S]*?)```|((?:^\|.+\|\s*$\n?)+)/gm;
    let lastIndex = 0;
    let match;

    while ((match = blockRegex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            appendPlainText(container, text.slice(lastIndex, match.index));
        }

        if (match[0].startsWith("```")) {
            appendCodeBlock(container, match[1] || "", match[2].replace(/\n$/, ""));
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
    copyBtn.textContent = "복사";
    copyBtn.addEventListener("click", () => copyText(code, copyBtn));   // 헬퍼 재사용

    header.append(langLabel, copyBtn);

    const pre = document.createElement("pre");
    const codeEl = document.createElement("code");
    codeEl.textContent = code;
    pre.appendChild(codeEl);

    wrapper.append(header, pre);
    container.appendChild(wrapper);
}

function appendTable(container, block) {
    const lines = block.trim().split("\n").map(l => l.trim());
    const parseCells = (line) => line.replace(/^\||\|$/g, "").split("|").map(c => c.trim());

    const table = document.createElement("table");
    table.className = "md-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    parseCells(lines[0]).forEach(cellText => {
        const th = document.createElement("th");
        th.textContent = cellText;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");
    lines.slice(2).forEach(line => {   // 0번 = 헤더, 1번 = 구분선(---)
        if (!line.startsWith("|")) return;
        const row = document.createElement("tr");
        parseCells(line).forEach(cellText => {
            const td = document.createElement("td");
            td.textContent = cellText;
            row.appendChild(td);
        });
        tbody.appendChild(row);
    });

    table.append(thead, tbody);
    container.appendChild(table);
}


// ── 말풍선 내부 구획 ────────────────────────────────────────

function ensureContentArea(bubble) {
    let area = bubble.querySelector(".content-area");
    if (!area) {
        area = document.createElement("div");
        area.className = "content-area";
        bubble.appendChild(area);
    }
    return area;
}

function ensureThinkingBlock(bubble) {
    let block = bubble.querySelector(".thinking-block");
    if (!block) {
        block = document.createElement("details");
        block.className = "thinking-block";
        block.open = true;

        const summary = document.createElement("summary");
        summary.textContent = "생각 중…";

        const textDiv = document.createElement("div");
        textDiv.className = "thinking-text";

        block.append(summary, textDiv);
        bubble.insertBefore(block, bubble.firstChild);
    }
    return block;
}


// ── 메시지 한 줄 ────────────────────────────────────────────

function botLabel() {
    const session = currentSession();
    const modelSelect = document.getElementById("model-select");
    const tag = session?.model || modelSelect?.value || "";
    return tag ? `Bot · ${nicknameFor(tag)}` : "Bot";
}

function renderMessage(msgObj) {
    const chatBox = document.getElementById("chat-box");
    const isUser = msgObj.role === "user";

    const row = document.createElement("div");
    row.className = `msg-row ${isUser ? "user" : "bot"}`;

    const nameLabel = document.createElement("div");
    nameLabel.className = "msg-name";
    nameLabel.textContent = isUser ? "나" : botLabel();

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    renderMessageContent(ensureContentArea(bubble), msgObj.content);

    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.textContent = "복사";
    // DOM 텍스트가 아니라 원본 문자열을 복사한다.
    // 이전엔 bubble.textContent 를 긁었는데, 거기엔 코드 블록 헤더의 "python" / "복사"
    // 같은 UI 텍스트와 thinking 본문까지 딸려 들어갔다.
    copyBtn.addEventListener("click", () => copyText(msgObj.content, copyBtn));
    actions.appendChild(copyBtn);

    if (isUser) {
        const editBtn = document.createElement("button");
        editBtn.type = "button";
        editBtn.textContent = "수정";
        editBtn.addEventListener("click", () => startEdit(msgObj, row, bubble));
        actions.appendChild(editBtn);
    } else {
        const retryBtn = document.createElement("button");
        retryBtn.type = "button";
        retryBtn.textContent = "재생성";
        retryBtn.addEventListener("click", () => retryFrom(msgObj));
        actions.appendChild(retryBtn);
    }

    row.append(nameLabel, bubble, actions);
    const atBottom = scrollAnchor(chatBox);
    chatBox.appendChild(row);
    atBottom.stick();

    return { row, bubble, actions };
}


// ── 추론 메트릭 ─────────────────────────────────────────────
//
// Ollama의 done 청크에 들어있던 지표. 지금까지는 통째로 버려지고 있었다.
// prompt_tokens 는 모델이 자기 토크나이저로 실제로 센 값이라, 화면에 띄우는 동시에
// 서버의 토큰 추정기를 보정하는 데도 쓰인다.

function renderStats(row, stats) {
    row.querySelector(".msg-stats")?.remove();

    const parts = [];
    if (stats.ttft_ms != null) parts.push(`첫 토큰 ${stats.ttft_ms}ms`);
    if (stats.tokens_per_sec != null) parts.push(`${stats.tokens_per_sec} tok/s`);
    if (stats.output_tokens) parts.push(`출력 ${stats.output_tokens}`);
    if (stats.prompt_tokens) parts.push(`입력 ${stats.prompt_tokens}`);
    if (!parts.length) return;

    const el = document.createElement("div");
    el.className = "msg-stats";
    el.textContent = parts.join("  ·  ");
    row.appendChild(el);
}

// 에러는 메시지가 아니다. 말풍선인 척하면 안 된다.
function renderNotice(text) {
    const chatBox = document.getElementById("chat-box");
    const notice = document.createElement("div");
    notice.className = "notice";
    notice.textContent = text;
    const atBottom = scrollAnchor(chatBox);
    chatBox.appendChild(notice);
    atBottom.stick();
}