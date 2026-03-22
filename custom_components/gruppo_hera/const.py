"""Constants for Gestione Energia Hera integration."""

DOMAIN = "gruppo_hera"
MANUFACTURER = "DangerBlack"
INTEGRATION_NAME = "Gestione Energia Hera"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_CONTRACT_IDS = "contract_ids"

# Default values
DEFAULT_SCAN_INTERVAL = 21600  # 6 hours in seconds

# Sensor types
SENSOR_TYPES = {
    "consumption_total": {
        "name": "Total Consumption",
        "unit": "kWh",
        "device_class": "energy",
    },
    "consumption_f1": {
        "name": "Consumption F1",
        "unit": "kWh",
        "device_class": "energy",
    },
    "consumption_f2": {
        "name": "Consumption F2",
        "unit": "kWh",
        "device_class": "energy",
    },
    "consumption_f3": {
        "name": "Consumption F3",
        "unit": "kWh",
        "device_class": "energy",
    },
    "average_daily": {
        "name": "Average Daily Consumption",
        "unit": "kWh/day",
        "device_class": "energy",
    },
    "last_bill_amount": {
        "name": "Last Bill Amount",
        "unit": "€",
        "device_class": "monetary",
    },
}
