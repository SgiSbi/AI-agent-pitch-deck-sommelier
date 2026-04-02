const axios = require('axios');

const BACKEND_URL = process.env.BACKEND_URL || 'http://backend:8000';

/**
 * Login: proxy to backend /users/login, return JWT token to client
 */
async function login(req, res) {
  const { login, password } = req.body;

  if (!login || !password) {
    return res.status(400).json({ error: 'Login and password are required' });
  }

  try {
    const response = await axios.post(`${BACKEND_URL}/users/login`, { login, password });
    const { access_token } = response.data;
    // Fetch user profile to get role and other fields
    const meResponse = await axios.get(`${BACKEND_URL}/users/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    res.json({ success: true, access_token, ...meResponse.data });
  } catch (error) {
    const status = error.response?.status || 503;
    const detail = error.response?.data?.detail || 'Auth service unavailable';
    res.status(status).json({ error: detail });
  }
}

/**
 * Middleware: validate Bearer JWT by calling backend /users/me
 */
async function checkAuth(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const token = authHeader.slice(7);

  try {
    const response = await axios.get(`${BACKEND_URL}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    req.user = response.data;
    req.token = token;
    next();
  } catch (error) {
    const status = error.response?.status || 401;
    res.status(status).json({ error: 'Invalid or expired token' });
  }
}

module.exports = { login, checkAuth };
