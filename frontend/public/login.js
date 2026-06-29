// let resetEmail = '';

function showPanel(id) {
  ['login-panel', 'register-panel' /* , 'reset-panel' */].forEach((panelId) => {
    document.getElementById(panelId).classList.toggle('hidden', panelId !== id);
  });
}

async function login(event) {
  event.preventDefault();
  const loginValue = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const err = document.getElementById('login-error');
  err.classList.add('hidden');
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login: loginValue, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    err.textContent = data.error || 'Ошибка авторизации';
    err.classList.remove('hidden');
    return;
  }
  setCurrentUser(data);
  // if (data.must_change_password) {
  //   window.location.href = '/change-password';
  //   return;
  // }
  window.location.href = '/generate';
}

async function register(event) {
  event.preventDefault();
  const err = document.getElementById('register-error');
  const ok = document.getElementById('register-success');
  err.classList.add('hidden');
  ok.classList.add('hidden');
  const payload = {
    login: document.getElementById('reg-username').value.trim(),
    password: document.getElementById('reg-password').value,
    email: null,
  };
  if (payload.password !== document.getElementById('reg-password2').value) {
    err.textContent = 'Пароли не совпадают';
    err.classList.remove('hidden');
    return;
  }
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    err.textContent = data.error || 'Ошибка регистрации';
    err.classList.remove('hidden');
    return;
  }
  ok.textContent = 'Аккаунт создан. Теперь войдите.';
  ok.classList.remove('hidden');
}

// Восстановление пароля по email временно отключено
/*
async function requestReset(event) {
  event.preventDefault();
  const email = document.getElementById('reset-email').value.trim();
  const msg = document.getElementById('reset-message');
  const err = document.getElementById('reset-error');
  msg.classList.add('hidden');
  err.classList.add('hidden');
  const res = await fetch('/api/auth/password-reset/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  const data = await res.json();
  if (!res.ok) {
    err.textContent = data.error || 'Ошибка отправки OTP';
    err.classList.remove('hidden');
    return;
  }
  resetEmail = email;
  document.getElementById('reset-verify-form').classList.remove('hidden');
  msg.textContent = data.detail || 'Если email зарегистрирован, OTP отправлен';
  msg.classList.remove('hidden');
}

async function verifyReset(event) {
  event.preventDefault();
  const email = resetEmail || document.getElementById('reset-email').value.trim();
  const otp = document.getElementById('verify-otp').value.trim();
  const err = document.getElementById('reset-error');
  err.classList.add('hidden');
  const res = await fetch('/api/auth/password-reset/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  });
  const data = await res.json();
  if (!res.ok) {
    err.textContent = data.error || 'Неверный OTP';
    err.classList.remove('hidden');
    return;
  }
  setCurrentUser(data);
  window.location.href = data.must_change_password ? '/change-password' : '/generate';
}
*/

document.addEventListener('DOMContentLoaded', () => {
  renderTopNav('login');
  if (getCurrentUser()) {
    // const current = getCurrentUser();
    // window.location.href = current?.must_change_password ? '/change-password' : '/generate';
    window.location.href = '/generate';
    return;
  }
  document.getElementById('login-form').addEventListener('submit', login);
  document.getElementById('register-form').addEventListener('submit', register);
  // document.getElementById('reset-request-form').addEventListener('submit', requestReset);
  // document.getElementById('reset-verify-form').addEventListener('submit', verifyReset);
  document.getElementById('show-register').addEventListener('click', (e) => { e.preventDefault(); showPanel('register-panel'); });
  // document.getElementById('show-reset').addEventListener('click', (e) => { e.preventDefault(); showPanel('reset-panel'); });
  document.getElementById('show-login-from-register').addEventListener('click', (e) => { e.preventDefault(); showPanel('login-panel'); });
  // document.getElementById('show-login-from-reset').addEventListener('click', (e) => { e.preventDefault(); showPanel('login-panel'); });
});
