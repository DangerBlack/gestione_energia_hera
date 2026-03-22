# Gruppo Hera - Home Assistant Integration

A **pure Python** Home Assistant integration for Gruppo Hera Servizi Online that retrieves bills, contracts, and consumption data with **auto-re-authentication**.

## Features

- ✅ **Pure Python** - No external service or Node.js required
- ✅ **Auto-re-authentication** - Automatically refreshes expired sessions
- ✅ **Azure AD B2C OAuth 2.0** - Full authentication flow with PKCE
- ✅ **Automatic session caching** - Cookies and tokens cached locally
- ✅ **Bills** - List and download PDF bills
- ✅ **Contracts** - View electricity and gas contracts
- ✅ **Consumption data** - Get usage with F1/F2/F3 time-of-use bands
- ✅ **HACS compatible** - Easy installation via Home Assistant Community Store
- ✅ **Single dependency** - Only requires `aiohttp` (built into Home Assistant)

## Installation

### Option 1: HACS (Recommended)

1. **Add this repository to HACS:**
   - Open HACS in Home Assistant
   - Click "Integrations"
   - Click the three dots (⋮) in the top right
   - Select "Custom repositories"
   - Add this repository URL
   - Select "Integration" as category
   - Click "Add"

2. **Install the integration:**
   - Search for "Gruppo Hera" in HACS
   - Click on it and press "Download"

3. **Restart Home Assistant:**
   - Settings → System → Restart

4. **Configure the integration:**
   - Settings → Devices & Services → Add Integration
   - Search for "Gruppo Hera"
   - Enter your Gruppo Hera email and password

### Option 2: Manual Installation

1. **Copy the integration folder:**
   ```bash
   # From the repository root
   cp -r custom_components/gruppo_hera /path/to/homeassistant/config/custom_components/
   ```

2. **Restart Home Assistant:**
   - Settings → System → Restart

3. **Configure the integration:**
   - Settings → Devices & Services → Add Integration
   - Search for "Gruppo Hera"
   - Enter your Gruppo Hera email and password

## Configuration

### Using ConfigFlow (UI)

1. Click "Add Integration" in Home Assistant
2. Search for "Gruppo Hera"
3. Enter your Gruppo Hera credentials (email and password)
4. The integration will test authentication and create the config entry

**Note:** Credentials are stored securely in Home Assistant's configuration.

### Using secrets.yaml (Optional)

For better security, you can store credentials in `secrets.yaml`:

```yaml
# configuration.yaml
gruppo_hera:
  email: !secret gruppo_hera_email
  password: !secret gruppo_hera_password
```

```yaml
# secrets.yaml
gruppo_hera_email: your-email@example.com
gruppo_hera_password: your-password
```

## Usage

Once configured, the integration will:

- Automatically authenticate with Gruppo Hera on startup
- Fetch contracts, bills, and consumption data
- Create sensors for each contract's consumption
- Auto-re-authenticate when sessions expire (every 6 hours by default)

### Sensors Created

For each electricity/gas contract, the integration creates:

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.gruppo_hera_{type}_total_consumption` | Total kWh consumption | kWh |
| `sensor.gruppo_hera_{type}_consumption_f1` | Band F1 consumption (peak) | kWh |
| `sensor.gruppo_hera_{type}_consumption_f2` | Band F2 consumption (semi-peak) | kWh |
| `sensor.gruppo_hera_{type}_consumption_f3` | Band F3 consumption (off-peak) | kWh |
| `sensor.gruppo_hera_{type}_average_daily` | Average daily consumption | kWh/day |

Plus a global bill sensor:
| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.gruppo_hera_last_bill_amount` | Most recent bill amount | € |

Where `{type}` is replaced with the contract type (e.g., `electric`, `gas`).

### Example: Display Consumption in Dashboard

```yaml
# configuration.yaml
lovelace:
  resources:
    - url: /hacsfiles/mini-graph-card/mini-graph-card-bundle.js
      type: module

card_mod:
  configuration:
    card:
      type: custom:mini-graph-card
      entities:
        - entity: sensor.gruppo_hera_electric_total_consumption
      name: Electric Consumption
      hour24: true
      points_per_hour: 1
```

