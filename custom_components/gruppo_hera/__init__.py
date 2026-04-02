"""Gruppo Hera integration setup."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    STARTUP_DELAY_MAX,
)
from .auth import login, logout, load_cookies, configure_storage, _authenticate_sync, save_cookies
from .api import get_contracts, get_bills, get_usage

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Gruppo Hera component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gruppo Hera from a config entry."""

    # Point cookie storage at the HA config directory (safe across updates)
    configure_storage(hass.config.config_dir)

    # Create coordinator
    coordinator = GruppoHeraDataUpdateCoordinator(hass, entry)
    
    # Add random delay on first refresh to spread API load across time
    # This prevents all customers from hitting the API simultaneously after Watchtower updates
    startup_delay = random.randint(0, STARTUP_DELAY_MAX)
    if startup_delay > 0:
        _LOGGER.info(f"Waiting {startup_delay}s before first update (to spread API load)")
        await asyncio.sleep(startup_delay)
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when options change so the new scan_interval takes effect
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # Clear cached cookies on removal
    await logout()


class GruppoHeraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Gruppo Hera API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize."""
        self.config_entry = config_entry
        self.email = config_entry.data.get(CONF_EMAIL, "")
        self.password = config_entry.data.get(CONF_PASSWORD, "")
        
        scan_interval = config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Gruppo Hera API."""
        try:
            # Always perform fresh login (session expires after ~1 hour)
            _LOGGER.info("Performing authentication...")
            
            # Login (blocking HTTP requests in _authenticate_sync) - run in executor
            cookies = await self.hass.async_add_executor_job(
                _do_login, self.email, self.password
            )
            _LOGGER.info("Authentication successful")
            
            # Fetch all data using async aiohttp calls directly
            # Fetch contracts and bills in parallel
            contracts_task = get_contracts()
            bills_task = get_bills()
            contracts, bills = await asyncio.gather(contracts_task, bills_task)
            
            # Fetch usage for each contract
            usage_data = {}
            for contract in contracts:
                contract_id = contract.get("id")
                if contract_id:
                    try:
                        usage = await get_usage(contract_id, page_number=0, page_size=10)
                        usage_data[contract_id] = usage
                    except Exception as err:
                        _LOGGER.warning(f"Failed to fetch usage for {contract_id}: {err}")
            
            return {
                "contracts": contracts,
                "bills": bills,
                "usage": usage_data,
                "last_update": datetime.now(),
            }
            
        except Exception as err:
            if "Not authenticated" in str(err) or "authentication" in str(err).lower():
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}")
            raise UpdateFailed(f"Data fetch error: {err}")


def _do_login(email: str, password: str) -> dict:
    """Synchronous login wrapper - runs in executor thread."""
    cookies = _authenticate_sync(email, password)
    save_cookies(cookies)
    return cookies
