// State
let currentUser = null;
let selectedFile = null;
let currentDocxBlob = null;

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const mainScreen = document.getElementById('main-screen');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const loginError = document.getElementById('login-error');
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const uploadInfo = document.getElementById('upload-info');
const fileInfo = document.getElementById('file-info');
const uploadError = document.getElementById('upload-error');
const processingSection = document.getElementById('processing-section');
const resultsSection = document.getElementById('results-section');
const errorSection = document.getElementById('error-section');
const downloadBtn = document.getElementById('download-btn');
const logoutBtn = document.getElementById('logout-btn');
const userDisplay = document.getElementById('user-display');
const adminScreen = document.getElementById('admin-screen');

// Upload area events
uploadArea.addEventListener('click', () => fileInput.click());
uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
});
downloadBtn.addEventListener('click', downloadReport);
logoutBtn.addEventListener('click', handleLogout);

// ==================== Auth helpers ====================
function authHeaders() {
  return { Authorization: `Bearer ${currentUser.access_token}` };
}

// ==================== Login ====================
async function handleLogin(event) {
  event.preventDefault();
  const login = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!login || !password) { showLoginError('Введи логин и пароль'); return; }
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    });
    const data = await response.json();
    if (!response.ok) { showLoginError(data.error || 'Неверные учетные данные'); return; }
    currentUser = data;
    localStorage.setItem('auth-token', JSON.stringify(data));
    hideLoginError();
    switchToMainScreen();
  } catch (error) {
    showLoginError('Ошибка подключения к серверу');
  }
}

// ==================== Register ====================
function showRegisterPanel() {
  document.getElementById('login-panel').classList.add('hidden');
  document.getElementById('register-panel').classList.remove('hidden');
  document.getElementById('register-error').classList.add('hidden');
  document.getElementById('register-success').classList.add('hidden');
  document.getElementById('reg-username').value = '';
  document.getElementById('reg-password').value = '';
  document.getElementById('reg-password2').value = '';
}

function showLoginPanel() {
  document.getElementById('register-panel').classList.add('hidden');
  document.getElementById('login-panel').classList.remove('hidden');
  hideLoginError();
}

async function handleRegister(event) {
  event.preventDefault();
  const login = document.getElementById('reg-username').value.trim();
  const password = document.getElementById('reg-password').value;
  const password2 = document.getElementById('reg-password2').value;
  const errEl = document.getElementById('register-error');
  const successEl = document.getElementById('register-success');
  errEl.classList.add('hidden');
  successEl.classList.add('hidden');

  if (!login) { errEl.textContent = 'Введи логин'; errEl.classList.remove('hidden'); return; }
  if (password.length < 6) { errEl.textContent = 'Пароль должен содержать минимум 6 символов'; errEl.classList.remove('hidden'); return; }
  if (password !== password2) { errEl.textContent = 'Пароли не совпадают'; errEl.classList.remove('hidden'); return; }

  try {
    const res = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login, password }),
    });
    const data = await res.json();
    if (!res.ok) { errEl.textContent = data.error || 'Ошибка регистрации'; errEl.classList.remove('hidden'); return; }
    successEl.textContent = `Аккаунт «${login}» создан. Теперь войдите.`;
    successEl.classList.remove('hidden');
    setTimeout(() => {
      showLoginPanel();
      usernameInput.value = login;
    }, 1500);
  } catch (e) {
    errEl.textContent = 'Ошибка подключения к серверу';
    errEl.classList.remove('hidden');
  }
}

function handleLogout() {
  currentUser = null;
  localStorage.removeItem('auth-token');
  selectedFile = null;
  currentDocxBlob = null;
  resetForm();
  switchToLoginScreen();
}

// ==================== UI Helpers ====================
function hideAllScreens() {
  loginScreen.classList.remove('active');
  mainScreen.classList.remove('active');
  adminScreen.classList.remove('active');
  document.getElementById('stats-screen').classList.remove('active');
  document.getElementById('profile-screen').classList.remove('active');
}

function switchToLoginScreen() {
  hideAllScreens();
  loginScreen.classList.add('active');
  usernameInput.value = '';
  passwordInput.value = '';
  showLoginPanel();
}

