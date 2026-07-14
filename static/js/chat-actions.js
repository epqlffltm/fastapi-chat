// static/js/chat-actions.js

async function startEdit(msgObj, row, bubble) {
    const actionsDiv = row.querySelector(".msg-actions");
    const editInput = document.createElement("input");
    editInput.type = "text";
    editInput.className = "edit-input";
    editInput.value = msgObj.content;

    bubble.replaceWith(editInput);
    actionsDiv.style.display = "none";
    editInput.focus();

    editInput.addEventListener("keydown", async (event) => {
        if (event.key === "Enter") {
            const newText = editInput.value.trim();
            if (!newText) return;

            const res = await fetch(`/sessions/${currentSessionId}/messages/from/${msgObj.id}`, { method: "DELETE" });
            if (!res.ok) throw new Error("메시지를 수정하지 못했습니다.");
            await refreshCurrentMessages();
            await requestReply(newText, false);
        } else if (event.key === "Escape") {
            editInput.replaceWith(bubble);
            actionsDiv.style.display = "";
        }
    });
}

async function retryFrom(msgObj) {
    const res = await fetch(`/sessions/${currentSessionId}/messages/from/${msgObj.id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("응답을 다시 생성하지 못했습니다.");
    await refreshCurrentMessages();
    await requestReply(null, true);
}

async function requestReply(message, regenerate = false) {
    const input = document.getElementById("message-input");
    const submitButton = document.querySelector(".send-btn");
    const thinkChecked = document.getElementById("think-checkbox").checked;
    const chatBox = document.getElementById("chat-box");

    input.disabled = true;
    submitButton.disabled = true;

    if (!regenerate && message) {
        renderMessage({ id: null, role: "user", content: message });
    }

    const placeholderObj = { id: null, role: "assistant", content: "" };
    const { bubble, actions } = renderMessage(placeholderObj);
    actions.style.display = "none";
    bubble.innerHTML = '<span class="typing-dots">...</span>';

    let fullText = "";
    let thinkingText = "";
    let firstChunk = true;
    let errorMessage = null;

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: regenerate ? null : message,
                model: document.getElementById("model-select").value,
                think: thinkChecked,
                regenerate,
            }),
        });

        if (!res.ok || !res.body) {
            let detail = `서버 오류 (status ${res.status})`;
            try {
                const body = await res.json();
                detail = body.detail || detail;
            } catch {
                // JSON 오류 본문이 아닌 경우 기본 메시지를 사용한다.
            }
            throw new Error(detail);
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

                if (firstChunk) {
                    bubble.innerHTML = "";
                    firstChunk = false;
                }

                if (evt.type === "error") {
                    errorMessage = evt.text;
                } else if (evt.type === "thinking") {
                    thinkingText += evt.text;
                    const block = ensureThinkingBlock(bubble);
                    block.querySelector(".thinking-text").textContent = thinkingText;
                } else if (evt.type === "content") {
                    const block = bubble.querySelector(".thinking-block");
                    if (block?.open) {
                        block.open = false;
                        block.querySelector("summary").textContent = "생각 과정 보기";
                    }
                    fullText += evt.text;
                    renderMessageContent(ensureContentArea(bubble), fullText);
                }

                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
    } catch (err) {
        errorMessage = err.message;
    } finally {
        try {
            await refreshCurrentMessages();
            await refreshSessionList();
        } catch (syncError) {
            errorMessage = errorMessage || syncError.message;
        }

        if (errorMessage) {
            renderMessage({ id: null, role: "assistant", content: `오류: ${errorMessage}` });
        }

        input.disabled = false;
        submitButton.disabled = false;
        input.focus();
    }
}