## Auto-Re-authentication

The integration automatically re-authenticates when:
- Session expires (typically after ~1 hour)
- Token is invalid
- API returns 401 Unauthorized

**No manual intervention required!** The integration handles it automatically.

### Re-authentication Interval

The default update interval is 6 hours (21600 seconds). You can customize this in the integration options:

1. Settings → Devices & Services
2. Click on Gruppo Hera integration
3. Click "Configure" or "Options"
4. Adjust the scan interval

## Troubleshooting

### Authentication Failed

**Symptoms:** Integration shows "Configuration failed" or sensors unavailable

**Solutions:**
1. Check your email and password are correct
2. Try logging in at https://servizionline.gruppohera.it to verify credentials
3. Check Home Assistant logs: Settings → System → Logs
4. Look for "gruppo_hera" in the logs for detailed error messages

### Sensors Not Updating

**Symptoms:** Sensors show old data or "unavailable"

**Solutions:**
1. Check Home Assistant logs for API errors
2. Verify internet connectivity from Home Assistant
3. Try removing and re-adding the integration
4. Check if Gruppo Hera services are accessible

### Session Expired Errors

**Symptoms:** Logs show "Session expired" or "Authentication failed"

**Solutions:**
1. The integration should auto-re-authenticate - check logs
2. If re-auth fails, remove and re-add the integration
3. Verify credentials haven't changed
4. Check for any 2FA requirements on your Gruppo Hera account

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.gruppo_hera: debug
```

Then restart Home Assistant and check logs for detailed information.

## Development

### Testing Locally

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install aiohttp homeassistant

# Test authentication
python3 -c "
import asyncio
from custom_components.gruppo_hera.auth import login
asyncio.run(login('your-email', 'your-password'))
"

# Test API calls
python3 -c "
import asyncio
from custom_components.gruppo_hera.api import get_contracts, get_bills
asyncio.run(get_contracts())
asyncio.run(get_bills())
"
```

### Directory Structure

```
gruppo_hera/
├── __init__.py          # Integration setup + data coordinator
├── auth.py              # Azure AD B2C authentication (pure Python)
├── api.py               # API endpoints (bills, contracts, usage)
├── config_flow.py       # Home Assistant ConfigFlow UI
├── sensor.py            # Sensor entities
├── const.py             # Constants and configuration keys
├── manifest.json        # Integration metadata
└── translations/
    └── en.json          # UI strings
```

### Key Components

- **auth.py**: Handles Azure AD B2C OAuth flow with PKCE
- **api.py**: API calls to Gruppo Hera endpoints
- **__init__.py**: Integration setup, coordinator, auto-reauth logic
- **config_flow.py**: UI configuration flow
- **sensor.py**: Creates consumption sensors

## API Endpoints

The integration uses these Gruppo Hera APIs:

- **Authentication:** `https://login.gruppohera.it`
- **Bills/Contracts:** `https://myhera.gruppohera.it/api/mw/v1`
- **Usage:** `https://servizionline.gruppohera.it/api`

## Requirements

- Home Assistant 2021.6+ (for ConfigFlow support)
- Python 3.8+ (built into Home Assistant)
- Internet connection to Gruppo Hera services
- Valid Gruppo Hera Servizi Online account

## Security Notes

- Credentials are stored in Home Assistant's encrypted configuration
- Session cookies are cached locally (not sent to external services)
- All communication is over HTTPS
- No data is sent to third parties

## Limitations

- Bills are read-only (cannot pay bills through this integration)
- Usage data may have a delay (depends on Gruppo Hera data updates)
- Only supports email/password authentication (no 2FA support yet)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - See LICENSE file for details

## Disclaimer

This is an **unofficial** integration for Gruppo Hera Servizi Online. Not affiliated with, endorsed by, or sponsored by Gruppo Hera S.p.A. Use at your own risk.

The authors are not responsible for any data loss, account issues, or other problems that may arise from using this integration. Use responsibly and at your own discretion.

## Support

For issues, questions, or feature requests:
- Open an issue on GitHub
- Check existing issues for solutions
- Provide detailed logs when reporting bugs
