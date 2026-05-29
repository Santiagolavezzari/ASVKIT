/* ═══════════════════════════════════════════════════════
   ASV Kit · Shared Module
   Eliminates duplication across all panel pages
   ═══════════════════════════════════════════════════════ */

const API = 'http://127.0.0.1:5000';

/* ── Type mapping ─────────────────────────────────────── */
const TYPE_MAP = {
  doorbell:    { label: 'Timbre',         color: 'var(--blue)',  bg: 'var(--blue-s)',  icon: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0' },
  smoke:       { label: 'Humo',           color: 'var(--red)',   bg: 'var(--red-s)',   icon: 'M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z' },
  washer:      { label: 'Lavadora',       color: 'var(--teal)',  bg: 'var(--teal-s)',  icon: 'M3 6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6zM3 10h18M12 17a3 3 0 1 0 0-6 3 3 0 0 0 0 6z' },
  door_window: { label: 'Puerta/Ventana', color: 'var(--amber)', bg: 'var(--amber-s)', icon: 'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10' },
};
const getType = t => TYPE_MAP[t] || TYPE_MAP.doorbell;

/* ── Time formatting ──────────────────────────────────── */
function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60)   return 'ahora';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
  return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
}

function formatFull(iso) {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('es-AR', {
    day: '2-digit', month: 'short', year: 'numeric'
  });
}

/* ── Badge helpers ────────────────────────────────────── */
function badgeClass(status) {
  return status === 'sent' ? 'badge-green' : status === 'failed' ? 'badge-red' : 'badge-gray';
}
function badgeText(status) {
  return status === 'sent' ? 'Enviado' : status === 'failed' ? 'Fallido' : 'Pendiente';
}

/* ── Auth check (sync - local only) ──────────────────── */
function authCheck(requireAdmin = false) {
  const stored = localStorage.getItem('asvkit_user') || sessionStorage.getItem('asvkit_user');
  if (!stored) { window.location.href = 'login.html'; return null; }
  let user;
  try {
    user = JSON.parse(stored);
    if (!user || !user.id) throw new Error('bad data');
  } catch {
    localStorage.removeItem('asvkit_user');
    sessionStorage.removeItem('asvkit_user');
    window.location.href = 'login.html';
    return null;
  }
  if (requireAdmin && user.role !== 'admin') {
    window.location.href = 'dashboard.html';
    return null;
  }
  return user;
}

/* ── Auth check (async - verifica con el servidor) ────── */
// Retorna el objeto user si la sesión es válida, sino redirige a login.
async function authCheckServer(requireAdmin = false) {
  try {
    const res = await fetch(API + '/api/auth/session', {
      credentials: 'include',
      signal: AbortSignal.timeout(5000)
    });
    if (!res.ok) {
      // Sesión inválida en el servidor
      localStorage.removeItem('asvkit_user');
      sessionStorage.removeItem('asvkit_user');
      window.location.href = 'login.html';
      return null;
    }
    const data = await res.json();
    if (!data.authenticated) {
      localStorage.removeItem('asvkit_user');
      sessionStorage.removeItem('asvkit_user');
      window.location.href = 'login.html';
      return null;
    }
    const user = { id: data.id, username: data.username, role: data.role };
    // Sincronizar storage local con lo que confirma el servidor
    if (localStorage.getItem('asvkit_user')) {
      localStorage.setItem('asvkit_user', JSON.stringify(user));
    } else {
      sessionStorage.setItem('asvkit_user', JSON.stringify(user));
    }
    if (requireAdmin && user.role !== 'admin') {
      window.location.href = 'dashboard.html';
      return null;
    }
    return user;
  } catch {
    // Sin conexión: intentar con datos locales como fallback
    return authCheck(requireAdmin);
  }
}

/* ── Init sidebar user info ───────────────────────────── */
function initSidebar(user) {
  const el = (id) => document.getElementById(id);
  if (el('user-name'))   el('user-name').textContent = user.username;
  if (el('user-role'))   el('user-role').textContent = user.role === 'admin' ? 'Administrador' : 'Usuario';
  if (el('user-avatar')) el('user-avatar').textContent = user.username[0].toUpperCase();
  if (user.role === 'admin') {
    document.querySelectorAll('.admin-only').forEach(e => e.style.display = '');
  }
  // Mobile sidebar toggle
  initMobileSidebar();
}

