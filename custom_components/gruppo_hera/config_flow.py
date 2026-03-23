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
                _LOGGER.debug("Attempting login for: %s", self.email)
                cookies = await login(self.email, self.password)
                
                # Check if we got a valid session
                _LOGGER.debug("Login returned cookies: %s", list(cookies.keys()) if cookies else None)
                
                if cookies and (cookies.get('profile') or any(
                    k.startswith('x-ms-cpim-sso') for k in cookies.keys()
                )):
                    _LOGGER.info("Authentication successful for: %s", self.email)
                    
                    # Clear the test cookies - they will be re-created during actual use
                    from .auth import clear_cookies
                    clear_cookies()
                    
                    # Store credentials directly (not as secret references)
                    # Home Assistant will encrypt them in the config entry
                    return self.async_create_entry(
                        title="Gruppo Hera",
                        data={
                            CONF_EMAIL: self.email,
                            CONF_PASSWORD: self.password,
                        },
                    )
                else:
                    _LOGGER.error("Authentication failed: no session cookies received")
                    errors["base"] = "invalid_auth"
                    
            except Exception as err:
                _LOGGER.error("Auth error: %s - %s", type(err).__name__, str(err))
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_AUTH_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return GruppoHeraOptionsFlowHandler(config_entry)


class GruppoHeraOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._config_entry = config_entry

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
                        default=self._config_entry.options.get("scan_interval", 86400),
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
