const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
const axios = require('axios');
const FormData = require('form-data');
require('dotenv').config({ path: path.join(__dirname, '.env.frontend') });

const authMiddleware = require('./auth');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

const upload = multer({ storage: multer.memoryStorage() });

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

app.use((_req, res, next) => {
  res.setTimeout(600000, () => res.status(503).json({ error: 'Request timeout' }));
  next();
});

// Health checks
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

app.get('/api/backend-health', async (_req, res) => {
  try {
    await axios.get(`${BACKEND_URL}/docs`, { timeout: 5000 });
    res.json({ status: 'connected' });
  } catch (error) {
    res.status(503).json({ status: 'disconnected', error: error.message });
  }
});

// Auth endpoints
app.post('/api/auth/login', authMiddleware.login);
app.post('/api/auth/logout', (_req, res) => res.json({ success: true }));
app.get('/api/auth/check', authMiddleware.checkAuth, (req, res) => {
  res.json({ authenticated: true, login: req.user.login });
});

// Upload and process PDF
app.post('/api/process-pdf', authMiddleware.checkAuth, upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file provided' });
    }
    if (req.file.mimetype !== 'application/pdf') {
      return res.status(400).json({ error: 'Only PDF files are allowed' });
    }

    console.log(`[PDF Upload] Starting: ${req.file.originalname} (${req.file.size} bytes) for user: ${req.user.login}`);

    const formData = new FormData();
    formData.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: 'application/pdf',
    });

    const timeout = parseInt(process.env.BACKEND_TIMEOUT) || 600000;
    console.log(`[PDF Upload] Backend timeout: ${timeout}ms`);

    const response = await axios.post(
      `${BACKEND_URL}/pipeline/process-pdf`,
      formData,
      {
        headers: {
          ...formData.getHeaders(),
          Authorization: `Bearer ${req.token}`,
        },
        timeout,
        responseType: 'arraybuffer',
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
      }
    );

    console.log(`[PDF Upload] Success! File size: ${response.data.length} bytes`);

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    res.setHeader('Content-Disposition', 'attachment; filename="report.docx"');
    res.setHeader('X-Input-Tokens', response.headers['x-input-tokens'] || '0');
    res.setHeader('X-Output-Tokens', response.headers['x-output-tokens'] || '0');
    res.setHeader('X-Tavily-Requests', response.headers['x-tavily-requests'] || '0');

    res.send(response.data);
  } catch (error) {
    console.error(`[PDF Upload] Error: ${error.message}`);
    if (error.code === 'ECONNABORTED') {
      res.status(504).json({ error: 'Backend timeout', details: error.message });
    } else if (error.response) {
      res.status(error.response.status || 503).json({
        error: 'Backend processing failed',
        details: error.response.data?.detail || error.message,
      });
    } else {
      res.status(503).json({ error: 'Backend connection failed', details: error.message });
    }
  }
});

app.listen(PORT, () => {
  console.log(`✅ Web frontend running on http://localhost:${PORT}`);
  console.log(`📡 Backend: ${BACKEND_URL}`);
});