function switchToMainScreen() {
  hideAllScreens();
  mainScreen.classList.add('active');
  userDisplay.textContent = `👤 ${currentUser.login}`;
  const adminBtn = document.getElementById('admin-nav-btn');
  if (currentUser.role === 'admin') adminBtn.classList.remove('hidden');
  else adminBtn.classList.add('hidden');

  const hasAccess = currentUser.role === 'admin' || currentUser.is_whitelisted;
  let banner = document.getElementById('access-warning-banner');
  if (!hasAccess) {
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'access-warning-banner';
      banner.className = 'access-warning';
      banner.textContent = '⚠ У вас нет доступа к генерации отчётов. Обратитесь к администратору.';
      document.querySelector('#main-screen .container').prepend(banner);
    }
    banner.classList.remove('hidden');
  } else if (banner) {
    banner.classList.add('hidden');
  }
  resetForm();
}

function showLoginError(msg) { loginError.textContent = msg; loginError.classList.remove('hidden'); }
function hideLoginError() { loginError.classList.add('hidden'); }
function showUploadError(msg) { uploadError.textContent = '❌ ' + msg; uploadError.classList.remove('hidden'); }
function hideUploadError() { uploadError.classList.add('hidden'); }

// ==================== Admin Screen ====================
function switchToAdminScreen() {
  if (!currentUser || currentUser.role !== 'admin') return;
  hideAllScreens();
  adminScreen.classList.add('active');
  document.getElementById('admin-user-display').textContent = `👤 ${currentUser.login}`;
  document.getElementById('admin-logout-btn').onclick = handleLogout;
  loadUsers();
  loadTmpInfo();
}

async function loadUsers() {
  const wrap = document.getElementById('users-table-wrap');
  const errEl = document.getElementById('admin-error');
  wrap.innerHTML = '<p class="muted">Загрузка...</p>';
  errEl.classList.add('hidden');
  try {
    const res = await fetch('/api/admin/users', { headers: authHeaders() });
    if (!res.ok) throw new Error((await res.json()).error || 'Ошибка загрузки');
    wrap.innerHTML = renderUsersTable(await res.json());
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
    wrap.innerHTML = '';
  }
}

