"""Errors raised by the Justworx client."""

from __future__ import annotations


class JustworxError(Exception):
    """Raised for any non-2xx response from the Justworx API (``/api/v2``).

    Attributes:
        status: HTTP status code (0 if the request never reached the server -- see
            :class:`JustworxConnectionError` for that case specifically).
        code: The API's machine-readable error code, e.g. ``"NOT_FOUND"``, ``"INVALID_FIELDS"``.
        detail: A human-readable detail string, when the API sent one.
    """

    def __init__(self, status: int, code: str, detail: str | None = None) -> None:
        message = f"{code}: {detail}" if detail else code
        super().__init__(message)
        self.status = status
        self.code = code
        self.detail = detail


class JustworxConnectionError(JustworxError):
    """The request never reached the Justworx API (DNS, TLS, timeout, connection refused)."""

    def __init__(self, detail: str) -> None:
        super().__init__(0, "NETWORK_ERROR", detail)
