function getCurrentUser() {
  const saved = localStorage.getItem('auth-token');
  if (!saved) return null;
  try {
    return JSON.parse(saved);
  } catch (_) {
    return null;
  }
}

function setCurrentUser(user) {
  localStorage.setItem('auth-token', JSON.stringify(user));
}

function clearCurrentUser() {
  localStorage.removeItem('auth-token');
}

function authHeaders() {
  const user = getCurrentUser();
  return user ? { Authorization: `Bearer ${user.access_token}` } : {};
}

function requireAuth(redirect = '/login') {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = redirect;
    return null;
  }
  // Смена пароля через email временно отключена
  // if (user.must_change_password && window.location.pathname !== '/change-password') {
  //   window.location.href = '/change-password';
  //   return null;
  // }
  return user;
}

function logout() {
  clearCurrentUser();
  window.location.href = '/';
}

function escHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function hasAuthorizationHeader(headers) {
  if (!headers) return false;
  if (headers instanceof Headers) {
    return Boolean(headers.get('Authorization'));
  }
  if (Array.isArray(headers)) {
    return headers.some(([k, _v]) => String(k).toLowerCase() === 'authorization');
  }
  return Object.keys(headers).some((k) => k.toLowerCase() === 'authorization');
}

if (!window.__authFetchPatched) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const response = await originalFetch(input, init);
    const isAuthorizedCall = hasAuthorizationHeader(init?.headers);
    const isAuthPage = window.location.pathname === '/login';
    if (response.status === 401 && isAuthorizedCall && !isAuthPage) {
      clearCurrentUser();
      window.location.href = '/login';
    }
    return response;
  };
  window.__authFetchPatched = true;
}

function goToGeneration() {
  const user = getCurrentUser();
  if (!user) {
    window.location.href = '/login';
    return;
  }
  // if (user.must_change_password) {
  //   window.location.href = '/change-password';
  //   return;
  // }
  window.location.href = '/generate';
}

function renderTopNav(activePage = '') {
  const target = document.getElementById('top-nav');
  if (!target) return;
  const user = getCurrentUser();
  const loginLabel = user ? 'Выход' : 'Вход';
  const userLabel = user ? `👤 ${escHtml(user.login)}` : '👤 Гость';
  target.innerHTML = `
    <header class="header">
      <div class="container header-row">
        <h1 class="logo-link" id="brand-link">Pitch Deck Sommelier</h1>
        <div class="user-info">
          <span class="user-display">${userLabel}</span>
          <button id="nav-home" class="btn btn-outline btn-small">Главная</button>
          <button id="nav-generate" class="btn btn-outline btn-small">Генерация</button>
          <button id="nav-profile" class="btn btn-outline btn-small">Профиль</button>
          <button id="nav-reports" class="btn btn-outline btn-small">Отчеты</button>
          <button id="nav-admin" class="btn btn-outline btn-small">Админ</button>
          <button id="nav-auth" class="btn btn-outline btn-small">${loginLabel}</button>
        </div>
      </div>
    </header>
  `;

  target.querySelector('#brand-link').onclick = () => (window.location.href = '/');
  target.querySelector('#nav-home').onclick = () => (window.location.href = '/');
  target.querySelector('#nav-generate').onclick = () => goToGeneration();
  target.querySelector('#nav-profile').onclick = () => (window.location.href = user ? '/profile' : '/login');
  target.querySelector('#nav-reports').onclick = () => (window.location.href = user ? '/reports' : '/login');
  target.querySelector('#nav-admin').onclick = () => (window.location.href = user ? '/admin' : '/login');
  target.querySelector('#nav-auth').onclick = () => (user ? logout() : (window.location.href = '/login'));

  const activeByPage = {
    home: 'nav-home',
    upload: 'nav-generate',
    profile: 'nav-profile',
    reports: 'nav-reports',
    admin: 'nav-admin',
    login: 'nav-auth',
  };
  const activeBtnId = activeByPage[activePage];
  if (activeBtnId) {
    const activeBtn = target.querySelector(`#${activeBtnId}`);
    if (activeBtn) activeBtn.classList.add('nav-active');
  }
}