function renderUsersTable(users) {
  if (!users.length) return '<p class="muted">Нет пользователей</p>';
  const rows = users.map(u => `
    <tr class="${!u.is_active ? 'row-blocked' : ''}">
      <td>${u.id}</td>
      <td><strong>${escHtml(u.login)}</strong></td>
      <td><span class="badge badge-${u.role}">${u.role}</span></td>
      <td>${u.is_active ? '<span class="badge badge-active">активен</span>' : '<span class="badge badge-blocked">заблокирован</span>'}</td>
      <td>${u.is_whitelisted ? '<span class="badge badge-wl">✓</span>' : '<span class="badge badge-nowl">—</span>'}</td>
      <td class="td-stats">${(u.total_input_tokens + u.total_output_tokens).toLocaleString()}</td>
      <td class="td-stats">${u.total_tavily_requests}</td>
      <td class="td-stats">${u.reports_count}</td>
      <td class="td-actions">
        ${u.is_active
          ? `<button class="btn btn-danger btn-xs" onclick="adminAction(${u.id},'block')">Блок</button>`
          : `<button class="btn btn-success btn-xs" onclick="adminAction(${u.id},'unblock')">Разблок</button>`}
        ${u.is_whitelisted
          ? `<button class="btn btn-outline btn-xs" onclick="adminAction(${u.id},'unwhitelist')">−WL</button>`
          : `<button class="btn btn-outline btn-xs" onclick="adminAction(${u.id},'whitelist')">+WL</button>`}
      </td>
    </tr>`).join('');
  return `<div class="table-scroll"><table class="admin-table">
    <thead><tr><th>ID</th><th>Логин</th><th>Роль</th><th>Статус</th><th>WL</th>
    <th>Токены</th><th>Поиски</th><th>Отчёты</th><th>Действия</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

async function adminAction(userId, action) {
  const errEl = document.getElementById('admin-error');
  errEl.classList.add('hidden');
  try {
    const res = await fetch(`/api/admin/users/${userId}/${action}`, {
      method: 'PATCH', headers: authHeaders(),
    });
    if (!res.ok) throw new Error((await res.json()).error || 'Ошибка');
    await loadUsers();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}

async function loadTmpInfo() {
  try {
    const res = await fetch('/api/admin/tmp/info', { headers: authHeaders() });
    if (!res.ok) throw new Error('Ошибка');
    const data = await res.json();
    document.getElementById('tmp-path').textContent = data.path;
    document.getElementById('tmp-size').textContent = `${data.size_mb} МБ (${data.size_bytes.toLocaleString()} байт)`;
  } catch (e) {
    document.getElementById('tmp-size').textContent = 'Ошибка загрузки';
  }
}

async function clearTmp() {
  if (!confirm('Очистить директорию tmp? Это удалит все временные файлы.')) return;
  const msgEl = document.getElementById('tmp-message');
  msgEl.className = 'hidden';
  try {
    const res = await fetch('/api/admin/tmp/clear', { method: 'DELETE', headers: authHeaders() });
    const data = await res.json();
    msgEl.textContent = data.detail || 'Готово';
    msgEl.className = res.ok ? 'info-box' : 'error';
    await loadTmpInfo();
  } catch (e) {
    msgEl.textContent = e.message;
    msgEl.className = 'error';
  }
}

// ==================== Stats Screen ====================
function switchToStatsScreen() {
  hideAllScreens();
  document.getElementById('stats-screen').classList.add('active');
  document.getElementById('stats-user-display').textContent = `👤 ${currentUser.login}`;
  document.getElementById('stats-logout-btn').onclick = handleLogout;
  loadStats();
}

async function loadStats() {
  const wrap = document.getElementById('stats-table-wrap');
  const errEl = document.getElementById('stats-error');
  const summary = document.getElementById('stats-summary');
  wrap.innerHTML = '<p class="muted">Загрузка...</p>';
  errEl.classList.add('hidden');
  summary.classList.add('hidden');
  try {
    const res = await fetch('/api/users/me/reports', { headers: authHeaders() });
    if (!res.ok) throw new Error((await res.json()).error || 'Ошибка загрузки');
    const reports = await res.json();
    const totalTokens = reports.reduce((s, r) => s + r.input_tokens + r.output_tokens, 0);
    const totalSearches = reports.reduce((s, r) => s + r.tavily_requests, 0);
    document.getElementById('stats-total').textContent = reports.length;
    document.getElementById('stats-tokens').textContent = totalTokens.toLocaleString();
    document.getElementById('stats-searches').textContent = totalSearches;
    summary.classList.remove('hidden');
    wrap.innerHTML = renderReportsTable(reports);
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
    wrap.innerHTML = '';
  }
}

function renderReportsTable(reports) {
  if (!reports.length) return '<p class="muted">У вас пока нет отчётов</p>';
  const rows = reports.map(r => {
    const date = new Date(r.created_at).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
    const name = r.presentation_dir.replace(/_\d{8}_[a-f0-9]+$/, '').replace(/_/g, ' ');
    const dlBtn = r.docx_path
      ? `<button class="btn btn-outline btn-xs" onclick="downloadReportById(${r.id}, '${escHtml(name)}')">⬇ DOCX</button>`
      : `<span class="muted" style="font-size:0.8rem">недоступен</span>`;
    return `<tr>
      <td>${r.id}</td>
      <td title="${escHtml(r.presentation_dir)}">${escHtml(name)}</td>
      <td class="td-stats">${(r.input_tokens + r.output_tokens).toLocaleString()}</td>
      <td class="td-stats">${r.tavily_requests}</td>
      <td class="td-stats">${date}</td>
      <td class="td-actions">${dlBtn}</td>
    </tr>`;
  }).join('');
  return `<div class="table-scroll"><table class="admin-table">
    <thead><tr><th>#</th><th>Презентация</th><th>Токены</th><th>Поиски</th><th>Дата</th><th></th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

async function downloadReportById(reportId, name) {
  const errEl = document.getElementById('stats-error');
  try {
    const res = await fetch(`/api/pipeline/reports/${reportId}/download`, { headers: authHeaders() });
    if (!res.ok) throw new Error((await res.json()).error || 'Ошибка скачивания');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name || 'report'}.docx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}

// ==================== Profile Screen ====================
function switchToProfileScreen() {
  hideAllScreens();
  document.getElementById('profile-screen').classList.add('active');
  document.getElementById('profile-user-display').textContent = `👤 ${currentUser.login}`;
  document.getElementById('profile-logout-btn').onclick = handleLogout;
  loadProfile();
}

async function loadProfile() {
  const errEl = document.getElementById('profile-error');
  errEl.classList.add('hidden');
  try {
    const res = await fetch('/api/users/me', { headers: authHeaders() });
    if (!res.ok) throw new Error((await res.json()).error || 'Ошибка загрузки профиля');
    const u = await res.json();
    currentUser = { ...currentUser, ...u };
    localStorage.setItem('auth-token', JSON.stringify(currentUser));
    document.getElementById('profile-login').textContent = u.login;
    document.getElementById('profile-role').innerHTML = `<span class="badge badge-${u.role}">${u.role}</span>`;
    document.getElementById('profile-access').innerHTML = u.is_whitelisted || u.role === 'admin'
      ? '<span class="badge badge-active">разрешён</span>'
      : '<span class="badge badge-blocked">нет доступа</span>';
    document.getElementById('profile-tokens').textContent = (u.total_input_tokens + u.total_output_tokens).toLocaleString();
    document.getElementById('profile-searches').textContent = u.total_tavily_requests;
    document.getElementById('profile-created').textContent = new Date(u.created_at).toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove('hidden');
  }
}

// ==================== File Upload ====================
function handleFileSelect(file) {
  hideUploadError();
  if (file.type !== 'application/pdf') {
    showUploadError('Только PDF файлы!');
    selectedFile = null;
    resetUploadUI();
    return;
  }
  selectedFile = file;
  fileInfo.textContent = `📄 ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} МБ)`;
  uploadInfo.classList.remove('hidden');
  uploadBtn.classList.remove('hidden');
}

function resetUploadUI() {
  selectedFile = null;
  fileInput.value = '';
  uploadInfo.classList.add('hidden');
  uploadBtn.classList.add('hidden');
}

// ==================== Processing ====================
async function handleUpload() {
  if (!selectedFile) { showUploadError('Выбери файл!'); return; }
  hideUploadError();
  showProcessing();

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const response = await fetch('/api/process-pdf', {
      method: 'POST',
      headers: { Authorization: `Bearer ${currentUser.access_token}` },
      body: formData,
    });

    if (!response.ok) {
      let errMsg = 'Ошибка обработки';
      try { const d = await response.json(); errMsg = d.error || d.detail || errMsg; } catch (_) {}
      if (response.status === 403) {
        resetForm();
        showUploadError('У вас нет доступа к генерации отчётов. Обратитесь к администратору.');
        return;
      }
      throw new Error(errMsg);
    }

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/vnd.openxmlformats') && !contentType.includes('application/octet-stream')) {
      let errMsg = 'Сервер вернул неожиданный ответ';
      try { const d = await response.json(); errMsg = d.error || d.detail || errMsg; } catch (_) {}
      throw new Error(errMsg);
    }

    currentDocxBlob = await response.blob();
    document.getElementById('stat-tokens').textContent = (
      parseInt(response.headers.get('X-Input-Tokens') || '0') +
      parseInt(response.headers.get('X-Output-Tokens') || '0')
    ).toLocaleString();
    document.getElementById('stat-searches').textContent = response.headers.get('X-Tavily-Requests') || '0';
    showSuccess();
  } catch (error) {
    showError(error.message);
  }
}

