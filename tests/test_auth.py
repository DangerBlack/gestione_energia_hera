"""Unit tests for auth.py — all mocked, no real credentials needed."""
import pathlib
from unittest.mock import MagicMock, mock_open, patch

import pytest


import gruppo_hera.auth as auth


@pytest.fixture(autouse=True)
def reset_auth_state():
    """Isolate module-level state between tests."""
    original_file = auth._COOKIE_FILE
    original_token = auth._access_token
    original_cache = auth._cached_cookies
    yield
    auth._COOKIE_FILE = original_file
    auth._access_token = original_token
    auth._cached_cookies = original_cache


# ---------------------------------------------------------------------------
# generate_random_string
# ---------------------------------------------------------------------------

def test_random_string_correct_length():
    assert len(auth.generate_random_string(43)) == 43
    assert len(auth.generate_random_string(32)) == 32


def test_random_string_alphanumeric_only():
    import string
    allowed = set(string.ascii_letters + string.digits)
    result = auth.generate_random_string(200)
    assert set(result) <= allowed


def test_random_string_uses_csprng():
    # Two calls must not produce the same output (probability ~0 with 43 chars)
    assert auth.generate_random_string(43) != auth.generate_random_string(43)


def test_random_string_uses_secrets_module():
    # Verify secrets.choice is called, not random.choice
    import secrets as _secrets
    with patch.object(_secrets, 'choice', wraps=_secrets.choice) as spy:
        auth.generate_random_string(10)
        assert spy.call_count == 10


# ---------------------------------------------------------------------------
# build_cookie_header
# ---------------------------------------------------------------------------

def test_build_cookie_header_format():
    result = auth.build_cookie_header({'a': '1', 'b': '2'})
    parts = result.split('; ')
    assert 'a=1' in parts
    assert 'b=2' in parts


def test_build_cookie_header_single():
    assert auth.build_cookie_header({'key': 'val'}) == 'key=val'


def test_build_cookie_header_empty():
    assert auth.build_cookie_header({}) == ''


# ---------------------------------------------------------------------------
# configure_storage
# ---------------------------------------------------------------------------

def test_configure_storage_sets_path():
    auth.configure_storage('/my/config')
    assert auth._COOKIE_FILE == pathlib.Path('/my/config/.gruppo_hera_session.json')


def test_configure_storage_outside_component_dir():
    auth.configure_storage('/ha/config')
    component_dir = pathlib.Path(__file__).parent.parent / 'custom_components' / 'gruppo_hera'
    assert not str(auth._COOKIE_FILE).startswith(str(component_dir))


# ---------------------------------------------------------------------------
# save_cookies / load_cookies / clear_cookies
# ---------------------------------------------------------------------------

def test_save_cookies_populates_memory_cache():
    auth._cached_cookies = None
    auth._access_token = None
    cookies = {'profile': 'p123', 'accessToken': 'tok', 'session': 's'}

    with patch('builtins.open', mock_open()):
        auth.save_cookies(cookies)

    assert auth._cached_cookies is not None
    assert auth._cached_cookies['profile'] == 'p123'
    assert auth._access_token == 'tok'


def test_save_cookies_excludes_access_token_from_disk():
    """The access token must never be written to disk."""
    written = {}

    m = mock_open()
    with patch('builtins.open', m):
        auth.save_cookies({'profile': 'p', 'accessToken': 'secret', 'session': 's'})
        handle = m()
        # Collect all data passed to write()
        written_data = ''.join(str(c.args[0]) for c in handle.write.call_args_list)

    assert 'secret' not in written_data


def test_load_cookies_returns_from_memory_without_disk_io():
    auth._cached_cookies = {'profile': 'p', 'accessToken': 'tok'}
    auth._access_token = 'tok'

    with patch('builtins.open', side_effect=AssertionError("disk should not be read")):
        result = auth.load_cookies()

    assert result['profile'] == 'p'
    assert result['accessToken'] == 'tok'


def test_load_cookies_returns_copy_not_reference():
    auth._cached_cookies = {'profile': 'original'}
    auth._access_token = None

    result = auth.load_cookies()
    result['profile'] = 'mutated'

    assert auth._cached_cookies['profile'] == 'original'


def test_load_cookies_reattaches_access_token_from_disk():
    """On cold start, disk data + in-memory token should be merged."""
    auth._cached_cookies = None
    auth._access_token = 'mem_token'
    disk_data = {'profile': 'p', 'session': 's'}

    with patch('pathlib.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=__import__('json').dumps(disk_data))):
        result = auth.load_cookies()

    assert result['accessToken'] == 'mem_token'
    assert result['profile'] == 'p'


def test_load_cookies_returns_none_when_no_cache_and_no_file():
    auth._cached_cookies = None
    auth._access_token = None

    with patch('pathlib.Path.exists', return_value=False):
        result = auth.load_cookies()

    assert result is None


def test_clear_cookies_resets_all_state():
    auth._access_token = 'tok'
    auth._cached_cookies = {'profile': 'p'}

    with patch('pathlib.Path.exists', return_value=False):
        auth.clear_cookies()

    assert auth._access_token is None
    assert auth._cached_cookies is None


def test_clear_cookies_deletes_file_if_exists():
    auth._access_token = None
    auth._cached_cookies = None

    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.unlink') as mock_unlink:
        auth.clear_cookies()
        mock_unlink.assert_called_once()


# ---------------------------------------------------------------------------
# get_cookie_header
# ---------------------------------------------------------------------------

def test_get_cookie_header_returns_none_when_not_authenticated():
    auth._cached_cookies = None
    with patch('pathlib.Path.exists', return_value=False):
        assert auth.get_cookie_header() is None


def test_get_cookie_header_builds_header_from_cache():
    auth._cached_cookies = {'profile': 'p', 'session': 's'}
    auth._access_token = None
    header = auth.get_cookie_header()
    assert 'profile=p' in header
    assert 'session=s' in header
