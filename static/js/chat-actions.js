// static/js/chat-actions.js
//
// 스트리밍 요청 + 수정/재생성.

// 수정과 재생성은 둘 다 "DB에서 이 지점 이후를 지우고 다시 생성"이다.
// 서버에서 지웠으면 화면도 즉시 그 상태를 반영해야 한다. 이전엔 재동기화를
// 스트리밍이 끝난 뒤에 했기 때문에, 생성되는 내내 이미 삭제된 메시지가 화면에 남아 있었다.
async function truncateFrom(messageId) {
    await fetch(`/sessions/${currentSessionId}/messages/from/${messageId}`, { method: "DELETE" });
    await refreshCurrentMessages();
}


async function startEdit(msgObj, row, bubble) {
    const actionsDiv = row.querySelector(".msg-actions");

    const editInput = document.createElement("input");
    editInput.type = "text";
    editInput.className = "edit-input";
    editInput.value = msgObj.content;

    bubble.replaceWith(editInput);
    actionsDiv.style.display = "none";
    editInput.focus();

    let closed = false;
    const cancel = () => {
        if (closed) return;
        closed = true;
        editInput.replaceWith(bubble);
        actionsDiv.style.display = "";
    };

    editInput.addEventListener("blur", cancel);
    editInput.addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
            const newText = editInput.value.trim();
            if (!newText) return;

            closed = true;   // 곧 DOM이 통째로 갈리므로 blur의 cancel이 끼어들지 못하게
            await truncateFrom(msgObj.id);
            await requestReply(newText, false);
        } else if (e.key === "Escape") {
            cancel();
        }
    });
}


async function retryFrom(msgObj) {
    await truncateFrom(msgObj.id);
    await requestReply(null, true);
}


async function requestReply(message, regenerate = false) {
    const input = document.getElementById("message-input");
    const sendBtn = document.querySelector(".send-btn");
    const chatBox = document.getElementById("chat-box");
    const think = document.getElementById("think-checkbox").checked;

    input.disabled = true;
    sendBtn.disabled = true;

    if (!regenerate && message) {
        renderMessage({ id: null, role: "user", content: message });
    }

    const { bubble, actions } = renderMessage({ id: null, role: "assistant", content: "" });
    actions.style.display = "none";

    const dots = document.createElement("span");
    dots.className = "typing-dots";
    dots.textContent = "●●●";
    bubble.replaceChildren(dots);

    let fullText = "";
    let thinkingText = "";
    let firstChunk = true;
    let errorMessage = null;
    let stats = null;

    try {
        const res = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: regenerate ? null : message,
                model: document.getElementById("model-select").value,
                think: think,
                regenerate: regenerate,
            }),
        });

        if (!res.ok || !res.body) {
            const detail = await res.json().catch(() => null);
            throw new Error(detail?.detail ?? `서버 오류 (HTTP ${res.status})`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        stream: while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // NDJSON: 줄 하나가 JSON 하나. 청크 경계에서 잘린 마지막 줄은
            // 다음 청크가 올 때까지 buffer에 남겨둔다.
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;

                let evt;
                try { evt = JSON.parse(line); } catch { continue; }

                if (evt.type === "stats") {   // 스트림 마지막에 오는 추론 메트릭
                    stats = evt;
                    continue;
                }

                if (firstChunk) {
                    bubble.replaceChildren();
                    firstChunk = false;
                }

                if (evt.type === "error") {
                    errorMessage = evt.text;
                    break stream;
                }

                // 토큰을 넣기 전에 "바닥 근처였나"를 먼저 판단한다.
                // (넣은 뒤에 재면 방금 늘어난 높이 때문에 항상 멀어진 걸로 나온다.)
                const atBottom = scrollAnchor(chatBox);

                if (evt.type === "thinking") {
                    thinkingText += evt.text;
                    ensureThinkingBlock(bubble).querySelector(".thinking-text").textContent = thinkingText;
                } else if (evt.type === "content") {
                    const block = bubble.querySelector(".thinking-block");
                    if (block && block.open) {
                        block.open = false;
                        block.querySelector("summary").textContent = "생각 과정";
                    }
                    fullText += evt.text;
                    renderMessageContent(ensureContentArea(bubble), fullText);
                }

                atBottom.stick();   // 바닥 근처였을 때만 따라 내려간다
            }
        }
    } catch (err) {
        errorMessage = err.message;
    } finally {
        // 성공이든 실패든 항상 DB 기준으로 다시 그린다.
        //
        // 이전 버전은 에러가 나면 재동기화를 건너뛰었다(if (!errored)). 그런데 서버는
        // 토큰이 조금이라도 나왔으면 그 부분 응답을 저장한다 → 화면은 에러, DB엔 잘린 답변.
        // 다음 새로고침 때 없던 메시지가 튀어나오는 상태 불일치가 남았다.
        await refreshCurrentMessages();
        await refreshSessionList();

        // 재동기화가 화면을 갈아엎으므로, 메트릭은 그 뒤에 마지막 봇 메시지에 붙인다.
        if (stats) {
            const botRows = chatBox.querySelectorAll(".msg-row.bot");
            const lastRow = botRows[botRows.length - 1];
            if (lastRow) renderStats(lastRow, stats);
        }

        if (errorMessage) renderNotice(errorMessage);

        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}