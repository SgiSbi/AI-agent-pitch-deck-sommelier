async function savePasswordAfterOtp(event) {
  event.preventDefault();
  const err = document.getElementById('otp-password-error');
  err.textContent = 'Смена пароля через email временно отключена';
  err.classList.remove('hidden');
  return;

  /* Восстановление по email временно отключено
  const ok = document.getElementById('otp-password-success');
  ok.classList.add('hidden');
  err.classList.add('hidden');

  const newPassword = document.getElementById('otp-new-password').value;
  const repeat = document.getElementById('otp-new-password-repeat').value;
  if (newPassword !== repeat) {
    err.textContent = 'Новый пароль и повтор не совпадают';
    err.classList.remove('hidden');
    return;
  }

  try {
    const res = await fetch('/api/users/me/password/otp', {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_password: newPassword }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Не удалось сменить пароль');

    const user = getCurrentUser() || {};
    user.must_change_password = false;
    setCurrentUser(user);

    ok.textContent = data.detail || 'Пароль успешно изменен';
    ok.classList.remove('hidden');
    setTimeout(() => { window.location.href = '/generate'; }, 900);
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
  */
}

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth('/login');
  if (!user) return;
  renderTopNav('profile');
  if (!user.must_change_password) {
    window.location.href = '/profile';
    return;
  }
  document.getElementById('otp-password-form').addEventListener('submit', savePasswordAfterOtp);
});
