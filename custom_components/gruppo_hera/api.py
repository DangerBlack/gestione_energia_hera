"""
Gruppo Hera API Module
Ported from Node.js api.js - Pure Python, no external dependencies
"""
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import aiohttp
except ImportError:
    raise ImportError("aiohttp is required: pip install aiohttp")

from .auth import get_cookie_header, load_cookies

# API Base URLs (matching Node.js api.js)
API_BASE = 'https://myhera.gruppohera.it'
SERVIZIONLINE_BASE = 'https://servizionline.gruppohera.it'


async def get_profile_id() -> str:
    """Get the authenticated user's profile ID."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    # Try environment variable first
    import os
    env_profile_id = os.getenv('HERA_PROFILE_ID')
    if env_profile_id:
        return env_profile_id
    
    # Extract from cookie if available
    import re
    profile_match = re.search(r'profile=([^;]+)', cookie_header)
    if profile_match:
        return profile_match.group(1).strip()
    
    # Fetch from API as fallback
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/api/mw/v1/profile/list",
            headers={
                'Cookie': cookie_header,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/json',
            }
        ) as resp:
            if not resp.ok:
                raise Exception(f"Failed to get profile list: {resp.status}")
            
            data = await resp.json()
            
            if not data.get('list') or len(data['list']) == 0:
                raise Exception("No profiles found for this user")
            
            # Return default or first profile
            default_profile = next((p for p in data['list'] if p.get('isDefault')), None)
            return (default_profile or data['list'][0])['id']


async def get_bills() -> List[Dict]:
    """Get list of bills for the authenticated user."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    profile_id = await get_profile_id()
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/api/mw/v1/profile/{profile_id}/bill/list",
            headers={
                'Cookie': cookie_header,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/json',
                'Referer': 'https://servizionline.gruppohera.it/bill/list',
            }
        ) as resp:
            if not resp.ok:
                error_text = await resp.text()
                raise Exception(f"Failed to get bills: {resp.status} {error_text}")
            
            data = await resp.json()
            return data.get('list', [])


async def download_bill(bill_id: str) -> bytes:
    """Download a specific bill as PDF."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    profile_id = await get_profile_id()
    url = f"{SERVIZIONLINE_BASE}/profile/{profile_id}/bill/export/pdf/{bill_id}"
    
    full_cookie = f"{cookie_header}; profile={profile_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={
                'Cookie': full_cookie,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/pdf',
                'Referer': 'https://servizionline.gruppohera.it/',
                'X-Bwb-PlatformId': 'web',
                'X-Bwb-Referer': 'HERA',
                'attachment': 'true',
            },
            allow_redirects=True
        ) as resp:
            if not resp.ok:
                error_text = await resp.text()
                raise Exception(f"Failed to download bill {bill_id}: {resp.status} {error_text}")
            
            return await resp.read()


async def get_contracts() -> List[Dict]:
    """Get list of contracts (electricity and gas)."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    profile_id = await get_profile_id()
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/api/mw/v1/profile/{profile_id}/contract/list",
            headers={
                'Cookie': cookie_header,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/json',
                'Referer': 'https://servizionline.gruppohera.it/contracts/list',
            }
        ) as resp:
            if not resp.ok:
                error_text = await resp.text()
                raise Exception(f"Failed to get contracts: {resp.status} {error_text}")
            
            data = await resp.json()
            return data.get('list', [])


async def get_usage(contract_id: str, page_number: int = 0, page_size: int = 10) -> Dict:
    """Get usage/consumption data for a specific contract."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    profile_id = await get_profile_id()
    url = f"{SERVIZIONLINE_BASE}/profile/{profile_id}/contract/{contract_id}/usage?pageNumber={page_number}&pageSize={page_size}"
    
    full_cookie = f"{cookie_header}; profile={profile_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={
                'Cookie': full_cookie,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/json',
                'Referer': 'https://servizionline.gruppohera.it/usage/energy/',
                'X-Bwb-PlatformId': 'web',
                'X-Bwb-Referer': 'HERA',
            }
        ) as resp:
            if not resp.ok:
                error_text = await resp.text()
                raise Exception(f"Failed to get usage data: {resp.status} {error_text}")
            
            return await resp.json()


async def get_usage_export(contract_id: str, usage_type: str = 'ELECTRIC') -> bytes:
    """Export usage data to Excel."""
    cookie_header = get_cookie_header()
    cookies = load_cookies()
    auth_header = f"Bearer {cookies['accessToken']}" if cookies and cookies.get('accessToken') else None
    
    if not cookie_header:
        raise Exception("Not authenticated. Please login first.")
    
    profile_id = await get_profile_id()
    url = f"{SERVIZIONLINE_BASE}/profile/{profile_id}/read/archive/{usage_type}/export/xls?contractId={contract_id}"
    
    full_cookie = f"{cookie_header}; profile={profile_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url,
            headers={
                'Cookie': full_cookie,
                'Authorization': auth_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'application/vnd.ms-excel',
                'Referer': 'https://servizionline.gruppohera.it/usage/energy/',
                'X-Bwb-PlatformId': 'web',
                'X-Bwb-Referer': 'HERA',
                'attachment': 'true',
            },
            allow_redirects=True
        ) as resp:
            if not resp.ok:
                error_text = await resp.text()
                raise Exception(f"Failed to export usage data: {resp.status} {error_text}")
            
            return await resp.read()
