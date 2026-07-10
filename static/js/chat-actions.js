// static/js/chat-actions.js
// 메시지 수정, 재시도, /chat NDJSON 스트리밍 호출 (thinking 지원)

function startEdit(msgObj, row, bubble) {
    const idx = conversationHistory.indexOf(msgObj);
    if (idx === -1) { alert("너무 오래된 메시지라 수정할 수 없어요."); return; }

    const actionsDiv = row.querySelector(".msg-actions");
    const editInput = document.createElement("input");
    editInput.type = "text";
    editInput.className = "edit-input";
    editInput.value = msgObj.content;

    bubble.replaceWith(editInput);
    actionsDiv.style.display = "none";
    editInput.focus();

    editInput.addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
            const newText = editInput.value.trim();
            if (!newText) return;

            conversationHistory = conversationHistory.slice(0, idx);
            removeRowsAfter(row);

            msgObj.content = newText;
            conversationHistory.push(msgObj);
            persistCurrentMessages();

            const contentArea = ensureContentArea(bubble);
            renderMessageContent(contentArea, newText);
            editInput.replaceWith(bubble);
            actionsDiv.style.display = "";

            await requestReply();
        } else if (e.key === "Escape") {
            editInput.replaceWith(bubble);
            actionsDiv.style.display = "";
        }
    });
}

async function retryFrom(msgObj, row) {
    const idx = conversationHistory.indexOf(msgObj);
    if (idx === -1) { alert("너무 오래된 메시지라 재시도할 수 없어요."); return; }

    conversationHistory = conversationHistory.slice(0, idx);
    document.getElementById("chat-box").removeChild(row);

    await requestReply();
}

// bubble 안의 실제 답변 영역(content-area)을 가져오거나 새로 만듦
function ensureContentArea(bubble) {
    let contentArea = bubble.querySelector(".content-area");
    if (!contentArea) {
        contentArea = document.createElement("div");
        contentArea.className = "content-area";
        bubble.appendChild(contentArea);
    }
    return contentArea;
}

// bubble 안의 생각 과정(thinking-block)을 가져오거나 새로 만듦
function ensureThinkingBlock(bubble) {
    let block = bubble.querySelector(".thinking-block");
    if (!block) {
        block = document.createElement("details");
        block.className = "thinking-block";
        block.open = true;

        const summary = document.createElement("summary");
        summary.textContent = "🤔 생각 중...";

        const textDiv = document.createElement("div");
        textDiv.className = "thinking-text";

        block.appendChild(summary);
        block.appendChild(textDiv);
        bubble.insertBefore(block, bubble.firstChild);
    }
    return block;
}

async function requestReply() {
    const input = document.getElementById("message-input");
    const submitButton = document.querySelector(".send-btn");
    const thinkChecked = document.getElementById("think-checkbox").checked;

    input.disabled = true;
    submitButton.disabled = true;

    const placeholderObj = { role: "assistant", content: "" };
    const { bubble, actions } = renderMessage(placeholderObj);
    actions.style.display = "none";
    bubble.innerHTML = '<span class="typing-dots">●●●</span>';

    const chatBox = document.getElementById("chat-box");
    let fullText = "";
    let thinkingText = "";
    let firstChunk = true;
    let errored = false;

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                model: document.getElementById("model-select").value,
                messages: conversationHistory,
                think: thinkChecked,
            }),
        });

        if (!res.ok || !res.body) {
            throw new Error(`서버 오류 (status ${res.status}). 잠시 후 다시 시도해주세요.`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // 마지막 미완성 줄은 다음 루프까지 보관

            for (const line of lines) {
                if (!line.trim()) continue;
                let evt;
                try { evt = JSON.parse(line); } catch { continue; }

                if (firstChunk) {
                    bubble.innerHTML = "";
                    firstChunk = false;
                }

                if (evt.type === "error") {
                    errored = true;
                    const contentArea = ensureContentArea(bubble);
                    renderMessageContent(contentArea, "⚠️ " + evt.text);
                } else if (evt.type === "thinking") {
                    thinkingText += evt.text;
                    const block = ensureThinkingBlock(bubble);
                    block.querySelector(".thinking-text").textContent = thinkingText;
                } else if (evt.type === "content") {
                    // 실제 답변이 시작되면 생각 블록은 접어서 정리
                    const block = bubble.querySelector(".thinking-block");
                    if (block && block.open) {
                        block.open = false;
                        block.querySelector("summary").textContent = "🤔 생각 과정 보기";
                    }
                    fullText += evt.text;
                    const contentArea = ensureContentArea(bubble);
                    renderMessageContent(contentArea, fullText);
                }

                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }

        if (!errored) {
            placeholderObj.content = fullText;
            conversationHistory.push(placeholderObj);

            if (conversationHistory.length > MAX_HISTORY) {
                conversationHistory = conversationHistory.slice(-MAX_HISTORY);
            }

            actions.style.display = "";
            persistCurrentMessages();
        }
    } catch (err) {
        const contentArea = ensureContentArea(bubble);
        renderMessageContent(contentArea, "⚠️ " + err.message);
    } finally {
        input.disabled = false;
        submitButton.disabled = false;
        input.focus();
    }
}