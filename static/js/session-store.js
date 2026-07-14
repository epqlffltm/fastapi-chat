// static/js/session-store.js

let sessions = [];
let visibleSessions = [];
let modelNicknames = JSON.parse(localStorage.getItem("chat_nicknames") || "{}");
let currentSessionId = null;
let conversationHistory = [];

function saveNicknames() {
    localStorage.setItem("chat_nicknames", JSON.stringify(modelNicknames));
}

function currentSession() {
    return sessions.find((session) => session.id === currentSessionId);
}

function nicknameFor(modelTag) {
    return modelNicknames[modelTag] || modelTag || "모델";
}

async function fetchSessions() {
    const res = await fetch("/sessions");
    if (!res.ok) throw new Error("대화 목록을 불러오지 못했습니다.");
    sessions = await res.json();
    visibleSessions = [...sessions];
}

async function refreshSessionList() {
    const searchInput = document.getElementById("session-search");
    await fetchSessions();
    if (searchInput?.value.trim()) {
        await searchSessions(searchInput.value);
        return;
    }
    renderSessionList();
}

async function refreshCurrentMessages() {
    const res = await fetch(`/sessions/${currentSessionId}/messages`);
    if (!res.ok) throw new Error("메시지를 불러오지 못했습니다.");
    conversationHistory = await res.json();
    rerenderChat();
}

async function startNewSession() {
    const modelSelect = document.getElementById("model-select");
    const res = await fetch("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: modelSelect.value }),
    });
    if (!res.ok) throw new Error("새 대화를 만들지 못했습니다.");

    const session = await res.json();
    sessions.unshift(session);
    visibleSessions = [...sessions];
    await switchSession(session.id);
}

async function switchSession(id) {
    const session = sessions.find((item) => item.id === id);
    if (!session) return;

    currentSessionId = id;
    document.getElementById("model-select").value = session.model;
    updateNicknameDisplay();

    await refreshCurrentMessages();
    renderSessionList();
}

async function deleteSession(id) {
    const res = await fetch(`/sessions/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("대화를 삭제하지 못했습니다.");

    sessions = sessions.filter((session) => session.id !== id);
    visibleSessions = visibleSessions.filter((session) => session.id !== id);

    if (currentSessionId === id) {
        if (sessions.length > 0) await switchSession(sessions[0].id);
        else await startNewSession();
    } else {
        renderSessionList();
    }
}

function renderSessionList() {
    const sessionListEl = document.getElementById("session-list");
    sessionListEl.innerHTML = "";

    visibleSessions.forEach((session) => {
        const item = document.createElement("div");
        item.className = "session-item" + (session.id === currentSessionId ? " active" : "");

        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = session.title;

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "session-del-btn";
        delBtn.textContent = "삭제";
        delBtn.title = "대화 삭제";
        delBtn.onclick = (event) => {
            event.stopPropagation();
            if (confirm("이 대화를 완전히 삭제할까요? 되돌릴 수 없습니다.")) {
                deleteSession(session.id);
            }
        };

        item.appendChild(title);
        item.appendChild(delBtn);
        item.onclick = () => switchSession(session.id);
        sessionListEl.appendChild(item);
    });
}

let searchDebounceTimer = null;

async function searchSessions(query) {
    const q = query.trim();
    if (!q) {
        visibleSessions = [...sessions];
        renderSessionList();
        return;
    }

    const res = await fetch(`/sessions/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error("대화 검색에 실패했습니다.");
    visibleSessions = await res.json();
    renderSessionList();
}

function onSessionSearchInput(query) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => searchSessions(query), 250);
}
