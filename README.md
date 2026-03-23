# Gruppo Hera Services

This repository contains two separate implementations for interacting with Gruppo Hera Servizi Online:

## 📦 Projects

### 1. **hera-cli** - JavaScript CLI Tool
A minimal command-line tool for authenticating and retrieving bills, contracts, and consumption data.

**Features:**
- Zero dependencies (native Node.js fetch)
- CLI with ASCII visualization
- Programmatic API for scripting
- Session caching

**See:** [hera-cli/README.md](hera-cli/README.md) for documentation

**Quick Start:**
```bash
cd hera-cli
node hera-cli.js login
node hera-cli.js bills
node hera-cli.js usage <contract-id>
```

---

### 2. **custom_components/gruppo_hera** - Home Assistant Integration
A pure Python Home Assistant integration with daily updates.

**Features:**
- Pure Python (no external service needed)
- Daily data updates (24-hour interval)
- Home Assistant ConfigFlow UI
- Sensors for consumption data
- HACS compatible
- Full authentication before each update

**See:** [custom_components/gruppo_hera/](custom_components/gruppo_hera/) for the integration

**Quick Start:**
1. Copy `custom_components/gruppo_hera` to your Home Assistant `config/custom_components/`
2. Restart Home Assistant
3. Add integration via Settings → Devices & Services
4. Enter your Gruppo Hera credentials

---

## 🔐 Authentication

Both implementations use the same Azure AD B2C OAuth 2.0 flow:

1. Session initiation with CSRF tokens
2. Credential submission to SelfAsserted endpoint
3. Token exchange via authorization code
4. Session establishment with caching

## 📊 Data Available

Both implementations can retrieve:
- **Bills** - List and download PDF bills
- **Contracts** - Electricity and gas contract details
- **Usage/Consumption** - Monthly consumption with F1/F2/F3 time-of-use bands
- **Exports** - Excel export of usage data

## 🛠️ Technical Details

### Authentication Endpoints
- **Authority:** `https://login.gruppohera.it/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web`
- **Client ID:** `40c94bb1-2d83-4ccc-8c72-fde8ad15ed24`

### API Endpoints
- **Bills/Contracts:** `https://myhera.gruppohera.it/api/mw/v1`
- **Usage:** `https://servizionline.gruppohera.it/api`

## 📁 Repository Structure

```
.
├── hera-cli/                    # JavaScript CLI tool
│   ├── auth.js                 # Authentication implementation
│   ├── api.js                  # API integration
│   ├── hera-cli.js             # CLI interface
│   ├── index.js                # Library exports
│   └── README.md               # CLI documentation
│
├── custom_components/           # Home Assistant integration
│   └── gruppo_hera/
│       ├── __init__.py         # Integration setup
│       ├── auth.py             # Python auth (ported from auth.js)
│       ├── api.py              # Python API (ported from api.js)
│       ├── config_flow.py      # HA ConfigFlow
│       ├── sensor.py           # Sensor entities
│       ├── const.py            # Constants
│       └── manifest.json       # Integration metadata
│
├── .gitignore                  # Git ignore rules
├── hacs.json                   # HACS configuration
└── README.md                   # This file
```

## ⚠️ Disclaimer

These are unofficial tools for Gruppo Hera Servizi Online. Not affiliated with or endorsed by Gruppo Hera. Use at your own risk.

## 📝 Notes

- Session cookies are cached in `.session-cookies.json`
- Credentials should be stored securely (use secrets in Home Assistant)
- Integration performs full authentication every 24 hours
- Both implementations share the same authentication logic (Python version ported from JavaScript)
- Data updates once daily (appropriate for bills/contracts that change monthly)
