// --- HTTP helpers ---
async function apiFetch(url, opt = {}) {
  const r = await fetch(url, Object.assign({ credentials: 'same-origin' }, opt));
  if (r.status === 401) { location.href = '/login'; throw new Error('401'); }
  const ct = r.headers.get('content-type') || '';
  return ct.includes('application/json') ? r.json() : r.text();
}
const apiGet = (u) => apiFetch(u);
const apiPost = (u, bodyObj) => apiFetch(u, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams(bodyObj || {})
});
function mountSSE(url, onmsg) {
  const es = new EventSource(url, { withCredentials: true });
  es.onmessage = (e) => onmsg(JSON.parse(e.data));
  es.onerror = () => es.close();
  return es;
}

// --- Theme helpers ---
function getSavedTheme() {
  try { return localStorage.getItem('theme'); } catch (_) { return null }
}
function detectPreferred() {
  try { return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light'; } catch (_) { return 'light' }
}
function applyTheme(theme) {
  const t = (theme || 'light');
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('theme', t); } catch (_) { }
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.textContent = (t === 'dark' ? '☀️' : '🌙');
    btn.title = (t === 'dark' ? '切换为明亮' : '切换为深色');
  }
}
function initTheme() {
  const saved = getSavedTheme();
  applyTheme(saved || detectPreferred());
  const btn = document.getElementById('themeToggle');
  if (btn) { btn.addEventListener('click', () => { const cur = document.documentElement.getAttribute('data-theme') || 'light'; applyTheme(cur === 'dark' ? 'light' : 'dark'); }); }
}
document.addEventListener('DOMContentLoaded', initTheme);

