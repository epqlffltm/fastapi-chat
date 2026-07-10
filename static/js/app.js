// static/js/app.js
// 페이지 로드시 실행되는 진입점 - 모델 목록 불러오기, 이벤트 리스너 연결

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

    if (sessions.length === 0) {
        startNewSession();
    } else {
        switchSession(sessions[0].id);
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

    modelSelect.addEventListener("change", () => {
        updateNicknameDisplay();
        const session = currentSession();
        if (session) { session.model = modelSelect.value; saveSessions(); }
    });

    document.getElementById("new-chat-btn").addEventListener("click", startNewSession);

    document.getElementById("reset-button").addEventListener("click", () => {
        conversationHistory = [];
        const session = currentSession();
        if (session) { session.title = "새 대화"; }
        persistCurrentMessages();
        rerenderChat();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;

        const userMsg = { role: "user", content: message };
        renderMessage(userMsg);
        conversationHistory.push(userMsg);

        const session = currentSession();
        if (session && session.title === "새 대화") {
            session.title = message.length > 20 ? message.slice(0, 20) + "…" : message;
        }

        if (conversationHistory.length > MAX_HISTORY) {
            conversationHistory = conversationHistory.slice(-MAX_HISTORY);
        }

        input.value = "";
        persistCurrentMessages();
        await requestReply();
    });
}

// ---- 초기 실행 ----
setupNicknameEditing();
setupEventListeners();
loadModels();