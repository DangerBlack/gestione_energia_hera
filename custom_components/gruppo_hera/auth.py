"""
Gruppo Hera Authentication Module
Ported from Node.js auth.js - Pure Python, no external dependencies
"""
import asyncio
import base64
import hashlib
import json
import os
import random
import string
from pathlib import Path
from typing import Dict, Optional

try:
    import aiohttp
except ImportError:
    raise ImportError("aiohttp is required: pip install aiohttp")


COOKIE_FILE = Path(__file__).parent / ".session-cookies.json"

# Azure AD B2C Configuration
CLIENT_ID = "40c94bb1-2d83-4ccc-8c72-fde8ad15ed24"
AUTHORITY = "https://login.gruppohera.it/myheraapp.onmicrosoft.com/B2C_1A_SignIn_Web"
API_BASE = "https://myhera.gruppohera.it/api/mw/v1"
SERVIZIONLINE_BASE = "https://servizionline.gruppohera.it/api"


def generate_random_string(length: int) -> str:
    """Generate random alphanumeric string."""
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def extract_cookies(set_cookie_header: Optional[str]) -> Dict[str, str]:
    """Extract cookies from Set-Cookie header."""
    if not set_cookie_header:
        return {}
    
    cookies = {}
    cookie_strings = set_cookie_header.split(', ')
    
    for cookie_str in cookie_strings:
        eq_idx = cookie_str.find('=')
        if eq_idx > 0:
            name = cookie_str[:eq_idx]
            val = cookie_str[eq_idx + 1:].split(';')[0]
            cookies[name] = val
    
    return cookies


def build_cookie_header(cookies: Dict[str, str]) -> str:
    """Build Cookie header from cookies dict."""
    return '; '.join(f"{k}={v}" for k, v in cookies.items())


def load_cookies() -> Optional[Dict]:
    """Load session cookies from cache."""
    try:
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading cookies: {e}")
    return None


def save_cookies(cookies: Dict):
    """Save session cookies to cache."""
    with open(COOKIE_FILE, 'w') as f:
        json.dump(cookies, f, indent=2)


def clear_cookies():
    """Clear cached cookies."""
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()


def get_cookie_header() -> Optional[str]:
    """Get cookie header string for API calls."""
    cookies = load_cookies()
    if not cookies:
        return None
    return build_cookie_header(cookies)


def is_authenticated() -> bool:
    """Check if valid session is cached."""
    cookies = load_cookies()
    if not cookies:
        return False
    return bool(
        cookies.get('profile') or 
        cookies.get('accessToken') or
        any(k.startswith('x-ms-cpim-sso') for k in cookies.keys())
    )


