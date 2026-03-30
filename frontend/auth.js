const fs = require('fs');
const path = require('path');

const WHITELIST_PATH = path.join(__dirname, 'users_whitelist.json');

/**
 * Load users whitelist from JSON file
 */
function loadWhitelist() {
  try {
    if (!fs.existsSync(WHITELIST_PATH)) {
      return {};
    }
    const data = fs.readFileSync(WHITELIST_PATH, 'utf-8');
    return JSON.parse(data);
  } catch (error) {
    console.error('Error loading whitelist:', error);
    return {};
  }
}

/**
 * Get user role from whitelist
 */
function getUserRole(username) {
  if (!username) return null;
  const whitelist = loadWhitelist();
  const user = whitelist[username.toLowerCase()];
  return user ? user.role : null;
}

/**
 * Get user ID from whitelist
 */
function getUserId(username) {
  if (!username) return null;
  const whitelist = loadWhitelist();
  const user = whitelist[username.toLowerCase()];
  return user ? user.id : null;
}

/**
 * Check if user is in whitelist
 */
function isUserAllowed(username) {
  const role = getUserRole(username);
  return role === 'standard' || role === 'admin';
}

/**
 * Login middleware - validates username from whitelist
 */
function login(req, res) {
  const { username } = req.body;

  if (!username || typeof username !== 'string') {
    return res.status(400).json({ error: 'Username is required' });
  }

  if (!isUserAllowed(username)) {
    return res.status(403).json({ error: 'Access denied. User not in whitelist.' });
  }

  const userId = getUserId(username);
  const role = getUserRole(username);

  // Create session (in production, use JWT or sessions)
  res.json({
    success: true,
    username,
    id: userId,
    role,
  });
}

/**
 * Check auth middleware - verifies user session/token
 */
function checkAuth(req, res, next) {
  const authHeader = req.headers.authorization;
  
  if (!authHeader) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  // Simple auth: extract username from bearer token or query
  const username = req.headers['x-username'] || req.query.username;

  if (!username) {
    return res.status(401).json({ error: 'Username required' });
  }

  if (!isUserAllowed(username)) {
    return res.status(403).json({ error: 'Access denied' });
  }

  req.user = {
    username: username.toLowerCase(),
    id: getUserId(username),
  };

  next();
}

module.exports = {
  login,
  checkAuth,
  isUserAllowed,
  getUserRole,
  getUserId,
  loadWhitelist,
};
