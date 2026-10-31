"""Hafnia Gateway API client.

Implements the workflow described in ``gateway-api.md``:
1. Login via ``POST /api/Sessions/Login``
2. Submit a summary request via ``POST /api/Summaries``
3. Poll ``GET /api/Summaries/{id}`` until ``Progress`` is ``Completed`` or ``Failed``.

Configuration is resolved in this order for each setting:
1. Environment variable (e.g. ``HAFNIA_PASSWORD``) – highest priority.
2. ``.env`` file in the project root (loaded once at import time via python-dotenv).
3. Streamlit ``secrets.toml`` (``[HAFNIA_PASSWORD]``) – used when running under
   Streamlit and a secrets file exists.
4. Hard-coded default (URL and username only – **never** for the password).

Required keys:
- ``HAFNIA_GATEWAY_URL`` – e.g. ``https://localhost:15443``
- ``HAFNIA_USERNAME`` – gateway user name (default ``administrator``)
- ``HAFNIA_PASSWORD`` – gateway password; **must** be provided

The client disables SSL verification because the gateway uses a self-signed certificate.
"""
import os
import time
from typing import Any, Dict, Optional

import requests

# Load a .env file from the project root into os.environ if one exists.
# This is a no-op when the file is absent, so tests and CI work without it.
try:
    from dotenv import load_dotenv as _load_dotenv  # type: ignore
    _load_dotenv(override=False)  # env vars already set in the shell take precedence
except ImportError:
    pass  # python-dotenv is optional; env vars and Streamlit secrets still work