async def authenticate_with_b2c(email: str, password: str) -> Dict:
    """
    Full Azure AD B2C OAuth flow with cookies.
    Returns session cookies.
    """
    # Generate PKCE parameters
    code_verifier = generate_random_string(43)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')
    
    state = generate_random_string(32)
    nonce = generate_random_string(32)
    client_request_id = generate_random_string(36)
    
    # Build authorize URL
    from urllib.parse import urlencode
    
    scope = 'openid offline_access https://myheraapp.onmicrosoft.com/40c94bb1-2d83-4ccc-8c72-fde8ad15ed24/read profile'
    state_value = json.dumps({'id': generate_random_string(32), 'meta': {'interactionType': 'redirect'}})
    
    authorize_url = f"{AUTHORITY}/oauth2/v2.0/authorize?{urlencode({
        'client_id': CLIENT_ID,
        'scope': scope,
        'redirect_uri': 'https://servizionline.gruppohera.it/auth/hera/login',
        'response_type': 'code',
        'response_mode': 'fragment',
        'state': state_value,
        'nonce': nonce,
        'client-request-id': client_request_id,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
        'referrer': 'hera',
        'env': 'prod'
    })}"
    
    # Step 1: Get initial session
    print("Step 1: Getting initial session...")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            authorize_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.5',
            },
            allow_redirects=False
        ) as resp:
            cookies = extract_cookies(resp.headers.get('set-cookie', ''))
            
            if 'x-ms-cpim-csrf' not in cookies:
                raise Exception("Failed to get CSRF token from initial session")
            
            # Extract TID from x-ms-cpim-trans cookie
            trans_cookie = cookies.get('x-ms-cpim-trans', '')
            tid = None
            
            if trans_cookie:
                try:
                    padded = trans_cookie + '=' * (4 - len(trans_cookie) % 4)
                    json_data = base64.b64decode(padded).decode()
                    data = json.loads(json_data)
                    tid = data.get('T_DIC', [{}])[0].get('I') or data.get('C_ID')
                except Exception as e:
                    print(f"Warning: Could not extract TID: {e}")
            
            if not tid:
                tid = generate_random_string(36)
                print(f"  Generated TID: {tid}")
            else:
                print(f"  Got TID: {tid}")
            
            print("  Got CSRF token")
            
            # Step 2: Submit credentials
            csrf_token = cookies['x-ms-cpim-csrf']
            tx_state = base64.b64encode(json.dumps({'TID': tid}).encode()).decode()
            
            self_asserted_url = f"{AUTHORITY}/SelfAsserted?tx=StateProperties={tx_state}&p=B2C_1A_SignIn_Web"
            
            print("Step 2: Submitting credentials...")
            async with session.post(
                self_asserted_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-CSRF-TOKEN': csrf_token,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': 'https://login.gruppohera.it',
                    'Referer': authorize_url,
                    'Cookie': build_cookie_header(cookies),
                },
                data={
                    'request_type': 'RESPONSE',
                    'signInName': email,
                    'password': password
                }
            ) as cred_resp:
                if not cred_resp.ok:
                    error_text = await cred_resp.text()
                    raise Exception(f"Authentication failed: {error_text}")
                
                cred_data = await cred_resp.json()
                
                if cred_data.get('status') == '400' or cred_data.get('errors'):
                    raise Exception(f"Invalid credentials: {cred_data}")
                
                # Update cookies
                cred_cookies = extract_cookies(cred_resp.headers.get('set-cookie', ''))
                cookies.update(cred_cookies)
                
                print("  Credentials accepted")
            
            # Step 3: Get redirect
            print("Step 3: Getting redirect...")
            
            # Use wall clock time (like Node.js Date.now() / 1000), not monotonic time
            import time
            base_time = int(time.time())
            page_view_id = generate_random_string(36)
            
            # Build diags parameter with trace data (from HAR analysis)
            diags = {
                "pageViewId": page_view_id,
                "pageId": "CombinedSigninAndSignup",
                "trace": [
                    {"ac": "T005", "acST": base_time, "acD": 1},
                    {"ac": f"T021 - URL:{AUTHORITY}/b2c/login_sol.html", "acST": base_time, "acD": 500},
                    {"ac": "T019", "acST": base_time + 1, "acD": 3},
                    {"ac": "T004", "acST": base_time + 1, "acD": 2},
                    {"ac": "T003", "acST": base_time + 1, "acD": 2},
                    {"ac": "T035", "acST": base_time + 1, "acD": 0},
                    {"ac": "T030Online", "acST": base_time + 1, "acD": 0},
                    {"ac": "T002", "acST": base_time + 17, "acD": 0},
                    {"ac": "T018T010", "acST": base_time + 16, "acD": 1040}
                ]
            }
            from urllib.parse import quote
            diags_param = quote(json.dumps(diags))
            
            # Build exact Referer from the authorize request (with all original params)
            from urllib.parse import urlencode
            scope = 'openid offline_access https://myheraapp.onmicrosoft.com/40c94bb1-2d83-4ccc-8c72-fde8ad15ed24/read profile'
            state_value = json.dumps({'id': generate_random_string(32), 'meta': {'interactionType': 'redirect'}})
            authorize_referer = f"{AUTHORITY.lower()}/oauth2/v2.0/authorize?{urlencode({
                'client_id': CLIENT_ID,
                'scope': scope,
                'redirect_uri': 'https://servizionline.gruppohera.it/auth/hera/login',
                'response_type': 'code',
                'response_mode': 'fragment',
                'state': state_value,
                'nonce': nonce,
                'client-request-id': client_request_id,
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256',
                'referrer': 'hera',
                'env': 'prod'
            })}"
            
            combined_url = f"{AUTHORITY}/api/CombinedSigninAndSignup/confirmed?rememberMe=false&csrf_token={quote(csrf_token)}&tx=StateProperties={tx_state}&p=B2C_1A_SignIn_Web"
            
            async with session.get(
                combined_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
                    'Cookie': build_cookie_header(cookies),
                    'Referer': authorize_referer,
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Pragma': 'no-cache',
                    'Cache-Control': 'no-cache',
                },
                allow_redirects=False
            ) as combined_resp:
                if combined_resp.status != 302:
                    body = await combined_resp.text()
                    raise Exception(f"Expected 302 redirect, got {combined_resp.status}")
                
                location = combined_resp.headers.get('location')
                if not location:
                    raise Exception("No redirect location from CombinedSigninAndSignup")
                
                print(f"  Got redirect location: {location[:100]}...")
                
                # Update cookies
                combined_cookies = extract_cookies(combined_resp.headers.get('set-cookie', ''))
                cookies.update(combined_cookies)
            
            # Step 4: Exchange code for token
            print("Step 3: Exchanging code for token...")
            
            hash_idx = location.find('#')
            if hash_idx == -1:
                raise Exception("No hash fragment in redirect URL")
            
            code_fragment = location[hash_idx + 1:]
            from urllib.parse import parse_qs
            params = parse_qs(code_fragment)
            code = params.get('code', [None])[0]
            
            if not code:
                raise Exception("No code in redirect URL fragment")
            
            callback_url = location[:hash_idx]
            
            async with session.post(
                f"{AUTHORITY}/oauth2/v2.0/token",
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Cookie': build_cookie_header(cookies),
                    'x-client-SKU': 'msal.js.browser',
                    'x-client-VER': '2.35.0',
                },
                data={
                    'client_id': CLIENT_ID,
                    'redirect_uri': 'https://servizionline.gruppohera.it/auth/hera/login',
                    'scope': scope,
                    'code': code,
                    'grant_type': 'authorization_code',
                    'code_verifier': code_verifier,
                    'client_info': '1',
                }
            ) as token_resp:
                if not token_resp.ok:
                    error_text = await token_resp.text()
                    raise Exception(f"Token exchange failed: {error_text}")
                
                token_data = await token_resp.json()
                print("  Got access token")
                
                cookies['accessToken'] = token_data['access_token']
                
                # Update cookies from token response
                token_cookies = extract_cookies(token_resp.headers.get('set-cookie', ''))
                cookies.update(token_cookies)
            
            # Step 5: Establish session with servizionline
            print("Step 4: Establishing session with servizionline...")
            
            async with session.get(
                callback_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
                    'Accept': 'text/html,application/xhtml+xml',
                    'Cookie': build_cookie_header(cookies),
                    'Referer': 'https://servizionline.gruppohera.it/',
                },
                allow_redirects=True
            ) as callback_resp:
                final_cookies = extract_cookies(callback_resp.headers.get('set-cookie', ''))
                cookies.update(final_cookies)
                
                print(f"  Response URL: {callback_resp.url}")
                print(f"  Cookies received: {list(cookies.keys())}")
                
                has_session = cookies.get('profile') or any(k.startswith('x-ms-cpim-sso') for k in cookies.keys())
                
                if not has_session:
                    raise Exception("No session cookie received - authentication failed")
                
                print("  Session established!")
    
    return cookies


async def login(email: str, password: str) -> Dict:
    """
    Login with email/password - returns session cookies.
    Uses cached session if available.
    """
    # Check for cached session
    cached = load_cookies()
    if cached and (cached.get('profile') or any(k.startswith('x-ms-cpim-sso') for k in cached.keys())):
        print("Using cached session")
        return cached
    
    # Perform login
    cookies = await authenticate_with_b2c(email, password)
    
    # Check for session cookie
    has_session = cookies.get('profile') or any(k.startswith('x-ms-cpim-sso') for k in cookies.keys())
    
    if has_session:
        save_cookies(cookies)
        print("Login successful! Session cached.")
    else:
        raise Exception("Login failed - no session cookie received")
    
    return cookies


async def logout():
    """Clear stored authentication session."""
    clear_cookies()
    print("Logged out. Session cleared.")


# Async wrapper for sync functions
async def get_cookie_header_async() -> Optional[str]:
    """Get cookie header string for API calls."""
    return get_cookie_header()
