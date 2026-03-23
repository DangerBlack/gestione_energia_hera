"""Gruppo Hera integration setup."""
from __future__ import annotations

import logging
from datetime import timedelta
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
from .auth import login, logout, load_cookies
from .api import get_contracts, get_bills, get_usage

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Gruppo Hera component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gruppo Hera from a config entry."""
    
    # Create coordinator
    coordinator = GruppoHeraDataUpdateCoordinator(hass, entry)
    
    # Add random delay on first refresh to spread API load across time
    # This prevents all customers from hitting the API simultaneously after Watchtower updates
    import random
    startup_delay = random.randint(0, STARTUP_DELAY_MAX)
    if startup_delay > 0:
        _LOGGER.info(f"Waiting {startup_delay}s before first update (to spread API load)")
        await asyncio.sleep(startup_delay)
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove a config entry."""
    # Clear cached cookies on removal
    await logout()
    return True


class GruppoHeraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from Gruppo Hera API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize."""
        self.config_entry = config_entry
        self.email = config_entry.data.get(CONF_EMAIL, "")
        self.password = config_entry.data.get(CONF_PASSWORD, "")
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Gruppo Hera API."""
        try:
            # Always perform fresh login (session expires after ~1 hour)
            # This is more reliable than trying to reuse expired sessions
            _LOGGER.info("Performing authentication...")
            await login(self.email, self.password)
            _LOGGER.info("Authentication successful")
            
            # Fetch all data in parallel using executor for sync calls
            contracts, bills = await self.hass.async_add_executor_job(
                self._fetch_contracts_and_bills_sync
            )
            
            # Fetch usage for each contract
            usage_data = {}
            for contract in contracts:
                contract_id = contract.get("id")
                if contract_id:
                    try:
                        usage = await self.hass.async_add_executor_job(
                            self._fetch_usage_sync, contract_id
                        )
                        usage_data[contract_id] = usage
                    except Exception as err:
                        _LOGGER.warning(f"Failed to fetch usage for {contract_id}: {err}")
            
            return {
                "contracts": contracts,
                "bills": bills,
                "usage": usage_data,
                "last_update": self.hass.data.get("now"),
            }
            
        except Exception as err:
            if "Not authenticated" in str(err) or "authentication" in str(err).lower():
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}")
            raise UpdateFailed(f"Data fetch error: {err}")

    def _fetch_contracts_and_bills_sync(self):
        """Fetch contracts and bills using the sync API wrapper."""
        # Import here to avoid circular imports
        from .api import get_contracts, get_bills
        
        # These are async functions, so we need to run them
        # Since we're in an executor, we can't use async/await directly
        # Instead, we use the sync wrappers or run in a new loop
        import asyncio
        
        async def fetch():
            contracts = await get_contracts()
            bills = await get_bills()
            return contracts, bills
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(fetch())
        finally:
            loop.close()

    def _fetch_usage_sync(self, contract_id: str):
        """Fetch usage for a specific contract."""
        from .api import get_usage
        
        import asyncio
        
        async def fetch():
            return await get_usage(contract_id, page_number=0, page_size=10)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(fetch())
        finally:
            loop.close()

    async def _async_ensure_authenticated(self):
        """Deprecated: Always perform fresh login instead."""
        # This method is no longer used - we always do full login
        # Session expires after ~1 hour, so reusing cached sessions is unreliable
        pass
