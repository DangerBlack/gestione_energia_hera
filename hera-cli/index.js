const { login, logout, loadCookies } = require('./auth');
const { getBills, downloadBill, getBillDetails, getContracts, getUsage, getUsageExport } = require('./api');

/**
 * Gruppo Hera Servizi Online API Client
 *
 * Minimal library for authenticating and retrieving bills
 * from Gruppo Hera's portal using cookie-based session
 */

module.exports = {
  // Authentication
  login,
  logout,

  // Bill operations
  getBills,
  downloadBill,
  getBillDetails,

  // Contract and usage operations
  getContracts,
  getUsage,
  getUsageExport,

  // Helper to check if user is authenticated
  isAuthenticated: () => {
    const cookies = loadCookies();
    return !!(cookies && (cookies.profile || cookies.accessToken || Object.keys(cookies).some(k => k.startsWith('x-ms-cpim-sso'))));
  },
};
