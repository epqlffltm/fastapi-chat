// static/js/app.js

function showAppError(message) {
    const banner = document.getElementById("app-error");
    banner.textContent = message;
    banner.hidden = false;
}

function clearAppError() {
    const banner = document.getElementById("app-error");
    banner.textContent = "";
    banner.hidden = true;
}

async function loadModels() {
    const modelSelect = document.getElementById("model-select");

    try {
        const res = await fetch("/models");
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "모델 목록을 불러오지 못했습니다.");
        if (!Array.isArray(data.models) || data.models.length === 0) {
            throw new Error("설치된 Ollama 모델이 없습니다.");
        }

        modelSelect.innerHTML = "";
        data.models.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            modelSelect.appendChild(opt);
        });
        clearAppError();
    } catch (err) {
        modelSelect.innerHTML = '<option value="">모델 연결 안 됨</option>';
        modelSelect.disabled = true;
        document.getElementById("message-input").disabled = true;
        document.querySelector(".send-btn").disabled = true;
        showAppError(err.message);
    }

    try {
        await fetchSessions();
        renderSessionList();

        if (sessions.length === 0) {
            if (!modelSelect.value) return;
            await startNewSession();
        } else {
            await switchSession(sessions[0].id);
        }
    } catch (err) {
        showAppError(err.message);
    }
}

function updateNicknameDisplay() {
    const modelSelect = document.getElementById("model-select");
    const nicknameDisplay = document.getElementById("nickname-display");
    nicknameDisplay.textContent = nicknameFor(modelSelect.value);
}

function setupNicknameEditing() {
    const modelSelect = document.getElementById("model-select");
    const nicknameDisplay = document.getElementById("nickname-display");

    nicknameDisplay.addEventListener("click", () => {
        if (!modelSelect.value) return;

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
        inputEl.addEventListener("keydown", (event) => {
            if (event.key === "Enter") inputEl.blur();
        });
    });
}

function setupEventListeners() {
    const modelSelect = document.getElementById("model-select");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("message-input");
    const searchInput = document.getElementById("session-search");
    const searchBtn = document.getElementById("session-search-btn");

    searchInput.addEventListener("input", (event) => {
        onSessionSearchInput(event.target.value);
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

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        input.value = "";
        await requestReply(message, false);
    });
}

setupNicknameEditing();
setupEventListeners();
loadModels();
