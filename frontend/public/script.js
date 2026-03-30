// State
let currentUser = null;
let selectedFile = null;
let currentDocxBlob = null;

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const mainScreen = document.getElementById('main-screen');
const loginForm = document.getElementById('login-form');
const usernameInput = document.getElementById('username');
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

// Combined event listener for upload area (drag & drop + click)
uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
  uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    handleFileSelect(files[0]);
  }
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    handleFileSelect(e.target.files[0]);
  }
});

downloadBtn.addEventListener('click', downloadReport);
logoutBtn.addEventListener('click', handleLogout);

// ==================== Login ====================
async function handleLogin(event) {
  event.preventDefault();
  const username = usernameInput.value.trim();

  if (!username) {
    showLoginError('Пожалуйста, введи username');
    return;
  }

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });

    const data = await response.json();

    if (!response.ok) {
      showLoginError(data.error || 'Неверные учетные данные');
      return;
    }

    currentUser = data;
    localStorage.setItem('auth-token', JSON.stringify(data));
    hideLoginError();
    switchToMainScreen();
  } catch (error) {
    console.error('Login error:', error);
    showLoginError('Ошибка подключения к серверу');
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
function switchToLoginScreen() {
  loginScreen.classList.add('active');
  mainScreen.classList.remove('active');
  usernameInput.value = '';
  hideLoginError();
}

function switchToMainScreen() {
  loginScreen.classList.remove('active');
  mainScreen.classList.add('active');
  userDisplay.textContent = `👤 ${currentUser.username}`;
  resetForm();
}

function showLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove('hidden');
}

function hideLoginError() {
  loginError.classList.add('hidden');
}

function showUploadError(message) {
  uploadError.textContent = '❌ ' + message;
  uploadError.classList.remove('hidden');
}

function hideUploadError() {
  uploadError.classList.add('hidden');
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
  if (!selectedFile) {
    showUploadError('Выбери файл!');
    return;
  }

  hideUploadError();
  showProcessing();

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const response = await fetch('/api/process-pdf', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${currentUser.username}`,
        'X-Username': currentUser.username,
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Ошибка обработки');
    }

    // Get response as blob
    const docxBlob = await response.blob();
    currentDocxBlob = docxBlob;

    // Extract stats from headers
    const inputTokens = response.headers.get('X-Input-Tokens') || '0';
    const outputTokens = response.headers.get('X-Output-Tokens') || '0';
    const tavilyRequests = response.headers.get('X-Tavily-Requests') || '0';

    const totalTokens = parseInt(inputTokens) + parseInt(outputTokens);

    document.getElementById('stat-tokens').textContent = totalTokens.toLocaleString();
    document.getElementById('stat-searches').textContent = tavilyRequests;

    showSuccess();
  } catch (error) {
    console.error('Upload error:', error);
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
  resultsSection.classList.remove('hidden');
}

function showError(message) {
  processingSection.classList.add('hidden');
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
  hideUploadError();
}

function downloadReport() {
  if (!currentDocxBlob) {
    showUploadError('Отчет недоступен');
    return;
  }

  const url = URL.createObjectURL(currentDocxBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `pitch-deck-report_${new Date().getTime()}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ==================== Initialization ====================
function init() {
  // Check if user is already logged in
  const saved = localStorage.getItem('auth-token');
  if (saved) {
    currentUser = JSON.parse(saved);
    switchToMainScreen();
  } else {
    switchToLoginScreen();
  }

  // Check backend connection
  checkBackendConnection();
}

async function checkBackendConnection() {
  try {
    const response = await fetch('/api/backend-health');
    if (!response.ok) {
      console.warn('Backend might be unavailable');
    }
  } catch (error) {
    console.error('Cannot reach backend:', error);
  }
}

// Start
document.addEventListener('DOMContentLoaded', init);
