"""Central configuration module for the Visualping crawler.

Loads primary project settings from environment variables, falling back to
sane defaults when a variable is unset or holds an invalid value. Also
defines the shared regex constants used by the secret finder and route
extraction modules.
"""

from __future__ import annotations

import os
import re

# Root URL the crawler starts traversal from.
ROOT_URL_ENV_VAR = "ROOT_URL"
DEFAULT_ROOT_URL = "https://challenge.visualping.io"

# Local port used when serving the generated HTML report.
APP_PORT_ENV_VAR = "APP_PORT"
DEFAULT_APP_PORT = 8000

# Network timeouts, in seconds, applied to outbound HTTP requests.
CONNECT_TIMEOUT_ENV_VAR = "CONNECT_TIMEOUT"
DEFAULT_CONNECT_TIMEOUT = 5.0

READ_TIMEOUT_ENV_VAR = "READ_TIMEOUT"
DEFAULT_READ_TIMEOUT = 10.0

# Maximum number of retry attempts for a failed network request.
MAX_RETRIES_ENV_VAR = "MAX_RETRIES"
DEFAULT_MAX_RETRIES = 3


def _get_env_str(name: str, default: str) -> str:
    """Return the environment variable as a stripped string, or default if unset/blank."""
    value = os.environ.get(name, "").strip()
    return value if value else default


def _get_env_int(name: str, default: int) -> int:
    """Return the environment variable parsed as int, or default if unset/invalid."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    """Return the environment variable parsed as float, or default if unset/invalid."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# Public, module-level settings resolved at import time.
ROOT_URL: str = _get_env_str(ROOT_URL_ENV_VAR, DEFAULT_ROOT_URL)
APP_PORT: int = _get_env_int(APP_PORT_ENV_VAR, DEFAULT_APP_PORT)
CONNECT_TIMEOUT: float = _get_env_float(CONNECT_TIMEOUT_ENV_VAR, DEFAULT_CONNECT_TIMEOUT)
READ_TIMEOUT: float = _get_env_float(READ_TIMEOUT_ENV_VAR, DEFAULT_READ_TIMEOUT)
MAX_RETRIES: int = _get_env_int(MAX_RETRIES_ENV_VAR, DEFAULT_MAX_RETRIES)

# Matches secret tokens in the exact format VISUALPING{16 hex characters}.
SECRET_PATTERN: re.Pattern[str] = re.compile(r"VISUALPING\{[a-fA-F0-9]{16}\}")

# Matches relative route-like strings (e.g. "/api/v1/users") embedded in raw
# text, inline scripts, or linked JS/CSS files. Excludes matches preceded by
# ':' so absolute "http(s)://" URLs are not mistaken for relative routes.
ROUTE_PATTERN: re.Pattern[str] = re.compile(r"(?<![\w./:])/[a-zA-Z0-9_\-./]+")
