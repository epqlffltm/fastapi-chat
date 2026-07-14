// static/js/app.js
// 페이지 로드시 실행되는 진입점

async function loadModels() {
    const modelSelect = document.getElementById("model-select");

    try {
        const res = await fetch("/models");
        const data = await res.json();

        // Ollama가 꺼져있거나 에러가 발생한 경우
        if (data.error) {
            modelSelect.innerHTML = "";
            const opt = document.createElement("option");
            opt.textContent = "⚠️ Ollama 연결 실패";
            opt.disabled = true;
            modelSelect.appendChild(opt);

            console.error("[Ollama Error]", data.error);

            // 채팅 영역에 안내 메시지 표시
            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML = `
                <div style="padding: 40px 20px; text-align: center; color: #666; line-height: 1.6;">
                    <p style="font-size: 15px; margin-bottom: 8px;">
                        <strong>Ollama 서버에 연결할 수 없습니다.</strong>
                    </p>
                    <p style="font-size: 13px; color: #888;">
                        Ollama를 실행한 후 페이지를 새로고침 해주세요.<br>
                        <code style="background:#f1f1f1; padding:1px 6px; border-radius:4px; font-size:12px;">ollama serve</code>
                    </p>
                </div>
            `;
            return;
        }

        // 정상 로드
        modelSelect.innerHTML = "";
        data.models.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            modelSelect.appendChild(opt);
        });

        await fetchSessions();
        renderSessionList();

        if (sessions.length === 0) {
            await startNewSession();
        } else {
            await switchSession(sessions[0].id);
        }

    } catch (err) {
        console.error("Failed to load models:", err);
        modelSelect.innerHTML = "";
        const opt = document.createElement("option");
        opt.textContent = "⚠️ 서버 연결 실패";
        opt.disabled = true;
        modelSelect.appendChild(opt);
    }
}

function updateNicknameDisplay() {
    const modelSelect = document.getElementById("model-select");
    const nicknameDisplay = document.getElementById("nickname-display");
    const modelName = nicknameFor(modelSelect.value);
    nicknameDisplay.textContent = modelName ? `Bot · ${modelName}` : "Bot";
}

function setupNicknameEditing() {
    const modelSelect = document.getElementById("model-select");
    const nicknameDisplay = document.getElementById("nickname-display");

    nicknameDisplay.addEventListener("click", () => {
        const tag = modelSelect.value;
        const inputEl = document.createElement("input");
        inputEl.type = "text";
        inputEl.className = "nickname-input";
        inputEl.value = modelNicknames[tag] || tag;
        nicknameDisplay.replaceWith(inputEl);
        inputEl.focus();
        inputEl.select();

        const save = () => {
            const val = inputEl.value.trim();
            if (val) {
                modelNicknames[tag] = val;
                saveNicknames();
            }
            inputEl.replaceWith(nicknameDisplay);
            updateNicknameDisplay();
            rerenderChat();
        };
        inputEl.addEventListener("blur", save);
        inputEl.addEventListener("keydown", (e) => {
            if (e.key === "Enter") inputEl.blur();
        });
    });
}

function setupEventListeners() {
    const modelSelect = document.getElementById("model-select");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("message-input");
    const searchInput = document.getElementById("session-search");
    const searchBtn = document.getElementById("session-search-btn");

    searchInput.addEventListener("input", (e) => {
        onSessionSearchInput(e.target.value);
    });

    searchBtn.addEventListener("click", () => {
        clearTimeout(searchDebounceTimer);
        searchSessions(searchInput.value);
    });

    modelSelect.addEventListener("change", async () => {
        updateNicknameDisplay();
        const session = currentSession();
        if (session) {
            await fetch(`/sessions/${session.id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model: modelSelect.value }),
            });
            session.model = modelSelect.value;
        }
    });

    document.getElementById("new-chat-btn").addEventListener("click", startNewSession);

    document.getElementById("reset-button").addEventListener("click", async () => {
        if (!confirm("이 대화의 메시지를 모두 지울까요?")) return;
        await fetch(`/sessions/${currentSessionId}/messages`, { method: "DELETE" });
        conversationHistory = [];
        rerenderChat();
        await refreshSessionList();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        input.value = "";
        await requestReply(message, false);
    });
}

// 초기화
setupNicknameEditing();
setupEventListeners();
loadModels();