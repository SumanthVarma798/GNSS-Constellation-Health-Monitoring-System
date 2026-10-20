"""Streamlit 1.53's fix for Google sign-in, applied to Streamlit 1.45. Delete this file once Streamlit is 1.53 or later.

Authlib 1.6.6 and later write the sign-in state into a session as well as the cache. Streamlit 1.45 has no session
and passes None, so signing in failed with "'NoneType' object does not support item assignment". Authlib before
1.6.11 has published security holes, so the fix goes here instead: keep the state in the cache only, as Streamlit 1.53
does (streamlit/web/server/authlib_tornado_integration.py, Apache License 2.0). tests/test_admin_page.py says when
this file is no longer needed.

Known limit, as in Streamlit 1.53: the state is not tied to the browser that started signing in, so someone could start
a sign-in and trick another person into finishing it, signing them in as the first. The allow-list still decides who
gets in, and every decision names the signed-in person.
"""
import json

import streamlit
from packaging.version import InvalidVersion, Version

try:
    from streamlit.web.server.authlib_tornado_integration import TornadoIntegration
except ImportError:   # a later Streamlit moved it, and by then has the fix itself
    TornadoIntegration = None

FIXED_IN = Version("1.53")


def _key(integration, state):
    return f"_state_{integration.name}_{state}"


def set_state_data(self, session, state, data):
    self.cache.set(_key(self, state), json.dumps({"data": data}), self.expires_in)


def get_state_data(self, session, state):
    try:
        kept = json.loads(self.cache.get(_key(self, state)) or "null")
    except (TypeError, ValueError):
        return None
    return kept.get("data") if isinstance(kept, dict) else None


def clear_state_data(self, session, state):
    self.cache.delete(_key(self, state))


def needed():
    try:
        return TornadoIntegration is not None and Version(streamlit.__version__) < FIXED_IN
    except InvalidVersion:
        return False


def apply():
    """Put the three methods on Streamlit's sign-in integration, when this Streamlit lacks them."""
    if needed():
        TornadoIntegration.set_state_data = set_state_data
        TornadoIntegration.get_state_data = get_state_data
        TornadoIntegration.clear_state_data = clear_state_data
