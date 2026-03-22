const fs = require('fs');
const path = require('path');

const COOKIE_FILE = path.join(__dirname, '.session-cookies.json');

/**
 * Load session cookies from cache
 */
function loadCookies() {
  try {
    if (fs.existsSync(COOKIE_FILE)) {
      const data = fs.readFileSync(COOKIE_FILE, 'utf8');
      return JSON.parse(data);
    }
  } catch (err) {
    console.log('Error loading cookies:', err.message);
  }
  return null;
}

/**
 * Save session cookies to cache
 */
function saveCookies(cookies) {
  fs.writeFileSync(COOKIE_FILE, JSON.stringify(cookies, null, 2));
}

/**
 * Clear cached cookies
 */
function clearCookies() {
  if (fs.existsSync(COOKIE_FILE)) {
    fs.unlinkSync(COOKIE_FILE);
  }
}

/**
 * Build Cookie header from cookies object
 */
function buildCookieHeader(cookies) {
  return Object.entries(cookies)
    .map(([key, value]) => `${key}=${value}`)
    .join('; ');
}

/**
 * Extract cookies from Set-Cookie header
 */
function extractCookies(setCookieHeader) {
  if (!setCookieHeader) return {};
  
  const cookies = {};
  const cookieStrings = setCookieHeader.split(', ');
  
  for (const cookieStr of cookieStrings) {
    const eqIdx = cookieStr.indexOf('=');
    if (eqIdx > 0) {
      const name = cookieStr.substring(0, eqIdx);
      const val = cookieStr.substring(eqIdx + 1).split(';')[0];
      cookies[name] = val;
    }
  }
  
  return cookies;
}

/**
 * Generate random string
 */
function generateRandomString(length) {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
}

/**
 * Login with email/password - returns session cookies
 * @param {string} email 
 * @param {string} password 
 * @returns {Promise<Object>} Session cookies
 */
async function login(email, password) {
  // Check for valid cached cookies first
  const cached = loadCookies();
  if (cached && (cached.profile || Object.keys(cached).some(k => k.startsWith('x-ms-cpim-sso')))) {
    console.log('Using cached session');
    return cached;
  }

  // Perform login via Azure AD B2C flow
  const cookies = await authenticateWithB2C(email, password);
  
  // Check for session cookie (profile or x-ms-cpim-sso)
  const hasSessionCookie = cookies && (cookies.profile || Object.keys(cookies).some(k => k.startsWith('x-ms-cpim-sso')));
  
  if (hasSessionCookie) {
    saveCookies(cookies);
    console.log('Login successful! Session cached.');
  } else {
    throw new Error('Login failed - no session cookie received');
  }
  
  return cookies;
}

/**
 * Full Azure AD B2C OAuth flow with cookies
 */
