const { getCookieHeader, loadCookies } = require('./auth');

const API_BASE = 'https://myhera.gruppohera.it';
const SERVIZIONLINE_BASE = 'https://servizionline.gruppohera.it';

/**
 * Get authorization header (Bearer token)
 */
function getAuthHeader() {
  const cookies = loadCookies();
  if (!cookies || !cookies.accessToken) {
    return null;
  }
  return `Bearer ${cookies.accessToken}`;
}

/**
 * Get the authenticated user's profile ID
 * Fetches from /api/mw/v1/profile/list endpoint
 * @returns {Promise<string>} Profile ID
 */
async function getProfileId() {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Try environment variable first (for CI/CD)
  const envProfileId = process.env.HERA_PROFILE_ID;
  if (envProfileId) {
    return envProfileId;
  }

  // Extract profile ID from cookie if available
  const profileMatch = cookieHeader.match(/profile=([^;]+)/);
  if (profileMatch) {
    return profileMatch[1].trim();
  }

  // Fetch profile list from API as fallback
  const response = await fetch(`${API_BASE}/api/mw/v1/profile/list`, {
    headers: {
      'Cookie': cookieHeader,
      'Authorization': authHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get profile list: ${response.status}`);
  }

  const data = await response.json();
  
  if (!data.list || data.list.length === 0) {
    throw new Error('No profiles found for this user');
  }

  // Return the first profile ID (or the default one if marked)
  const defaultProfile = data.list.find(p => p.isDefault);
  return (defaultProfile || data.list[0]).id;
}

/**
 * Get list of bills for the authenticated user
 * @returns {Promise<Array>} List of bills
 */
async function getBills() {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Dynamically get profile ID - NO hardcoded values
  const profileId = await getProfileId();

  // Get bills from the myhera API with Bearer token
  const response = await fetch(`${API_BASE}/api/mw/v1/profile/${profileId}/bill/list`, {
    headers: {
      'Cookie': cookieHeader,
      'Authorization': authHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json',
      'Referer': 'https://servizionline.gruppohera.it/bill/list',
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get bills: ${response.status} ${error}`);
  }

  const data = await response.json();
  return data.list || [];
}

/**
 * Download a specific bill (PDF)
 * @param {string} billId - Bill identifier 
 * @returns {Promise<Buffer>} Bill PDF as buffer
 */
async function downloadBill(billId) {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Dynamically get profile ID - NO hardcoded values
  const profileId = await getProfileId();
  
  // Use the servizionline API endpoint (from HAR analysis)
  const url = `https://servizionline.gruppohera.it/api/profile/${profileId}/bill/export/pdf/${billId}`;

  // Build cookie header with profile cookie
  const fullCookie = cookieHeader + '; profile=' + profileId;

  const response = await fetch(url, {
    headers: {
      'Cookie': fullCookie,
      'Authorization': authHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/pdf',
      'Referer': 'https://servizionline.gruppohera.it/',
      'X-Bwb-PlatformId': 'web',
      'X-Bwb-Referer': 'HERA',
      'attachment': 'true',
      'DNT': '1',
    },
    redirect: 'follow'
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to download bill ${billId}: ${response.status} ${error}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

/**
 * Get bill details
 * @param {string} billId - Bill identifier
 * @returns {Promise<Object>} Bill details
 */
async function getBillDetails(billId) {
  const cookieHeader = getCookieHeader();
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  const response = await fetch(`${API_BASE}/bill/details/${billId}`, {
    headers: {
      'Cookie': cookieHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json',
      'Referer': 'https://servizionline.gruppohera.it/bill/list',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get bill details: ${response.status}`);
  }

  return await response.json();
}

/**
 * Get list of contracts for the authenticated user
 * @returns {Promise<Array>} List of contracts (electricity and gas)
 */
async function getContracts() {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Dynamically get profile ID
  const profileId = await getProfileId();

  const response = await fetch(`${API_BASE}/api/mw/v1/profile/${profileId}/contract/list`, {
    headers: {
      'Cookie': cookieHeader,
      'Authorization': authHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/json',
      'Referer': 'https://servizionline.gruppohera.it/contracts/list',
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get contracts: ${response.status} ${error}`);
  }

  const data = await response.json();
  return data.list || [];
}

/**
 * Get usage/consumption data for a specific contract
 * @param {string} contractId - Contract identifier
 * @param {Object} options - Query options
 * @param {number} options.pageNumber - Page number (default: 0)
 * @param {number} options.pageSize - Page size (default: 10)
 * @returns {Promise<Object>} Usage data with F1/F2/F3 bands
 */
async function getUsage(contractId, options = {}) {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Dynamically get profile ID
  const profileId = await getProfileId();

  const pageNumber = options.pageNumber || 0;
  const pageSize = options.pageSize || 10;

  const response = await fetch(
    `${SERVIZIONLINE_BASE}/api/profile/${profileId}/contract/${contractId}/usage?pageNumber=${pageNumber}&pageSize=${pageSize}`,
    {
      headers: {
        'Cookie': cookieHeader + '; profile=' + profileId,
        'Authorization': authHeader,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
        'Accept': 'application/json',
        'Referer': 'https://servizionline.gruppohera.it/usage/energy/',
        'X-Bwb-PlatformId': 'web',
        'X-Bwb-Referer': 'HERA',
      },
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get usage data: ${response.status} ${error}`);
  }

  const data = await response.json();
  return data;
}

/**
 * Export usage data to Excel
 * @param {string} contractId - Contract identifier
 * @param {string} type - Export type: 'ELECTRIC' or 'GAS'
 * @returns {Promise<Buffer>} Excel file as buffer
 */
async function getUsageExport(contractId, type = 'ELECTRIC') {
  const cookieHeader = getCookieHeader();
  const authHeader = getAuthHeader();
  
  if (!cookieHeader) {
    throw new Error('Not authenticated. Please login first.');
  }

  // Dynamically get profile ID
  const profileId = await getProfileId();

  const url = `${SERVIZIONLINE_BASE}/api/profile/${profileId}/read/archive/${type}/export/xls?contractId=${contractId}`;

  const response = await fetch(url, {
    headers: {
      'Cookie': cookieHeader + '; profile=' + profileId,
      'Authorization': authHeader,
      'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
      'Accept': 'application/vnd.ms-excel',
      'Referer': 'https://servizionline.gruppohera.it/usage/energy/',
      'X-Bwb-PlatformId': 'web',
      'X-Bwb-Referer': 'HERA',
      'attachment': 'true',
    },
    redirect: 'follow'
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to export usage data: ${response.status} ${error}`);
  }

  const arrayBuffer = await response.arrayBuffer();
  return Buffer.from(arrayBuffer);
}

module.exports = { getBills, downloadBill, getBillDetails, getContracts, getUsage, getUsageExport };
