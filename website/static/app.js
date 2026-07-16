// Home Network Guardian - frontend SPA
const API = "";
let TOKEN = localStorage.getItem("hng_token") || "";
let currentHouses = [];
let activeHouse = null;
let refreshTimer = null;

function authHeaders(extra = {}) {
  return { "Content-Type": "application/json", ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}), ...extra };
}
async function api(path, opts = {}) {
  const res = await fetch(API + path, { ...opts, headers: authHeaders(opts.headers || {}) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
const $ = (id) => document.getElementById(id);
function show(el) { $(el).classList.remove("hidden"); }
function hide(el) { $(el).classList.add("hidden"); }

// ---- Auth UI ----
document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  t.classList.add("active");
  const signin = t.dataset.tab === "signin";
  $("signin-form").classList.toggle("hidden", !signin);
  $("signup-form").classList.toggle("hidden", signin);
});
$("signup-form").onsubmit = async (e) => {
  e.preventDefault();
  const msg = $("auth-msg"); msg.textContent = "";
  try {
    const r = await api("/api/auth/signup", { method: "POST", body: JSON.stringify({
      email: $("su-email").value, password: $("su-pass").value }) });
    TOKEN = r.token; localStorage.setItem("hng_token", TOKEN);
    enterApp();
  } catch (err) { msg.textContent = err.message; }
};
$("signin-form").onsubmit = async (e) => {
  e.preventDefault();
  const msg = $("auth-msg"); msg.textContent = "";
  try {
    const r = await api("/api/auth/signin", { method: "POST", body: JSON.stringify({
      email: $("si-email").value, password: $("si-pass").value }) });
    TOKEN = r.token; localStorage.setItem("hng_token", TOKEN);
    enterApp();
  } catch (err) { msg.textContent = err.message; }
};
$("logout").onclick = () => {
  TOKEN = ""; localStorage.removeItem("hng_token");
  clearInterval(refreshTimer); location.reload();
};

// ---- App ----
async function enterApp() {
  hide("auth"); show("dash"); show("userbox");
  try {
    const me = await api("/api/auth/me");
    $("email").textContent = me.user.email;
    $("plan").textContent = me.user.is_pro ? "PRO" : "FREE";
    $("plan").className = "badge" + (me.user.is_pro ? " pro" : "");
    $("upgrade").classList.toggle("hidden", me.user.is_pro);
    loadDashboard();
    refreshTimer = setInterval(loadDashboard, 30000); // auto-refresh
  } catch { TOKEN = ""; localStorage.removeItem("hng_token"); location.reload(); }
}
$("add-house").onclick = async () => {
  const name = prompt("House name:", "My Home");
  if (!name) return;
  await api("/api/houses", { method: "POST", body: JSON.stringify({ name }) });
  loadDashboard();
};
$("upgrade").onclick = async () => {
  if (!confirm("Activate Pro? (demo - no real payment)")) return;
  await api(`/api/houses/${activeHouse.id}/upgrade`, { method: "POST" });
  enterApp();
};

async function loadDashboard() {
  const d = await api("/api/dashboard");
  currentHouses = d.houses;
  const wrap = $("houses"); wrap.innerHTML = "";
  if (!d.houses.length) {
    wrap.innerHTML = '<p class="empty">No houses yet. Click “+ New House” to start.</p>';
    return;
  }
  d.houses.forEach(h => {
    const div = document.createElement("div");
    div.className = "house-card";
    const st = houseState(h);
    div.innerHTML = `<div class="name"><span class="dot ${st.cls}"></span>${h.name}</div>
      <div class="meta">${h.device_count} devices · ${h.has_key ? "router linked" : "no router key"}</div>`;
    div.onclick = () => openHouse(h);
    wrap.appendChild(div);
  });
  if (activeHouse) {
    const a = d.houses.find(x => x.id === activeHouse.id);
    if (a) openHouse(a, true);
  }
}
function houseState(h) {
  if (!h.last_seen) return { cls: "idle", label: "no reports" };
  const mins = (Date.now() - new Date(h.last_seen).getTime()) / 60000;
  if (mins < 5) return { cls: "online", label: "online" };
  if (mins < 30) return { cls: "idle", label: "idle" };
  return { cls: "offline", label: "offline" };
}

function openHouse(h, keepScroll) {
  activeHouse = h;
  const det = $("house-detail");
  det.dataset.house = h.id;
  show("house-detail");
  $("hd-name").textContent = h.name;
  const st = houseState(h);
  const seen = h.last_seen ? new Date(h.last_seen).toLocaleString() : "never";
  $("hd-status").innerHTML = `<span class="dot ${st.cls}"></span> Router ${st.label} · last seen ${seen}`;

  const present = (h.devices || []).filter(d => d.status === "present").length;
  $("hd-stats").innerHTML = `
    <div class="stat"><div class="n">${(h.devices || []).length}</div><div class="l">Devices seen</div></div>
    <div class="stat"><div class="n">${present}</div><div class="l">Online now</div></div>
    <div class="stat"><div class="n">${(h.alerts || []).length}</div><div class="l">Alerts</div></div>`;

  const tb = $("hd-devices"); tb.innerHTML = "";
  (h.devices || []).forEach(d => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${d.mac}</td><td>${d.ip || "-"}</td><td>${d.vendor || "-"}</td>
      <td><span class="pill ${d.status}">${d.status}</span></td><td>${d.last_seen ? new Date(d.last_seen).toLocaleString() : "-"}</td>`;
    tb.appendChild(tr);
  });
  if (!(h.devices || []).length) tb.innerHTML = '<tr><td colspan="5" class="empty">No devices yet.</td></tr>';

  const al = $("hd-alerts"); al.innerHTML = "";
  (h.alerts || []).forEach(a => {
    const div = document.createElement("div");
    div.className = "alert-item type-" + a.type;
    div.innerHTML = `<span>${a.type.replace(/_/g, " ")}</span><span class="t">${a.created_at ? new Date(a.created_at).toLocaleString() : ""}</span>`;
    al.appendChild(div);
  });
  if (!(h.alerts || []).length) al.innerHTML = '<p class="empty">No alerts. All quiet. 🛡️</p>';
}

$("hd-save-key").onclick = async () => {
  const msg = $("hd-key-msg"); msg.textContent = ""; msg.style.color = "var(--danger)";
  const key = $("hd-key").value.trim();
  try {
    await api(`/api/houses/${activeHouse.id}/key`, { method: "POST", body: JSON.stringify({ api_key: key }) });
    msg.style.color = "var(--ok)"; msg.textContent = "Router linked! It will appear online within a minute.";
    loadDashboard();
  } catch (err) { msg.textContent = err.message; }
};

// ---- Boot ----
if (TOKEN) enterApp(); else show("auth");
