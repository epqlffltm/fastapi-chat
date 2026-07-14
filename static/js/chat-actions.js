// static/js/chat-actions.js
// 메시지 수정(Edit) / 재시도(Retry) 및 스트리밍 요청 처리

async function startEdit(msgObj, row, bubble) {
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

            // DB에서 해당 메시지 이후 모두 삭제 후 재생성
            await fetch(`/sessions/${currentSessionId}/messages/from/${msgObj.id}`, {
                method: "DELETE"
            });
            await requestReply(newText, false);
        } 
        else if (e.key === "Escape") {
            editInput.replaceWith(bubble);
            actionsDiv.style.display = "";
        }
    });
}

async function retryFrom(msgObj) {
    // 해당 메시지 이후 모두 삭제 후 재생성
    await fetch(`/sessions/${currentSessionId}/messages/from/${msgObj.id}`, {
        method: "DELETE"
    });
    await requestReply(null, true);
}

async function requestReply(message, regenerate = false) {
    const input = document.getElementById("message-input");
    const submitButton = document.querySelector(".send-btn");
    const thinkChecked = document.getElementById("think-checkbox").checked;
    const chatBox = document.getElementById("chat-box");

    input.disabled = true;
    submitButton.disabled = true;

    // 사용자 메시지 즉시 렌더링 (regenerate가 아닐 때만)
    if (!regenerate && message) {
        renderMessage({ id: null, role: "user", content: message });
    }

    // 어시스턴트 플레이스홀더 생성
    const placeholderObj = { id: null, role: "assistant", content: "" };
    const { bubble, actions } = renderMessage(placeholderObj);
    actions.style.display = "none";
    bubble.innerHTML = '<span class="typing-dots">●●●</span>';

    let fullText = "";
    let thinkingText = "";
    let firstChunk = true;
    let errored = false;

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: regenerate ? null : message,
                model: document.getElementById("model-select").value,
                think: thinkChecked,
                regenerate: regenerate,
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
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;

                let evt;
                try {
                    evt = JSON.parse(line);
                } catch {
                    continue;
                }

                // 첫 번째 청크가 오면 플레이스홀더 초기화
                if (firstChunk) {
                    bubble.innerHTML = "";
                    firstChunk = false;
                }

                if (evt.type === "error") {
                    errored = true;
                    renderMessageContent(ensureContentArea(bubble), "Warning: " + evt.text);
                } 
                else if (evt.type === "thinking") {
                    thinkingText += evt.text;
                    const block = ensureThinkingBlock(bubble);
                    block.querySelector(".thinking-text").textContent = thinkingText;
                } 
                else if (evt.type === "content") {
                    // Thinking 블록이 열려있으면 닫기
                    const thinkingBlock = bubble.querySelector(".thinking-block");
                    if (thinkingBlock && thinkingBlock.open) {
                        thinkingBlock.open = false;
                        thinkingBlock.querySelector("summary").textContent = "Thinking: 생각 과정 보기";
                    }
                    fullText += evt.text;
                    renderMessageContent(ensureContentArea(bubble), fullText);
                }

                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
    } 
    catch (err) {
        errored = true;
        renderMessageContent(ensureContentArea(bubble), "Warning: " + err.message);
    } 
    finally {
        // 에러가 없었을 때만 DB 기준으로 재동기화
        if (!errored) {
            await refreshCurrentMessages();
            await refreshSessionList();
        }
        input.disabled = false;
        submitButton.disabled = false;
        input.focus();
    }
}