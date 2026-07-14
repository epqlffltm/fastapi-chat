// static/js/session-store.js
// DB(API) 기반 세션 목록 관리.
// sessions = 전체 원본, displayedSessions = 현재 화면에 보여줄 목록

let sessions = [];              // 항상 전체 세션 원본 (절대 덮어쓰지 않음)
let displayedSessions = [];     // 검색 결과 등 화면에 보여줄 세션
let modelNicknames = JSON.parse(localStorage.getItem("chat_nicknames") || "{}");
let currentSessionId = null;
let conversationHistory = [];

function saveNicknames() {
    localStorage.setItem("chat_nicknames", JSON.stringify(modelNicknames));
}

function currentSession() {
    return sessions.find(s => s.id === currentSessionId);
}

function nicknameFor(modelTag) {
    return modelNicknames[modelTag] || modelTag;
}

async function fetchSessions() {
    const res = await fetch("/sessions");
    sessions = await res.json();
    displayedSessions = [...sessions];   // ← 중요: displayedSessions도 갱신
}

async function refreshSessionList() {
    await fetchSessions();
    renderSessionList();
}

async function refreshCurrentMessages() {
    const res = await fetch(`/sessions/${currentSessionId}/messages`);
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
    const session = await res.json();
    sessions.unshift(session);
    displayedSessions = [...sessions];
    await switchSession(session.id);
}

async function switchSession(id) {
    const session = sessions.find(s => s.id === id);
    if (!session) return;

    currentSessionId = id;
    document.getElementById("model-select").value = session.model;
    updateNicknameDisplay();

    await refreshCurrentMessages();
    renderSessionList();
}

async function deleteSession(id) {
    await fetch(`/sessions/${id}`, { method: "DELETE" });
    sessions = sessions.filter(s => s.id !== id);
    displayedSessions = displayedSessions.filter(s => s.id !== id);

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

    displayedSessions.forEach((s) => {
        const item = document.createElement("div");
        item.className = "session-item" + (s.id === currentSessionId ? " active" : "");

        const title = document.createElement("span");
        title.className = "session-title";
        title.textContent = s.title;

        const delBtn = document.createElement("button");
        delBtn.className = "session-del-btn";
        delBtn.textContent = "Delete";
        delBtn.onclick = (e) => {
            e.stopPropagation();
            if (confirm("이 대화를 완전히 삭제할까요? 되돌릴 수 없습니다.")) {
                deleteSession(s.id);
            }
        };

        item.appendChild(title);
        item.appendChild(delBtn);
        item.onclick = () => switchSession(s.id);
        sessionListEl.appendChild(item);
    });
}

let searchDebounceTimer = null;

async function searchSessions(query) {
    const q = query.trim();
    if (!q) {
        displayedSessions = [...sessions];
        renderSessionList();
        return;
    }
    const res = await fetch(`/sessions/search?q=${encodeURIComponent(q)}`);
    displayedSessions = await res.json();
    renderSessionList();
}

function onSessionSearchInput(query) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => searchSessions(query), 250);
}