def _get_config(env_key: str, secret_key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a configuration value safely.

    Resolution order:
    1. Environment variable ``env_key``.
    2. Streamlit secret ``secret_key`` (only when Streamlit is importable *and* a
       ``secrets.toml`` file exists – ``StreamlitSecretNotFoundError`` is caught).
    3. ``default``.

    This helper never raises due to a missing Streamlit secrets file, so the
    client can be instantiated in plain‑Python test environments without any
    ``secrets.toml``.
    """
    # 1. Environment variable wins.
    value = os.getenv(env_key)
    if value is not None:
        return value

    # 2. Attempt to read from Streamlit secrets.
    try:
        import streamlit as st  # type: ignore
        # Access via attribute to avoid .get() triggering __getitem__ on the
        # Secrets proxy, which raises StreamlitSecretNotFoundError.
        return st.secrets[secret_key]  # type: ignore[index]
    except KeyError:
        # Secret key not present in an existing secrets file – use default.
        pass
    except Exception:
        # Covers StreamlitSecretNotFoundError (no secrets.toml),
        # ImportError (Streamlit not installed), and any other issue.
        pass

    return default


def build_xprotect_uri(camera_id: str, start: "datetime", end: "datetime") -> str:  # noqa: F821
    """Build an XProtect camera URI from a camera ID and two UTC datetimes.

    Both ``start`` and ``end`` must be timezone-aware UTC datetimes (``tzinfo`` set to
    ``timezone.utc``).  The function formats each timestamp as ISO 8601 with a trailing
    ``Z`` (required by the Gateway – ``+`` characters in query strings are interpreted as
    spaces).

    Parameters
    ----------
    camera_id:
        The XProtect camera GUID, e.g. ``E0036434-54F2-4977-82D0-F86FCD47F977``.
    start:
        Clip start time in UTC.
    end:
        Clip end time in UTC.  Must be strictly after ``start``.

    Returns
    -------
    str
        A fully-formed ``xprotect://`` URI.

    Raises
    ------
    ValueError
        If ``end`` is not strictly after ``start``, or if either datetime is not
        timezone-aware.
    """
    from datetime import datetime, timezone  # local import keeps the module-level clean

    for label, dt in (("start", start), ("end", end)):
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError(f"{label} datetime must be timezone-aware (UTC).")

    if end <= start:
        raise ValueError("End time must be strictly after start time.")

    def _fmt(dt: datetime) -> str:
        # Normalize to UTC first so any offset (e.g. +02:00) becomes 00:00,
        # then replace +00:00 with Z (required by the Gateway API).
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat(timespec="seconds").replace("+00:00", "Z")

    return (
        f"xprotect://localhost/cameras/{camera_id}"
        f"?StartTime={_fmt(start)}&EndTime={_fmt(end)}"
    )


class HafniaClient:
    """Thin wrapper around the Hafnia Gateway REST API.

    The client is deliberately lightweight – it does **not** store any state beyond the
    current session identifier. All network calls use a short timeout and raise clear
    exceptions on HTTP errors.
    """

    def __init__(self, *, enabled: bool = True, timeout: int = 10):
        """Create a client.

        Parameters
        ----------
        enabled:
            Set to ``False`` to keep the client inert (useful for environments where the
            gateway is not reachable). When ``True`` the client reads configuration from
            environment variables or ``st.secrets``.
        timeout:
            HTTP request timeout in seconds.
        """
        self.enabled = enabled
        self.timeout = timeout
        if not enabled:
            # A disabled client behaves like a stub – all public methods raise.
            return

        # Resolve configuration using the safe helper which checks env vars first,
        # then Streamlit secrets (if available), then a hard‑coded default.
        self.base_url = _get_config("HAFNIA_GATEWAY_URL", "HAFNIA_GATEWAY_URL", "https://localhost:15443")
        self.username = _get_config("HAFNIA_USERNAME", "HAFNIA_USERNAME", "administrator")
        self.password = _get_config("HAFNIA_PASSWORD", "HAFNIA_PASSWORD")
        if not self.password:
            raise RuntimeError("HAFNIA_PASSWORD must be provided via environment variable or Streamlit secret.")

        # A ``requests.Session`` re‑uses the underlying TCP connection and makes it easy to
        # attach the ``X-Session-Id`` header after login.
        self.session = requests.Session()
        # Accept the self‑signed cert used by the gateway.
        self.session.verify = False
        self.session_id: Optional[str] = None

    # ---------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _ensure_logged_in(self) -> None:
        if self.session_id:
            return
        login_url = self._url("/api/Sessions/Login")
        payload = {"Name": self.username, "Password": self.password}
        resp = self.session.post(login_url, json=payload, timeout=self.timeout)
        if resp.status_code == 401:
            raise RuntimeError("Authentication failed – check HAFNIA_USERNAME / HAFNIA_PASSWORD.")
        resp.raise_for_status()
        data = resp.json()
        self.session_id = data.get("Id")
        if not self.session_id:
            raise RuntimeError("Login response did not contain a session Id.")
        self.session.headers.update({"X-Session-Id": self.session_id})

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def submit_summary(
        self,
        prompt: str,
        video_uri: str,
        ai_model_id: str = "traffic-general",
    ) -> str:
        """Submit a summary request.

        Returns the request ``Id`` which can be used with :meth:`get_summary`.
        """
        if not self.enabled:
            raise RuntimeError("Hafnia client is disabled.")
        self._ensure_logged_in()
        url = self._url("/api/Summaries")
        payload = {"Prompt": prompt, "VideoUris": [video_uri], "AiModelId": ai_model_id}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code == 400:
            raise RuntimeError(f"Bad request when submitting summary: {resp.json().get('Message', resp.text)}")
        resp.raise_for_status()
        data = resp.json()
        return data["Id"]

    def get_summary(self, request_id: str) -> Dict[str, Any]:
        """Retrieve a summary request status.

        The returned dictionary mirrors the JSON payload described in the API docs and
        includes ``Progress`` as well as ``Response`` or ``LastError`` when finished.
        """
        if not self.enabled:
            raise RuntimeError("Hafnia client is disabled.")
        self._ensure_logged_in()
        url = self._url(f"/api/Summaries/{request_id}")
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code == 404:
            raise RuntimeError(f"Summary request {request_id} not found.")
        resp.raise_for_status()
        return resp.json()

    def wait_for_completion(
        self,
        request_id: str,
        poll_interval: int = 3,
        max_minutes: int = 10,
    ) -> Dict[str, Any]:
        """Poll the gateway until the request is finished or the timeout is reached.

        Returns the final payload (either ``Completed`` or ``Failed``). Raises ``TimeoutError``
        if the operation does not finish within ``max_minutes``.
        """
        deadline = time.time() + max_minutes * 60
        while time.time() < deadline:
            result = self.get_summary(request_id)
            progress = result.get("Progress")
            if progress in {"Completed", "Failed"}:
                return result
            time.sleep(poll_interval)
        raise TimeoutError("Hafnia summary request did not finish within the allotted time.")

    # ---------------------------------------------------------------------
    # Optional helper for a single‑step flow used by the UI.
    # ---------------------------------------------------------------------
    def run_summary_workflow(
        self,
        prompt: str,
        video_uri: str,
        ai_model_id: str = "traffic-general",
        poll_interval: int = 3,
        max_minutes: int = 10,
    ) -> Dict[str, Any]:
        """Convenience wrapper that logs in, submits a request, and waits for the answer.
        """
        request_id = self.submit_summary(prompt, video_uri, ai_model_id)
        return self.wait_for_completion(request_id, poll_interval, max_minutes)
