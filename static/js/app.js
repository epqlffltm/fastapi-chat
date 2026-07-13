// static/js/app.js
// 페이지 로드시 실행되는 진입점

async function loadModels() {
    const modelSelect = document.getElementById("model-select");
    const res = await fetch("/models");
    const data = await res.json();
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
}

function updateNicknameDisplay() {
    const modelSelect = document.getElementById("model-select");
    const nicknameDisplay = document.getElementById("nickname-display");
    nicknameDisplay.textContent = "🤖 " + nicknameFor(modelSelect.value);
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

setupNicknameEditing();
setupEventListeners();
loadModels();