"""Sensor platform for Gruppo Hera integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


@dataclass
class GruppoHeraSensorDescription(SensorEntityDescription):
    """Describes Gruppo Hera sensor."""
    contract_id: str | None = None
    band: str | None = None


SENSOR_DESCRIPTIONS = [
    GruppoHeraSensorDescription(
        key="total_consumption",
        name="Total Consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
    ),
    GruppoHeraSensorDescription(
        key="consumption_f1",
        name="Consumption F1",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
        band="F1",
    ),
    GruppoHeraSensorDescription(
        key="consumption_f2",
        name="Consumption F2",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
        band="F2",
    ),
    GruppoHeraSensorDescription(
        key="consumption_f3",
        name="Consumption F3",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class="total_increasing",
        band="F3",
    ),
    GruppoHeraSensorDescription(
        key="average_daily",
        name="Average Daily Consumption",
        native_unit_of_measurement="kWh/day",
        device_class=SensorDeviceClass.ENERGY,
    ),
    GruppoHeraSensorDescription(
        key="last_bill_amount",
        name="Last Bill Amount",
        native_unit_of_measurement="€",
        device_class=SensorDeviceClass.MONETARY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up sensors based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get contracts from coordinator data
    contracts = coordinator.data.get("contracts", [])
    
    sensors = []
    
    # Create sensors for each contract
    for contract in contracts:
        contract_id = contract.get("id")
        service_type = contract.get("serviceType", "UNKNOWN")
        address = contract.get("supplyAddress", "Unknown")
        
        # Skip if no usage data available
        usage_data = coordinator.data.get("usage", {}).get(contract_id, {})
        if not usage_data:
            continue
        
        # Get latest usage record
        usage_list = usage_data.get("data", {}).get("list", [])
        if not usage_list:
            continue
        
        latest_usage = usage_list[0]
        
        # Create total consumption sensor
        sensors.append(
            GruppoHeraSensor(
                coordinator,
                SENSOR_DESCRIPTIONS[0],
                contract_id,
                service_type,
                address,
                latest_usage.get("totalUsage", 0),
            )
        )
        
        # Create band sensors (F1, F2, F3)
        reads = latest_usage.get("reads", [])
        reads_by_band = {r.get("type"): r for r in reads}
        
        for band in ["F1", "F2", "F3"]:
            if band in reads_by_band:
                sensors.append(
                    GruppoHeraSensor(
                        coordinator,
                        SENSOR_DESCRIPTIONS[1],  # Will be customized below
                        contract_id,
                        service_type,
                        address,
                        reads_by_band[band].get("value", 0),
                        band,
                    )
                )
        
        # Create average daily sensor
        sensors.append(
            GruppoHeraSensor(
                coordinator,
                SENSOR_DESCRIPTIONS[4],
                contract_id,
                service_type,
                address,
                latest_usage.get("averageUsage", 0),
            )
        )
    
    # Add last bill sensor (only once)
    bills = coordinator.data.get("bills", [])
    if bills:
        latest_bill = bills[0]
        sensors.append(
            GruppoHeraSensor(
                coordinator,
                SENSOR_DESCRIPTIONS[5],
                None,
                "BILLS",
                "All Bills",
                latest_bill.get("amount", 0),
            )
        )
    
    async_add_entities(sensors, update_before_add=True)


class GruppoHeraSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Gruppo Hera sensor."""

    def __init__(
        self,
        coordinator,
        description: GruppoHeraSensorDescription,
        contract_id: str | None,
        service_type: str,
        address: str,
        native_value: float,
        band: str | None = None,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self.entity_description = description
        self.contract_id = contract_id
        self.service_type = service_type
        self.address = address
        self.band = band
        
        # Customize entity name based on contract
        if contract_id:
            self._attr_name = f"{service_type} {description.name}"
            self._attr_unique_id = f"{contract_id}_{description.key}"
        else:
            self._attr_name = description.name
            self._attr_unique_id = f"bills_{description.key}"
        
        self._attr_native_value = native_value
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, contract_id or "bills")},
            name=f"Gruppo Hera {service_type}" if contract_id else "Gruppo Hera Bills",
            manufacturer=MANUFACTURER,
            model=service_type,
            suggested_area=address[:30] if address else None,
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        # Get latest usage data
        if self.contract_id:
            usage_data = self.coordinator.data.get("usage", {}).get(self.contract_id, {})
            usage_list = usage_data.get("data", {}).get("list", [])
            
            if usage_list:
                latest_usage = usage_list[0]
                
                if self.band:
                    # Return specific band value
                    reads = latest_usage.get("reads", [])
                    reads_by_band = {r.get("type"): r for r in reads}
                    return reads_by_band.get(self.band, {}).get("value", 0)
                elif self.entity_description.key == "total_consumption":
                    return latest_usage.get("totalUsage", 0)
                elif self.entity_description.key == "average_daily":
                    return latest_usage.get("averageUsage", 0)
        
        # For bill sensor
        if self.entity_description.key == "last_bill_amount":
            bills = self.coordinator.data.get("bills", [])
            if bills:
                return bills[0].get("amount", 0)
        
        return self._attr_native_value

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success
