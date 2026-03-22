"""Config flow for Gruppo Hera integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .auth import login

_LOGGER = logging.getLogger(__name__)

STEP_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class GruppoHeraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gruppo Hera."""

    VERSION = 1

    def __init__(self):
        self.email = None
        self.password = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]

            # Test authentication
            try:
                # Try to login with provided credentials
                await login(self.email, self.password)
                
                # Check if we got a valid session
                from .auth import load_cookies
                cookies = load_cookies()
                
                if cookies and (cookies.get('profile') or any(
                    k.startswith('x-ms-cpim-sso') for k in cookies.keys()
                )):
                    _LOGGER.info("Authentication successful")
                    
                    # Clear the test cookies
                    from .auth import clear_cookies
                    
                    # Create config entry with secret references
                    return self.async_create_entry(
                        title="Gruppo Hera",
                        data={
                            CONF_EMAIL: f"!secret {DOMAIN}_email",
                            CONF_PASSWORD: f"!secret {DOMAIN}_password",
                        },
                    )
                else:
                    errors["base"] = "invalid_auth"
                    
            except Exception as err:
                _LOGGER.error("Auth error: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_AUTH_SCHEMA,
            errors=errors,
        )

    @staticmethod
    async def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return GruppoHeraOptionsFlowHandler(config_entry)


class GruppoHeraOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", 21600),
                    ): vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
                }
            ),
        )


class AuthenticationError(HomeAssistantError):
    """Error during authentication."""
    pass


class CannotConnectError(HomeAssistantError):
    """Error when unable to connect to API."""
    pass
