// Thor UI — shared helpers

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) {
    window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
    return;
  }
  const data = await res.json().catch(() => ({}));
  return { status: res.status, data };
}

function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function renderSidebar(activeKey) {
  const links = [
    { key: "picker",    href: "/",          icon: "⬡", label: "Scrapers" },
    { key: "jobs",      href: "/jobs",      icon: "⚡", label: "Jobs" },
    { key: "leads",     href: "/leads",     icon: "◎", label: "Leads" },
    { key: "dashboard", href: "/dashboard", icon: "▦", label: "Dashboard" },
  ];

  return `
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">T</div>
        <div>
          <div class="brand-text">Thor</div>
          <div class="brand-sub">HUDREI SCRAPERS</div>
        </div>
      </div>
      <div class="sidebar-section">Main</div>
      ${links.map(l => `
        <a href="${l.href}" class="sidebar-link ${activeKey === l.key ? 'active' : ''}">
          <span class="icon">${l.icon}</span> ${l.label}
        </a>
      `).join("")}
      <div class="sidebar-footer">
        <a href="/logout">Sign out</a>
      </div>
    </aside>
  `;
}

function mountSidebar(activeKey) {
  const slot = $("#sidebar-slot");
  if (slot) slot.outerHTML = renderSidebar(activeKey);
}

function fmtDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function fmtRelative(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const d = Math.floor((Date.now() - t) / 1000);
  if (d < 60) return `${d}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
}

function statusPill(status) {
  const map = {
    queued: ["muted", "QUEUED"],
    running: ["running", "RUNNING"],
    done: ["ok", "DONE"],
    error: ["error", "ERROR"],
    cancelled: ["warn", "CANCELLED"],
  };
  const [cls, label] = map[status] || ["muted", status.toUpperCase()];
  return `<span class="pill ${cls}">${label}</span>`;
}
