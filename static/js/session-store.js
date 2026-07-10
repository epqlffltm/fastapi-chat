// static/js/session-store.js
// localStorage 기반 세션(대화방) 목록 관리

let sessions = JSON.parse(localStorage.getItem("chat_sessions") || "[]");
let modelNicknames = JSON.parse(localStorage.getItem("chat_nicknames") || "{}");
let currentSessionId = null;
let conversationHistory = [];

function saveSessions() {
    localStorage.setItem("chat_sessions", JSON.stringify(sessions));
}

function saveNicknames() {
    localStorage.setItem("chat_nicknames", JSON.stringify(modelNicknames));
}

function currentSession() {
    return sessions.find(s => s.id === currentSessionId);
}

function nicknameFor(modelTag) {
    return modelNicknames[modelTag] || modelTag;
}

function persistCurrentMessages() {
    const session = currentSession();
    if (!session) return;
    session.messages = conversationHistory;
    saveSessions();
    renderSessionList();
}

function startNewSession() {
    const session = {
        id: Date.now().toString(),
        title: "새 대화",
        model: document.getElementById("model-select").value,
        messages: [],
    };
    sessions.unshift(session);
    saveSessions();
    switchSession(session.id);
}

function switchSession(id) {
    const session = sessions.find(s => s.id === id);
    if (!session) return;
    currentSessionId = id;
    conversationHistory = session.messages;
    document.getElementById("model-select").value = session.model;
    updateNicknameDisplay();
    rerenderChat();
    renderSessionList();
}

function deleteSession(id) {
    sessions = sessions.filter(s => s.id !== id);
    saveSessions();
    if (currentSessionId === id) {
        if (sessions.length > 0) switchSession(sessions[0].id);
        else startNewSession();
    } else {
        renderSessionList();
    }
}

function renderSessionList() {
    const sessionListEl = document.getElementById("session-list");
    sessionListEl.innerHTML = "";
    sessions.forEach((s) => {
        const item = document.createElement("div");
        item.className = "session-item" + (s.id === currentSessionId ? " active" : "");

        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = s.title;

        const delBtn = document.createElement("button");
        delBtn.className = "session-del-btn";
        delBtn.textContent = "🗑️";
        delBtn.onclick = (e) => { e.stopPropagation(); deleteSession(s.id); };

        item.appendChild(title);
        item.appendChild(delBtn);
        item.onclick = () => switchSession(s.id);
        sessionListEl.appendChild(item);
    });
}