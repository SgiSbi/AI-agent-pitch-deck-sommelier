async function downloadReport(id, name) {
  const res = await fetch(`/api/pipeline/reports/${id}/download`, { headers: authHeaders() });
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name || 'report'}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function loadReports() {
  const wrap = document.getElementById('reports-wrap');
  const err = document.getElementById('reports-error');
  err.classList.add('hidden');
  const res = await fetch('/api/users/me/reports', { headers: authHeaders() });
  const reports = await res.json();
  if (!res.ok) {
    err.textContent = reports.error || 'Ошибка';
    err.classList.remove('hidden');
    return;
  }
  if (!reports.length) {
    wrap.textContent = 'У вас пока нет отчетов.';
    return;
  }
  wrap.innerHTML = `
    <div class="table-scroll"><table class="admin-table">
      <thead><tr><th>ID</th><th>Презентация</th><th>Статус</th><th>Дата</th><th></th></tr></thead>
      <tbody>
        ${reports.map((r) => `
          <tr>
            <td>${r.id}</td>
            <td>${escHtml(r.presentation_dir)}</td>
            <td>${escHtml(r.status)}</td>
            <td>${new Date(r.created_at).toLocaleString('ru-RU')}</td>
            <td>${r.status === 'completed' ? `<button class="btn btn-outline btn-xs" data-id="${r.id}" data-name="${escHtml(r.presentation_dir)}">Скачать</button>` : '<span class="muted">в обработке</span>'}</td>
          </tr>`).join('')}
      </tbody>
    </table></div>
  `;
  wrap.querySelectorAll('button[data-id]').forEach((btn) => {
    btn.onclick = () => downloadReport(btn.dataset.id, btn.dataset.name);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth()) return;
  renderTopNav('reports');
  loadReports();
});