function showProcessing() {
  uploadArea.style.display = 'none';
  uploadInfo.classList.add('hidden');
  uploadBtn.classList.add('hidden');
  resultsSection.classList.add('hidden');
  processingSection.classList.remove('hidden');
}

function showSuccess() {
  processingSection.classList.add('hidden');
  errorSection.classList.add('hidden');
  document.querySelector('.results-box.success').classList.remove('hidden');
  resultsSection.classList.remove('hidden');
}

function showError(message) {
  processingSection.classList.add('hidden');
  document.querySelector('.results-box.success').classList.add('hidden');
  document.getElementById('error-message').textContent = message;
  resultsSection.classList.remove('hidden');
  errorSection.classList.remove('hidden');
}

function resetForm() {
  selectedFile = null;
  currentDocxBlob = null;
  fileInput.value = '';
  uploadArea.style.display = 'block';
  uploadInfo.classList.add('hidden');
  uploadBtn.classList.add('hidden');
  processingSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  errorSection.classList.add('hidden');
  document.querySelector('.results-box.success').classList.remove('hidden');
  hideUploadError();
}

function downloadReport() {
  if (!currentDocxBlob) { showUploadError('Отчет недоступен'); return; }
  const url = URL.createObjectURL(currentDocxBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `pitch-deck-report_${new Date().getTime()}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ==================== Initialization ====================
function init() {
  const saved = localStorage.getItem('auth-token');
  if (saved) {
    currentUser = JSON.parse(saved);
    switchToMainScreen();
  } else {
    switchToLoginScreen();
  }
}

document.addEventListener('DOMContentLoaded', init);