/* ── Mobile sidebar ───────────────────────────────────── */
function initMobileSidebar() {
  const sidebar = document.querySelector('.sidebar');
  if (!sidebar) return;

  // Create hamburger button
  const burger = document.createElement('button');
  burger.className = 'mobile-burger';
  burger.id = 'mobile-burger';
  burger.setAttribute('aria-label', 'Menú');
  burger.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`;

  // Create overlay
  const overlay = document.createElement('div');
  overlay.className = 'sidebar-overlay';
  overlay.id = 'sidebar-overlay';

  document.body.appendChild(burger);
  document.body.appendChild(overlay);

  burger.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  });

  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
  });
}

/* ── Logout ───────────────────────────────────────────── */
async function logout() {
  try {
    await fetch(API + '/api/auth/logout', { method: 'POST', credentials: 'include' });
  } catch { /* ignore */ }
  localStorage.removeItem('asvkit_user');
  sessionStorage.removeItem('asvkit_user');
  window.location.href = 'login.html';
}

/* ── Toast notifications ──────────────────────────────── */
function showToast(msg, ok = true) {
  const t = document.getElementById('toast');
  if (!t) return;
  document.getElementById('toast-msg').textContent = msg;
  document.getElementById('toast-dot').style.background = ok ? 'var(--green)' : 'var(--red)';
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 3500);
}

/* ── Skeleton loaders ─────────────────────────────────── */
function skeletonRows(cols, rows = 4) {
  return Array.from({ length: rows }, () =>
    `<tr class="skeleton-row">${Array.from({ length: cols }, () =>
      `<td><div class="skeleton-block"></div></td>`
    ).join('')}</tr>`
  ).join('');
}

function skeletonCards(count = 4) {
  return Array.from({ length: count }, () =>
    `<div class="skeleton-card"><div class="skeleton-block" style="height:24px;width:60%;margin-bottom:8px"></div><div class="skeleton-block" style="height:14px;width:40%"></div></div>`
  ).join('');
}

/* ── Fetch helper ─────────────────────────────────────────── */

// Bandera para evitar loops de redirect
let _sessionLost = false;

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    credentials: 'include',
    signal: AbortSignal.timeout(8000),
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  });

  if (res.status === 401) {
    if (_sessionLost) return res; // ya se está manejando

    // Intentar restaurar sesión: si hay datos locales, redirigir al login limpiamente
    _sessionLost = true;
    localStorage.removeItem('asvkit_user');
    sessionStorage.removeItem('asvkit_user');

    // Pequeño delay para evitar redirigir antes de que Flask confirme la sesión
    await new Promise(r => setTimeout(r, 300));
    window.location.href = 'login.html';
    throw new Error('Unauthorized');
  }

  if (res.status === 403) {
    window.location.href = 'dashboard.html';
    throw new Error('Forbidden');
  }

  return res;
}

/* ── Confirm modal (replaces native confirm) ──────────── */
function confirmAction(message, onConfirm) {
  // Remove any existing confirm modal
  const existing = document.getElementById('confirm-modal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'confirm-modal';
  modal.className = 'modal-overlay open';
  modal.innerHTML = `
    <div class="modal" style="max-width:380px">
      <div class="modal-title">Confirmar acción</div>
      <p style="font-size:14px;color:var(--text2);line-height:1.6;margin-bottom:0">${message}</p>
      <div class="modal-footer">
        <button class="btn btn-ghost" id="confirm-cancel">Cancelar</button>
        <button class="btn btn-danger" id="confirm-ok">Confirmar</button>
      </div>
    </div>`;
  document.body.appendChild(modal);

  document.getElementById('confirm-cancel').onclick = () => modal.remove();
  document.getElementById('confirm-ok').onclick = () => { modal.remove(); onConfirm(); };
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

/* ── CSV Export ────────────────────────────────────────── */
function exportCSV(headers, rows, filename = 'export.csv') {
  const csvContent = [headers.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

/* ── Mini Chart (canvas-based bar chart) ──────────────── */
function drawBarChart(canvasId, data, color = '#0071e3') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const max = Math.max(...data.map(d => d.count), 1);
  const barW = Math.floor((W - 20) / data.length) - 4;
  const pad = (W - (barW + 4) * data.length) / 2;

  // Grid lines
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i++) {
    const y = Math.round(H * 0.15 + (H * 0.7 / 3) * i) + 0.5;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }

  // Bars
  data.forEach((d, i) => {
    const x = pad + i * (barW + 4);
    const barH = (d.count / max) * (H * 0.65);
    const y = H - 22 - barH;
    const r = Math.min(barW / 2, 4);

    // Bar with rounded top
    ctx.fillStyle = d.count > 0 ? color : 'rgba(255,255,255,0.04)';
    ctx.beginPath();
    ctx.moveTo(x, y + r);
    ctx.arcTo(x, y, x + barW, y, r);
    ctx.arcTo(x + barW, y, x + barW, y + barH, r);
    ctx.lineTo(x + barW, H - 22);
    ctx.lineTo(x, H - 22);
    ctx.closePath();
    ctx.fill();

    // Glow effect for non-zero bars
    if (d.count > 0) {
      ctx.shadowColor = color;
      ctx.shadowBlur = 8;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, barW, 2);
      ctx.shadowBlur = 0;
    }

    // Day label
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'center';
    const dayLabel = new Date(d.date).toLocaleDateString('es-AR', { weekday: 'narrow' });
    ctx.fillText(dayLabel, x + barW / 2, H - 6);
  });
}
