"""
Pytest configuration.

homeassistant stubs MUST be registered in sys.modules here, before any test
module is collected, because importing gruppo_hera (the package) executes
__init__.py which imports from homeassistant at module level.
"""
import enum
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Stub homeassistant and sub-packages
# ---------------------------------------------------------------------------

class _SensorDeviceClass(str, enum.Enum):
    ENERGY = 'energy'
    MONETARY = 'monetary'

class _SensorStateClass(str, enum.Enum):
    TOTAL_INCREASING = 'total_increasing'
    MEASUREMENT = 'measurement'

import dataclasses

@dataclasses.dataclass
class _SensorEntityDescription:
    """Minimal stand-in for HA's SensorEntityDescription."""
    key: str = ''
    name: str = ''
    native_unit_of_measurement: str = None
    device_class: object = None
    state_class: object = None
    icon: str = None

_sensor_mod = MagicMock()
_sensor_mod.SensorDeviceClass = _SensorDeviceClass
_sensor_mod.SensorStateClass = _SensorStateClass
_sensor_mod.SensorEntityDescription = _SensorEntityDescription
class _SensorEntity:
    pass

_sensor_mod.SensorEntity = _SensorEntity


class _CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

_coordinator_mod = MagicMock()
_coordinator_mod.CoordinatorEntity = _CoordinatorEntity

sys.modules.update({
    'homeassistant':                              MagicMock(),
    'homeassistant.components':                   MagicMock(),
    'homeassistant.components.sensor':            _sensor_mod,
    'homeassistant.config_entries':               MagicMock(),
    'homeassistant.core':                         MagicMock(),
    'homeassistant.exceptions':                   MagicMock(),
    'homeassistant.helpers':                      MagicMock(),
    'homeassistant.helpers.aiohttp_client':       MagicMock(),
    'homeassistant.helpers.entity':               MagicMock(),
    'homeassistant.helpers.update_coordinator':   _coordinator_mod,
})

# ---------------------------------------------------------------------------
# 2. Make custom_components/ importable as a top-level namespace so that
#    relative imports inside the integration (from .auth import …) resolve.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / 'custom_components'))
