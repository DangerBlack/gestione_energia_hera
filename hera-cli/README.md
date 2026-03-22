# Gruppo Hera CLI

A minimal **JavaScript** command-line tool for authenticating with Gruppo Hera's Servizi Online portal and retrieving bills, contracts, and consumption data.

## Features

- Full Azure AD B2C OAuth 2.0 authentication flow with PKCE
- Automatic session cookie and token caching
- Bill listing and PDF download
- Contract listing (electricity and gas)
- Consumption/usage data retrieval with F0/F1/F2/F3 time-of-use bands
- Excel export of usage data
- CLI tool with ASCII visualization of consumption
- Zero external dependencies (uses native fetch)

## Requirements

- Node.js 18+ (for native fetch)
- Internet connection to Gruppo Hera services

## Installation

No installation required - uses native Node.js fetch.

```bash
# Navigate to the her-cli directory
cd her-cli

# The library files are ready to use
```

## Usage

### CLI Commands

```bash
# Login with credentials
node hera-cli.js login

# List all bills
node hera-cli.js bills

# List all contracts (electricity and gas)
node hera-cli.js contracts

# Check authentication status
node hera-cli.js status

# Download a specific bill (PDF)
node hera-cli.js download <bill-id>

# Download all bills
node hera-cli.js download-all

# Get consumption data for a contract (with ASCII bar charts)
node hera-cli.js usage <contract-id> [page]

# Export usage data to Excel
node hera-cli.js usage-export <contract-id> [ELECTRIC|GAS]

# Logout (clear session)
node hera-cli.js logout
```

### Programmatic Usage

```javascript
const hera = require('./index');

async function main() {
  // Login with credentials
  await hera.login('your-email@example.com', 'your-password');

  // Get list of bills
  const bills = await hera.getBills();
  console.log(`Found ${bills.length} bills:`);
  bills.forEach(bill => {
    console.log(`  ${bill.id} - ${bill.emissionDate} - ${bill.amount}€ - ${bill.paymentStatus}`);
  });

  // Logout (clear session)
  hera.logout();
}

main().catch(console.error);
```

### Using Cached Session

```javascript
const hera = require('./index');

// Check if already authenticated
if (hera.isAuthenticated()) {
  const bills = await hera.getBills();
  console.log('Bills:', bills);
} else {
  await hera.login('email', 'password');
  const bills = await hera.getBills();
}
```

## API Reference

### `login(email, password)`
Authenticate with Gruppo Hera using Azure AD B2C OAuth flow.

**Parameters:**
- `email` (string): User's email address
- `password` (string): User's password

**Returns:** Promise<Object> - Session cookies

**Notes:** Automatically caches session for future use

### `logout()`
Clear stored authentication session.

### `getBills()`
Retrieve list of bills for the authenticated user.

**Returns:** Promise<Array> - Array of bill objects

### `downloadBill(billId)`
Download a specific bill as PDF.

**Parameters:**
- `billId` (string): Bill identifier

**Returns:** Promise<Buffer> - PDF file as Buffer

### `getContracts()`
Retrieve list of all contracts (electricity and gas).

**Returns:** Promise<Array> - Array of contract objects

### `getUsage(contractId, options)`
Retrieve consumption data for a specific contract.

**Parameters:**
- `contractId` (string): Contract identifier
- `options` (Object, optional):
  - `pageNumber` (number): Page number (default: 0)
  - `pageSize` (number): Items per page (default: 10)

**Returns:** Promise<Object> - Usage data

### `getUsageExport(contractId, type)`
Export usage data to Excel format.

**Parameters:**
- `contractId` (string): Contract identifier
- `type` (string): Export type - "ELECTRIC" or "GAS"

**Returns:** Promise<Buffer> - Excel file as Buffer

## Configuration

The library uses these default values (defined in `auth.js`):

- **Client ID:** `8627e0d8-c087-4cae-a5b4-57e975862e8f`
- **Authority:** `https://login.gruppohera.it/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web`
- **API Base (Bills/Contracts):** `https://myhera.gruppohera.it/api/mw/v1`
- **API Base (Usage):** `https://servizionline.gruppohera.it/api`

### Environment Variables

- `HERA_PROFILE_ID` - Override auto-discovered profile ID (optional)

## Authentication Flow

1. **Session Initiation:** GET authorize endpoint to obtain session cookies and TID
2. **Credential Submission:** POST to SelfAsserted endpoint with email/password
3. **Token Exchange:** GET CombinedSigninAndSignup/confirmed for redirect
4. **Code Exchange:** POST to token endpoint to obtain access token
5. **Session Establishment:** GET callback URL to establish session

All cookies and tokens are automatically cached in `.session-cookies.json`.

## Example Output

### Bills
```
$ node hera-cli.js bills
Found 13 bills:

ID                                       Date            Amount          Status
-------------------------------------------------------------------------------------
0000412606807674                         2026-03-11      207.36€         UNPAID
0000412604408426                         2026-02-11      326.25€         PAID
...
```

### Usage Data
```
$ node hera-cli.js usage 7777777777
Period: 2/1/2026 - 2/28/2026
Read Type: REAL
Total Usage: 116.84 kWh
Average Usage: 4.17 kWh/giorno

Consumption by band:
────────────────────────────────────────
F1: ██████████████████████████████ 42.12 kWh (36.0%)
F2: ██████████████████████████░░░░ 36.93 kWh (31.6%)
F3: ███████████████████████████░░░ 37.79 kWh (32.3%)
────────────────────────────────────────
```

## Files

- `index.js` - Main library exports
- `auth.js` - Azure AD B2C authentication implementation
- `api.js` - Bill API integration
- `hera-cli.js` - Command-line interface
- `.session-cookies.json` - Cached session data (created after login)

## Error Handling

All functions throw errors on failure:

```javascript
try {
  await hera.login(email, password);
  const bills = await hera.getBills();
} catch (error) {
  console.error('Operation failed:', error.message);
}
```

## Known Limitations

None! The library fully automates authentication and profile discovery.