async function authenticateWithB2C(email, password) {
  const CLIENT_ID = '40c94bb1-2d83-4ccc-8c72-fde8ad15ed24';
  const AUTHORITY = 'https://login.gruppohera.it/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web';
  
  // Step 1: Get initial session and extract TID
  const state = generateRandomString(32);
  const nonce = generateRandomString(32);
  // Generate code_verifier first (43-128 chars, alphanumeric + -._)
  const codeVerifier = generateRandomString(43);
  // Then derive code_challenge from code_verifier using SHA256
  const crypto = require('crypto');
  const codeChallenge = crypto.createHash('sha256').update(codeVerifier).digest('base64url');
  const clientRequestId = generateRandomString(36);
  
  const authorizeUrl = `${AUTHORITY}/oauth2/v2.0/authorize?` + new URLSearchParams({
    client_id: CLIENT_ID,
    scope: 'openid offline_access https://myheraapp.onmicrosoft.com/40c94bb1-2d83-4ccc-8c72-fde8ad15ed24/read profile',
    redirect_uri: 'https://servizionline.gruppohera.it/auth/hera/login',
    response_type: 'code',
    response_mode: 'fragment',
    state: JSON.stringify({ id: generateRandomString(), meta: { interactionType: 'redirect' } }),
    nonce,
    'client-request-id': clientRequestId,
    'code_challenge': codeChallenge,
    'code_challenge_method': 'S256',
    referrer: 'hera',
    env: 'prod'
  });

  console.log('Step 1: Getting initial session...');
  const sessionResponse = await fetch(authorizeUrl, {
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Language': 'en-US,en;q=0.5',
    },
    redirect: 'manual'
  });

  let cookies = extractCookies(sessionResponse.headers.get('set-cookie'));
  
  if (!cookies['x-ms-cpim-csrf']) {
    throw new Error('Failed to get CSRF token from initial session');
  }
  
  // Extract TID from x-ms-cpim-trans cookie
  const transCookie = cookies['x-ms-cpim-trans'];
  let tid = null;
  
  if (transCookie) {
    try {
      // The cookie is a single base64-encoded JSON (NOT dot-separated)
      const padded = transCookie + '='.repeat((4 - transCookie.length % 4) % 4);
      const json = Buffer.from(padded, 'base64').toString();
      const data = JSON.parse(json);
      // TID is in T_DIC[0].I or C_ID
      tid = data.T_DIC?.[0]?.I || data.C_ID;
    } catch (e) {
      console.log('Warning: Could not extract TID from trans cookie:', e.message);
    }
  }
  
  // If we couldn't extract TID, generate one (fallback)
  if (!tid) {
    tid = generateRandomString(36);
    console.log('  Generated TID:', tid);
  } else {
    console.log('  Got TID:', tid);
  }
  
  console.log('  Got CSRF token');

  // Step 2: Submit credentials to SelfAsserted endpoint with correct tx parameter
  const csrfToken = cookies['x-ms-cpim-csrf'];
  const txState = Buffer.from(JSON.stringify({ TID: tid })).toString('base64');
  const selfAssertedUrl = `${AUTHORITY}/SelfAsserted?tx=StateProperties=${txState}&p=B2C_1A_SignIn_Web`;

  console.log('Step 2: Submitting credentials...');
  const credResponse = await fetch(selfAssertedUrl, {
    method: 'POST',
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json, text/javascript, */*; q=0.01',
      'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      'X-CSRF-TOKEN': csrfToken,
      'X-Requested-With': 'XMLHttpRequest',
      'Origin': 'https://login.gruppohera.it',
      'Referer': authorizeUrl,
      'Cookie': buildCookieHeader(cookies),
    },
    body: new URLSearchParams({
      request_type: 'RESPONSE',
      signInName: email,
      password: password
    })
  });

  if (!credResponse.ok) {
    const error = await credResponse.text();
    throw new Error(`Authentication failed: ${error} (status: ${credResponse.status})`);
  }

  const credData = await credResponse.json();
  
  if (credData.status === '400' || credData.status === 400 || credData.errors) {
    throw new Error('Invalid credentials or authentication error: ' + JSON.stringify(credData));
  }
  
  // Update cookies from SelfAsserted response (includes x-ms-cpim-cache cookies)
  const credCookies = extractCookies(credResponse.headers.get('set-cookie'));
  for (const [key, value] of Object.entries(credCookies)) {
    cookies[key] = value;
  }
  
  console.log('  Credentials accepted');
  console.log('  Updated cookies:', Object.keys(cookies).join(', '));

  // Step 3: Call CombinedSigninAndSignup/confirmed to get the redirect
  console.log('Step 3: Getting redirect...');
  
  // The csrf_token is already in the x-ms-cpim-csrf cookie - use it directly
  const csrfTokenFull = cookies['x-ms-cpim-csrf'];
  
  // Build diags parameter with trace data (from HAR analysis)
  // acST is Unix timestamp in seconds, acD is duration in ms
  const pageViewId = generateRandomString(36);
  const baseTime = Math.floor(Date.now() / 1000); // Unix timestamp in seconds
  const diags = JSON.stringify({
    pageViewId: pageViewId,
    pageId: 'CombinedSigninAndSignup',
    trace: [
      { ac: 'T005', acST: baseTime, acD: 1 },
      { ac: 'T021 - URL:https://myhera-e4fvcthmd6a3epam.a03.azurefd.net/b2c/login_sol.html', acST: baseTime, acD: 500 },
      { ac: 'T019', acST: baseTime + 1, acD: 3 },
      { ac: 'T004', acST: baseTime + 1, acD: 2 },
      { ac: 'T003', acST: baseTime + 1, acD: 2 },
      { ac: 'T035', acST: baseTime + 1, acD: 0 },
      { ac: 'T030Online', acST: baseTime + 1, acD: 0 },
      { ac: 'T002', acST: baseTime + 17, acD: 0 },
      { ac: 'T018T010', acST: baseTime + 16, acD: 1040 }
    ]
  });
  
  const combinedUrl = `${AUTHORITY}/api/CombinedSigninAndSignup/confirmed?rememberMe=false&csrf_token=${encodeURIComponent(csrfTokenFull)}&tx=StateProperties=${txState}&p=B2C_1A_SignIn_Web`;

  // Build exact Referer from the authorize request (with all original params)
  const authorizeReferer = `${AUTHORITY.toLowerCase()}/oauth2/v2.0/authorize?` + new URLSearchParams({
    client_id: CLIENT_ID,
    scope: 'openid offline_access https://myheraapp.onmicrosoft.com/40c94bb1-2d83-4ccc-8c72-fde8ad15ed24/read profile',
    redirect_uri: 'https://servizionline.gruppohera.it/auth/hera/login',
    response_type: 'code',
    response_mode: 'fragment',
    state: JSON.stringify({ id: generateRandomString(), meta: { interactionType: 'redirect' } }),
    nonce,
    'client-request-id': clientRequestId,
    'code_challenge': codeChallenge,
    'code_challenge_method': 'S256',
    referrer: 'hera',
    env: 'prod'
  });

  const combinedResponse = await fetch(combinedUrl, {
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
      'Cookie': buildCookieHeader(cookies),
      'Referer': authorizeReferer,
      'DNT': '1',
      'Upgrade-Insecure-Requests': '1',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'same-origin',
      'Sec-Fetch-User': '?1',
      'Pragma': 'no-cache',
      'Cache-Control': 'no-cache',
    },
    redirect: 'manual'
  });

  if (combinedResponse.status !== 302) {
    const body = await combinedResponse.text();
    throw new Error(`Expected 302 redirect, got ${combinedResponse.status}: ${body.substring(0, 200)}`);
  }

  const location = combinedResponse.headers.get('location');
  if (!location) {
    throw new Error('No redirect location from CombinedSigninAndSignup');
  }
  console.log('  Got redirect location:', location.substring(0, 100) + '...');

  // Update cookies from CombinedSigninAndSignup response
  const combinedCookies = extractCookies(combinedResponse.headers.get('set-cookie'));
  for (const [key, value] of Object.entries(combinedCookies)) {
    cookies[key] = value;
  }

  // Step 4: Extract code from redirect URL and exchange for token
  console.log('Step 3: Exchanging code for token...');
  
  // The location URL has the code in the fragment (#code=...)
  // Need to parse hash manually since URLSearchParams doesn't work with fragments
  const hashIdx = location.indexOf('#');
  if (hashIdx === -1) {
    throw new Error('No hash fragment in redirect URL');
  }
  const codeFragment = location.substring(hashIdx + 1);
  const params = new URLSearchParams(codeFragment);
  const code = params.get('code');
  
  if (!code) {
    throw new Error('No code in redirect URL fragment');
  }
  
  // Build the callback URL (without hash for the initial request)
  const callbackUrl = location.substring(0, hashIdx);
  
  // Exchange code for token using the original code_verifier
  const tokenUrl = `${AUTHORITY}/oauth2/v2.0/token`;
  const tokenResponse = await fetch(tokenUrl, {
    method: 'POST',
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json',
      'Content-Type': 'application/x-www-form-urlencoded',
      'Cookie': buildCookieHeader(cookies),
    },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      redirect_uri: 'https://servizionline.gruppohera.it/auth/hera/login',
      scope: 'openid offline_access https://myheraapp.onmicrosoft.com/40c94bb1-2d83-4ccc-8c72-fde8ad15ed24/read profile',
      code: code,
      grant_type: 'authorization_code',
      code_verifier: codeVerifier,  // Use the original code_verifier
      client_info: '1',
      'x-client-SKU': 'msal.js.browser',
      'x-client-VER': '2.35.0',
    })
  });

  if (!tokenResponse.ok) {
    const error = await tokenResponse.text();
    throw new Error(`Token exchange failed: ${error}`);
  }

  const tokenData = await tokenResponse.json();
  console.log('  Got access token');

  // Save the access token for API calls
  cookies.accessToken = tokenData.access_token;

  // Update cookies from token response
  const tokenCookies = extractCookies(tokenResponse.headers.get('set-cookie'));
  for (const [key, value] of Object.entries(tokenCookies)) {
    cookies[key] = value;
  }

  // Step 5: Now call servizionline.gruppohera.it to establish session
  // The app will use the token to authenticate and set the profile cookie
  console.log('Step 4: Establishing session with servizionline...');
  
  const callbackResponse = await fetch(callbackUrl, {
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
      'Cookie': buildCookieHeader(cookies),
      'Referer': 'https://servizionline.gruppohera.it/',
    },
    redirect: 'follow'
  });

  // Extract final cookies
  const finalCookies = extractCookies(callbackResponse.headers.get('set-cookie'));
  for (const [key, value] of Object.entries(finalCookies)) {
    cookies[key] = value;
  }

  console.log('  Response URL:', callbackResponse.url);
  console.log('  Cookies received:', Object.keys(cookies).join(', '));

  // Check for profile cookie or x-ms-cpim-sso as session indicator
  // The x-ms-cpim-sso cookie might be the actual session cookie
  const hasSessionCookie = cookies.profile || Object.keys(cookies).some(k => k.startsWith('x-ms-cpim-sso'));
  
  if (!hasSessionCookie) {
    console.error('Available cookies:', Object.keys(cookies));
    throw new Error('No session cookie received - authentication may have failed');
  }
  
  console.log('  Session established!');

  return cookies;
}

/**
 * Logout - clear cached cookies
 */
function logout() {
  clearCookies();
  console.log('Logged out. Session cleared.');
}

/**
 * Get cookie header string for API calls
 */
function getCookieHeader() {
  const cookies = loadCookies();
  if (!cookies) return null;
  return buildCookieHeader(cookies);
}

module.exports = { login, logout, getCookieHeader, loadCookies };
