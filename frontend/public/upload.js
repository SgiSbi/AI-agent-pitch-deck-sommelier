let selectedFile = null;
const SECTION_LABELS = {
  '1_info_from_pdf': 'Информация из презентации',
  '2_market_analyze': 'Анализ рынка',
  '3_competitors_analyze': 'Анализ конкурентов',
  '4_product_analyze': 'Анализ продукта',
  '5_team_analyze': 'Анализ команды',
  '6_final_verdict': 'Финальный вердикт',
};

async function generateSingleSection(section, file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('section', section);
  const res = await fetch('/api/process-pdf/section/async', {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Ошибка генерации секции: ${SECTION_LABELS[section] || section}`);
  }
  return res.json();
}

async function startGeneration() {
  const err = document.getElementById('upload-error');
  const ok = document.getElementById('upload-success');
  const mode = document.getElementById('generation-mode').value;
  err.classList.add('hidden');
  ok.classList.add('hidden');
  if (!selectedFile) return;
  try {
    if (mode === 'full') {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const res = await fetch('/api/process-pdf/async', {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        err.textContent = data.error || 'Ошибка запуска обработки';
        err.classList.remove('hidden');
        return;
      }
      ok.textContent = data.detail || 'Отчет принят в обработку';
      ok.classList.remove('hidden');
      return;
    }

    const selectedSections = Array.from(
      document.querySelectorAll('#sections-wrap input[type="checkbox"]:checked')
    ).map((el) => el.value);
    if (!selectedSections.length) {
      err.textContent = 'Для частичной генерации выберите хотя бы одну секцию.';
      err.classList.remove('hidden');
      return;
    }

    ok.textContent = 'Постановка выбранных секций в очередь...';
    ok.classList.remove('hidden');
    const accepted = [];
    for (const section of selectedSections) {
      ok.textContent = `Постановка в очередь: ${SECTION_LABELS[section] || section}`;
      const queued = await generateSingleSection(section, selectedFile);
      accepted.push(queued);
    }
    ok.textContent = 'Выбранные секции приняты в обработку и появятся в отчётах.';
  } catch (e) {
    err.textContent = e.message;
    err.classList.remove('hidden');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const user = requireAuth();
  if (!user) return;
  renderTopNav('upload');
  const modeSelect = document.getElementById('generation-mode');
  const sectionsWrap = document.getElementById('sections-wrap');
  modeSelect.onchange = () => {
    sectionsWrap.classList.toggle('hidden', modeSelect.value !== 'partial');
  };

  const uploadArea = document.getElementById('upload-area');
  const fileInput = document.getElementById('file-input');
  const uploadBtn = document.getElementById('upload-btn');
  uploadArea.onclick = () => fileInput.click();
  uploadArea.ondragover = (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); };
  uploadArea.ondragleave = () => uploadArea.classList.remove('dragover');
  uploadArea.ondrop = (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      fileInput.dispatchEvent(new Event('change'));
    }
  };
  fileInput.onchange = () => {
    if (!fileInput.files.length) return;
    const file = fileInput.files[0];
    if (file.type !== 'application/pdf') return;
    selectedFile = file;
    document.getElementById('upload-info').textContent = `Файл: ${file.name}`;
    document.getElementById('upload-info').classList.remove('hidden');
    uploadBtn.classList.remove('hidden');
  };
  uploadBtn.onclick = startGeneration;
});
