"""Unit tests for api.py — all mocked, no real credentials needed."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import gruppo_hera.auth as auth
import gruppo_hera.api as api


def _make_mock_session(json_data: dict = None, status: int = 200, ok: bool = True):
    """Return an aiohttp.ClientSession mock that yields a single JSON response."""
    mock_resp = AsyncMock()
    mock_resp.ok = ok
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data or {})
    mock_resp.text = AsyncMock(return_value=json.dumps(json_data or {}))

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_cm)

    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_session_cm


@pytest.fixture(autouse=True)
def authenticated():
    """Provide a valid in-memory session for every test."""
    auth._cached_cookies = {'profile': 'profile_abc', 'accessToken': 'token_xyz', 'session': 's'}
    auth._access_token = 'token_xyz'
    yield
    auth._cached_cookies = None
    auth._access_token = None


# ---------------------------------------------------------------------------
# get_profile_id
# ---------------------------------------------------------------------------

async def test_get_profile_id_extracted_from_cookie():
    """Profile ID is read from the cached cookie — no HTTP call."""
    with patch('aiohttp.ClientSession', side_effect=AssertionError("should not make HTTP call")):
        result = await api.get_profile_id()
    assert result == 'profile_abc'


async def test_get_profile_id_raises_when_not_authenticated():
    auth._cached_cookies = None
    auth._access_token = None
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(Exception, match="Not authenticated"):
            await api.get_profile_id()


async def test_get_profile_id_falls_back_to_api():
    """When profile cookie is absent, the API is called."""
    auth._cached_cookies = {'accessToken': 'tok', 'session': 's'}  # no 'profile' key
    auth._access_token = 'tok'

    mock_data = {'list': [{'id': 'api_profile', 'isDefault': True}]}
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(mock_data)):
        result = await api.get_profile_id()
    assert result == 'api_profile'


# ---------------------------------------------------------------------------
# get_bills
# ---------------------------------------------------------------------------

async def test_get_bills_returns_list():
    payload = {'list': [
        {'id': 'b1', 'amount': 80.50},
        {'id': 'b2', 'amount': 120.00},
    ]}
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(payload)):
        result = await api.get_bills()

    assert len(result) == 2
    assert result[0]['id'] == 'b1'
    assert result[1]['amount'] == 120.00


async def test_get_bills_returns_empty_list_when_none():
    with patch('aiohttp.ClientSession', return_value=_make_mock_session({'list': []})):
        result = await api.get_bills()
    assert result == []


async def test_get_bills_raises_on_http_error():
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(status=401, ok=False)):
        with pytest.raises(Exception, match="Failed to get bills"):
            await api.get_bills()


async def test_get_bills_raises_when_not_authenticated():
    auth._cached_cookies = None
    auth._access_token = None
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(Exception, match="Not authenticated"):
            await api.get_bills()


# ---------------------------------------------------------------------------
# get_contracts
# ---------------------------------------------------------------------------

async def test_get_contracts_returns_list():
    payload = {'list': [
        {'id': 'c1', 'serviceType': 'ELECTRIC', 'supplyAddress': 'Via Roma 1'},
        {'id': 'c2', 'serviceType': 'GAS', 'supplyAddress': 'Via Roma 1'},
    ]}
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(payload)):
        result = await api.get_contracts()

    assert len(result) == 2
    assert result[0]['serviceType'] == 'ELECTRIC'
    assert result[1]['serviceType'] == 'GAS'


async def test_get_contracts_raises_on_http_error():
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(status=500, ok=False)):
        with pytest.raises(Exception, match="Failed to get contracts"):
            await api.get_contracts()


# ---------------------------------------------------------------------------
# get_usage
# ---------------------------------------------------------------------------

async def test_get_usage_returns_data():
    payload = {
        'list': [{
            'totalUsage': 250.5,
            'averageUsage': 8.35,
            'reads': [
                {'type': 'F1', 'value': 150.0},
                {'type': 'F2', 'value': 100.5},
            ]
        }]
    }
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(payload)):
        result = await api.get_usage('contract_1')

    assert result['list'][0]['totalUsage'] == 250.5
    assert result['list'][0]['reads'][0]['type'] == 'F1'


async def test_get_usage_raises_on_http_error():
    with patch('aiohttp.ClientSession', return_value=_make_mock_session(status=403, ok=False)):
        with pytest.raises(Exception, match="Failed to get usage"):
            await api.get_usage('contract_1')
