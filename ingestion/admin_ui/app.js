const API_BASE = `${window.location.origin}/api`;
const params = new URLSearchParams(window.location.search);
const TOKEN = params.get("token") || "";

const connection = document.getElementById("connection");
const feed = document.getElementById("feed");
const refreshBtn = document.getElementById("refresh-btn");
const userQuery = document.getElementById("user-query");
const userResults = document.getElementById("user-results");
const deviceInput = document.getElementById("device-input");
const reasonInput = document.getElementById("reason-input");
const manualBtn = document.getElementById("manual-btn");

let selectedUser = null;
let pollTimer = null;
let socket = null;

function headers(json = false) {
  const result = {};
  if (TOKEN) result.Authorization = `Bearer ${TOKEN}`;
  if (json) result["Content-Type"] = "application/json";
  return result;
}

function setConnection(text, state) {
  connection.textContent = text;
  connection.dataset.state = state;
}

async function loadFeed() {
  try {
    const response = await fetch(`${API_BASE}/checkins/live?limit=40&include_failed=true`, {
      headers: headers(),
    });
    if (!response.ok) throw new Error("Feed request failed");
    const payload = await response.json();
    renderFeed(payload.checkins || []);
  } catch (error) {
    console.warn(error);
    setConnection("Polling unavailable", "error");
  }
}

function renderFeed(items) {
  feed.innerHTML = "";
  items.forEach((item) => feed.appendChild(feedItem(item)));
}

function prependFeed(item) {
  feed.prepend(feedItem(item));
  while (feed.children.length > 40) {
    feed.lastElementChild.remove();
  }
}

function feedItem(item) {
  const li = document.createElement("li");
  li.className = `feed-item ${item.status.toLowerCase()}`;

  const main = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = item.user_name || labelForStatus(item.status);
  const meta = document.createElement("span");
  meta.textContent = `${new Date(item.checkin_time).toLocaleTimeString()} · ${item.device_or_location_id}`;
  main.append(title, meta);

  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = item.status.replaceAll("_", " ");

  li.append(main, badge);
  return li;
}

function labelForStatus(status) {
  if (status === "FAILED") return "Unknown face";
  if (status === "SPOOF_DETECTED") return "Spoof attempt";
  return "Check-in event";
}

function startSocket() {
  if (!TOKEN) {
    setConnection("Token required", "error");
    return;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(
    `${protocol}://${window.location.host}/api/checkins/live/ws?token=${encodeURIComponent(TOKEN)}`
  );
  socket.addEventListener("open", () => setConnection("Live", "ok"));
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "checkin") {
      prependFeed(payload.checkin);
    }
  });
  socket.addEventListener("close", () => {
    setConnection("Polling", "warn");
    window.setTimeout(startSocket, 4000);
  });
  socket.addEventListener("error", () => setConnection("Polling", "warn"));
}

async function searchUsers() {
  const query = userQuery.value.trim();
  if (!query) {
    userResults.innerHTML = "";
    selectedUser = null;
    manualBtn.disabled = true;
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/users?query=${encodeURIComponent(query)}&limit=8`, {
      headers: headers(),
    });
    if (!response.ok) throw new Error("User search failed");
    const payload = await response.json();
    renderUsers(payload.users || []);
  } catch (error) {
    console.warn(error);
  }
}

function renderUsers(users) {
  userResults.innerHTML = "";
  users.forEach((user) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "user-option";
    button.textContent = `${user.name} · ${user.email}`;
    button.addEventListener("click", () => {
      selectedUser = user;
      document.querySelectorAll(".user-option").forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
      manualBtn.disabled = false;
    });
    userResults.appendChild(button);
  });
}

async function manualOverride() {
  if (!selectedUser) return;
  manualBtn.disabled = true;
  manualBtn.textContent = "Recording";
  try {
    const response = await fetch(`${API_BASE}/checkins/manual`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        user_id: selectedUser.user_id,
        device_or_location_id: deviceInput.value.trim() || "front-desk",
        reason: reasonInput.value.trim() || null,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Manual check-in failed");
    await loadFeed();
    reasonInput.value = "";
  } catch (error) {
    alert(error.message);
  } finally {
    manualBtn.disabled = !selectedUser;
    manualBtn.textContent = "Record Manual Check-In";
  }
}

function debounce(fn, delay) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}

refreshBtn.addEventListener("click", loadFeed);
userQuery.addEventListener("input", debounce(searchUsers, 250));
manualBtn.addEventListener("click", manualOverride);

loadFeed();
startSocket();
pollTimer = window.setInterval(loadFeed, 10000);

window.addEventListener("beforeunload", () => {
  if (pollTimer) window.clearInterval(pollTimer);
  if (socket) socket.close();
});
