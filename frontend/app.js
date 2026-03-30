const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
require('dotenv').config({ path: path.join(__dirname, '.env.frontend') });

const authMiddleware = require('./auth');

const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

// Configure multer for file uploads
const upload = multer({ storage: multer.memoryStorage() });

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Set timeout for all requests to 10 minutes (600 seconds)
app.use((req, res, next) => {
  res.setTimeout(600000, () => {
    res.status(503).json({ error: 'Request timeout' });
  });
  next();
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

// Check backend connection
app.get('/api/backend-health', async (req, res) => {
  try {
    const axios = require('axios');
    const response = await axios.get(`${BACKEND_URL}/docs`, { timeout: 5000 });
    res.json({ status: 'connected' });
  } catch (error) {
    res.status(503).json({ status: 'disconnected', error: error.message });
  }
});

// Auth check endpoint
app.post('/api/auth/login', authMiddleware.login);
app.post('/api/auth/logout', (req, res) => {
  res.json({ success: true });
});
app.get('/api/auth/check', authMiddleware.checkAuth, (req, res) => {
  res.json({ authenticated: true, username: req.user.username });
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

    console.log(`[PDF Upload] Starting: ${req.file.originalname} (${req.file.size} bytes) for user: ${req.user.username}`);

    const axios = require('axios');
    const FormData = require('form-data');

    const formData = new FormData();
    formData.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: 'application/pdf',
    });
    formData.append('username', req.user.username);
    formData.append('user_id', req.user.id);

    // Use timeout from .env or default to 10 minutes
    const timeout = parseInt(process.env.BACKEND_TIMEOUT) || 600000;
    console.log(`[PDF Upload] Backend timeout: ${timeout}ms (${(timeout / 1000 / 60).toFixed(1)} minutes)`);

    const response = await axios.post(
      `${BACKEND_URL}/process-pdf`,
      formData,
      {
        headers: formData.getHeaders(),
        timeout: timeout,
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
      console.error('[PDF Upload] Request timeout - backend is taking too long');
      res.status(504).json({ error: 'Backend timeout - processing is taking too long', details: error.message });
    } else if (error.response) {
      console.error(`[PDF Upload] Backend error: ${error.response.status}`);
      res.status(error.response.status || 503).json({ 
        error: 'Backend processing failed', 
        details: error.response.data?.detail || error.message 
      });
    } else {
      console.error('[PDF Upload] Connection error', error.message);
      res.status(503).json({ error: 'Backend connection failed', details: error.message });
    }
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`✅ Web frontend running on http://localhost:${PORT}`);
  console.log(`📡 Backend: ${BACKEND_URL}`);
});

