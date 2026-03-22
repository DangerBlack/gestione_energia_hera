const fs = require('fs');
const path = require('path');

const CACHE_FILE = path.join(__dirname, '.token-cache.json');

/**
 * Load cached tokens from file
 * @returns {Object|null} Cached tokens or null if not found
 */
function loadTokens() {
  try {
    if (fs.existsSync(CACHE_FILE)) {
      const data = fs.readFileSync(CACHE_FILE, 'utf8');
      return JSON.parse(data);
    }
  } catch (err) {
    console.error('Error loading tokens:', err.message);
  }
  return null;
}

/**
 * Save tokens to file
 * @param {Object} tokens - Token object with access_token, refresh_token, expires_at
 */
function saveTokens(tokens) {
  try {
    fs.writeFileSync(CACHE_FILE, JSON.stringify(tokens, null, 2));
  } catch (err) {
    console.error('Error saving tokens:', err.message);
  }
}

/**
 * Clear cached tokens
 */
function clearTokens() {
  try {
    if (fs.existsSync(CACHE_FILE)) {
      fs.unlinkSync(CACHE_FILE);
    }
  } catch (err) {
    console.error('Error clearing tokens:', err.message);
  }
}

/**
 * Check if cached token is still valid
 * @param {Object} tokens - Cached tokens
 * @returns {boolean} True if token is valid
 */
function isTokenValid(tokens) {
  if (!tokens || !tokens.expires_at) return false;
  return Date.now() < tokens.expires_at - 60000; // 1 min buffer
}

module.exports = { loadTokens, saveTokens, clearTokens, isTokenValid };
