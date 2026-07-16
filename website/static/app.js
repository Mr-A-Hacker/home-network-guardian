// Home Network Guardian - frontend SPA
const API = ""; // same origin; agent posts to /api/v1/report
let TOKEN = localStorage.getItem("hng_token") || "";

function authHeaders(extra = {}) {
  return { "Content-Type": "application/json", ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}), ...extra };
}
async function api(path, opts = {}) {
  const res = await fetch(API + path, { ...opts, headers: authHeaders(opts.headers || {}) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
function show(el) { document.getElementById(el).classList.remove("hidden"); }
function hide(el) { document.getElementById(el).classList.add("hidden"); }

// ---- Auth UI ----
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const signin = t.dataset.tab === "signin";
  document.getElementById("signin-form").classList.toggle("hidden", !signin);
  document.getElementById("signup-form").classList.toggle("hidden", signin);
});
document.getElementById("signup-form").onsubmit = async (e) => {
  e.preventDefault();
  const msg = document.getElementById("auth-msg"); msg.textContent = "";
  try {
    const r = await api("/api/auth/signup", { method: "POST", body: JSON.stringify({
      email: document.getElementById("su-email").value,
      password: document.getElementById("su-pass").value }) });
    TOKEN = r.token; localStorage.setItem("hng_token", TOKEN);
    enterApp();
  } catch (err) { msg.textContent = err.message; }
};
document.getElementById("signin-form").onsubmit = async (e) => {
  e.preventDefault();
  const msg = document.getElementById("auth-msg"); msg.textContent = "";
  try {
    const r = await api("/api/auth/signin", { method: "POST", body: JSON.stringify({
      email: document.getElementById("si-email").value,
      password: document.getElementById("si-pass").value }) });
    TOKEN = r.token; localStorage.setItem("hng_token", TOKEN);
    enterApp();
  } catch (err) { msg.textContent = err.message; }
};
document.getElementById("logout").onclick = () => {
  TOKEN = ""; localStorage.removeItem("hng_token"); location.reload();
};

// ---- App ----
async function enterApp() {
  hide("auth"); show("dash"); show("userbox");
  try {
    const me = await api("/api/auth/me");
    document.getElementById("email").textContent = me.user.email;
    document.getElementById("plan").textContent = me.user.is_pro ? "PRO" : "FREE";
    document.getElementById("upgrade").classList.toggle("hidden", me.user.is_pro);
    loadDashboard();
  } catch { TOKEN = ""; localStorage.removeItem("hng_token"); location.reload(); }
}
document.getElementById("add-house").onclick = async () => {
  const name = prompt("House name:", "My Home");
  if (!name) return;
  await api("/api/houses", { method: "POST", body: JSON.stringify({ name }) });
  loadDashboard();
};
document.getElementById("upgrade").onclick = async () => {
  if (!confirm("Activate Pro? (demo - no real payment)")) return;
  const id = document.getElementById("house-detail").dataset.house;
  await api(`/api/houses/${id}/upgrade`, { method: "POST" });
  enterApp();
};

let currentHouses = [];
async function loadDashboard() {
  const d = await api("/api/dashboard");
  currentHouses = d.houses;
  const wrap = document.getElementById("houses"); wrap.innerHTML = "";
  d.houses.forEach(h => {
    const div = document.createElement("div");
    div.className = "house-card";
    const online = h.last_seen && (Date.now() - new Date(h.last_seen).getTime()) < 5 * 60000;
    div.innerHTML = `<div><span class="dot ${online ? "online" : "offline"}"></span><b>${h.name}</b></div>
      <div style="color:var(--muted);font-size:13px;margin-top:6px;">${h.device_count} devices · ${h.has_key ? "router linked" : "no router key"}</div>`;
    div.onclick = () => openHouse(h);
    wrap.appendChild(div);
  });
  if (!d.houses.length) wrap.innerHTML = "<p style='color:var(--muted)'>No houses yet. Create one above.</p>";
}

let activeHouse = null;
function openHouse(h) {
  activeHouse = h;
  const det = document.getElementById("house-detail");
  det.dataset.house = h.id;
  show("house-detail");
  document.getElementById("hd-name").textContent = h.name;
  const online = h.last_seen && (Date.now() - new Date(h.last_seen).getTime()) < 5 * 60000;
  document.getElementById("hd-status").textContent = online
    ? `🟢 Router online · last seen ${new Date(h.last_seen).toLocaleString()}`
    : (h.last_seen ? `🔴 Router offline · last seen ${new Date(h.last_seen).toLocaleString()}` : "⚪ No reports yet");
  document.getElementById("hd-key").value = h.api_key || "";

  const tb = document.getElementById("hd-devices"); tb.innerHTML = "";
  (h.devices || []).forEach(d => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${d.mac}</td><td>${d.ip || "-"}</td><td>${d.vendor || "-"}</td>
      <td><span class="pill ${d.status}">${d.status}</span></td><td>${d.last_seen ? new Date(d.last_seen).toLocaleString() : "-"}</td>`;
    tb.appendChild(tr);
  });
  const al = document.getElementById("hd-alerts"); al.innerHTML = "";
  (h.alerts || []).forEach(a => {
    const div = document.createElement("div");
    div.className = "alert-item";
    div.textContent = `${a.type} · ${a.created_at ? new Date(a.created_at).toLocaleString() : ""}`;
    al.appendChild(div);
  });
  if (!(h.alerts || []).length) al.innerHTML = "<p style='color:var(--muted)'>No alerts.</p>";
}

document.getElementById("hd-save-key").onclick = async () => {
  const msg = document.getElementById("hd-key-msg"); msg.textContent = "";
  const key = document.getElementById("hd-key").value.trim();
  try {
    await api(`/api/houses/${activeHouse.id}/key`, { method: "POST", body: JSON.stringify({ api_key: key }) });
    msg.style.color = "var(--ok)"; msg.textContent = "Router linked! It will appear online within a minute.";
    loadDashboard();
  } catch (err) { msg.textContent = err.message; }
};

// ---- Boot ----
if (TOKEN) enterApp(); else show("auth");
