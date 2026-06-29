async function loadUsers() {
  const wrap = document.getElementById('users-wrap');
  const err = document.getElementById('admin-error');
  err.classList.add('hidden');
  const res = await fetch('/api/admin/users', { headers: authHeaders() });
  const users = await res.json();
  if (!res.ok) {
    err.textContent = users.error || 'Ошибка загрузки';
    err.classList.remove('hidden');
    return;
  }
  wrap.innerHTML = `
    <div class="table-scroll"><table class="admin-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Логин</th>
          <th>Email</th>
          <th>Роль</th>
          <th>Токены</th>
          <th>Tavily</th>
          <th>Отчеты</th>
        </tr>
      </thead>
      <tbody>
        ${users.map((u) => `
          <tr>
            <td>${u.id}</td>
            <td>${escHtml(u.login)}</td>
            <td>${escHtml(u.email || '—')}</td>
            <td>${escHtml(u.role)}</td>
            <td class="td-stats">${((u.total_input_tokens || 0) + (u.total_output_tokens || 0)).toLocaleString()}</td>
            <td class="td-stats">${(u.total_tavily_requests || 0).toLocaleString()}</td>
            <td class="td-stats">${(u.reports_count || 0).toLocaleString()}</td>
          </tr>
        `).join('')}
      </tbody>
    </table></div>
  `;
}

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth();
  if (!user) return;
  if (user.role !== 'admin') {
    window.location.href = '/generate';
    return;
  }
  renderTopNav('admin');
  loadUsers();
});
