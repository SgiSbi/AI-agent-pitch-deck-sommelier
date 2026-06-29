async function loadProfile() {
  const err = document.getElementById('profile-error');
  err.classList.add('hidden');
  try {
    const res = await fetch('/api/users/me', { headers: authHeaders() });
    const u = await res.json();
    if (!res.ok) throw new Error(u.error || 'Ошибка загрузки профиля');
    setCurrentUser({ ...getCurrentUser(), ...u });
    document.getElementById('profile-info').innerHTML = `
      <div class="stat"><span class="stat-label">Логин</span><span class="stat-value">${escHtml(u.login)}</span></div>
      <div class="stat"><span class="stat-label">Роль</span><span class="stat-value">${escHtml(u.role)}</span></div>
      <div class="stat"><span class="stat-label">Токены (вход)</span><span class="stat-value">${(u.total_input_tokens || 0).toLocaleString()}</span></div>
      <div class="stat"><span class="stat-label">Токены (выход)</span><span class="stat-value">${(u.total_output_tokens || 0).toLocaleString()}</span></div>
      <div class="stat"><span class="stat-label">Токены (всего)</span><span class="stat-value">${((u.total_input_tokens || 0) + (u.total_output_tokens || 0)).toLocaleString()}</span></div>
      <div class="stat"><span class="stat-label">Поисков Tavily</span><span class="stat-value">${(u.total_tavily_requests || 0).toLocaleString()}</span></div>
    `;
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
}

// Email временно отключен
/*
async function saveEmail(event) {
  event.preventDefault();
  const email = document.getElementById('email-input').value.trim();
  const ok = document.getElementById('email-success');
  const err = document.getElementById('email-error');
  ok.classList.add('hidden');
  err.classList.add('hidden');
  try {
    const res = await fetch('/api/users/me/email', {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Не удалось сохранить email');
    ok.textContent = 'Email успешно сохранен.';
    ok.classList.remove('hidden');
    await loadProfile();
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
}
*/

async function changePassword(event) {
  event.preventDefault();
  const ok = document.getElementById('password-success');
  const err = document.getElementById('password-error');
  ok.classList.add('hidden');
  err.classList.add('hidden');

  const oldPassword = document.getElementById('old-password').value;
  const newPassword = document.getElementById('new-password').value;
  const repeatPassword = document.getElementById('new-password-repeat').value;
  if (newPassword !== repeatPassword) {
    err.textContent = 'Новый пароль и повтор не совпадают';
    err.classList.remove('hidden');
    return;
  }

  try {
    const res = await fetch('/api/users/me/password', {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Не удалось сменить пароль');
    ok.textContent = data.detail || 'Пароль успешно изменен';
    ok.classList.remove('hidden');
    document.getElementById('password-form').reset();
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth()) return;
  renderTopNav('profile');
  // document.getElementById('email-form').addEventListener('submit', saveEmail);
  document.getElementById('password-form').addEventListener('submit', changePassword);
  loadProfile();
});
