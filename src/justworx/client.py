"""Runtime client for the Justworx API (``/api/v2``). A thin, ergonomic wrapper over ``httpx``
-- no code generation on the Python side; see ``types.py`` for why. Method names, arguments and
wire behaviour are a deliberate port of the TypeScript SDK (``@justworxcloud/sdk``, ``client.js``)
-- same endpoints, same required/optional fields, same ``confirm=True`` -> ``timeoutMs: 8000``
mapping -- translated to Python's keyword-argument idiom rather than an options object.

A handful of things are intentionally NOT a 1:1 mirror, added because they are idiomatic here and
have no equivalent need in the JS client: a ``timeout`` constructor knob, ``close()``/context-manager
support (``httpx.Client`` holds a real connection pool; ``openapi-fetch`` does not), network/timeout
failures raised as :class:`JustworxConnectionError` rather than propagating the raw ``httpx``
exception, and ``list_devices``/``devices()`` taking named keyword arguments instead of forwarding
an arbitrary query object. None of these change what goes over the wire.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from .errors import JustworxConnectionError, JustworxError

DEFAULT_BASE_URL = "https://api.justworx.com/api/v2"


def _drop_none(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


class Justworx:
    """A Justworx API client.

    Args:
        api_key: A ``jwx_live_…`` API key, or an OAuth2 access token -- either works, this just
            sends whatever bearer you give it.
        base_url: Defaults to the production API.
        timeout: Request timeout in seconds (applies per-request; a call using ``confirm=True``
            can itself wait up to 8 seconds server-side for the device, so this should generally
            stay comfortably above that).
        transport: Inject a custom ``httpx.BaseTransport`` (tests, proxies). See
            ``httpx.MockTransport`` for testing without a real network call.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Justworx: api_key is required")
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        """Close the underlying HTTP connection pool. Optional -- also usable as a context
        manager (``with Justworx(...) as jwx:``), which calls this on exit."""
        self._client.close()

    def __enter__(self) -> Justworx:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _unwrap(self, response: httpx.Response) -> dict:
        if response.status_code >= 400:
            body: dict = {}
            if response.content:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
            raise JustworxError(
                response.status_code,
                body.get("error") or f"HTTP_{response.status_code}",
                body.get("detail"),
            )
        if not response.content:
            return {}
        return response.json()

    def _request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict:
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException:
            raise JustworxConnectionError("request timed out") from None
        except httpx.HTTPError as exc:
            raise JustworxConnectionError(str(exc)) from exc
        return self._unwrap(response)

    # ---- meta ----

    def whoami(self) -> dict:
        """Introspect the calling credential: account, auth type, scopes."""
        return self._request("GET", "/me")

    # ---- devices ----

    def list_devices(
        self,
        *,
        online: bool | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict:
        """One page of devices the credential can access."""
        return self._request("GET", "/devices", params=_drop_none(online=online, limit=limit, cursor=cursor))

    def get_device(self, serial: str) -> dict:
        """One device's full state -- the twin. Never touches the device; works while it's
        offline."""
        return self._request("GET", f"/devices/{serial}")

    def devices(self, *, online: bool | None = None, limit: int | None = None) -> Iterator[dict]:
        """Iterate ALL accessible devices, transparently following cursors.

        Example:
            for d in jwx.devices():
                ...
        """
        cursor: str | None = None
        while True:
            page = self.list_devices(online=online, limit=limit, cursor=cursor)
            yield from page["items"]
            cursor = page.get("nextCursor")
            if not cursor:
                return

    # ---- device history ----

    def get_device_log(
        self,
        serial: str,
        *,
        from_: str | None = None,
        to: str | None = None,
        type: str | None = None,
        id_number: int | None = None,
        rule_number: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict:
        """One page of a device's history -- commands sent, replies received, values reported,
        connections lost and regained -- newest first. Reads stored data only: no command is
        sent, no airtime is used, and it works for an offline device.

        Not the same as a device's event *notification settings* (``GET /devices/{serial}/events``
        configures what gets pushed, not what happened).

        ``from_`` has a trailing underscore because ``from`` is a Python keyword; it maps onto
        the real ``from`` query parameter.
        """
        params = _drop_none(
            **{"from": from_, "to": to, "type": type, "idNumber": id_number, "ruleNumber": rule_number,
               "limit": limit, "cursor": cursor}
        )
        return self._request("GET", f"/devices/{serial}/log", params=params)

    # ---- IO actuation ----
    # Each of these used to be built on a single generic dispatch call, POST
    # /devices/{serial}/commands. /api/v2 has no such endpoint any more -- every action is its own
    # REST verb+path. confirm=True still means "send timeoutMs: 8000"; that mapping is unchanged,
    # it now just targets the per-action endpoint instead of the old dispatcher. confirm itself has
    # never existed on the wire -- it is purely a client-side convenience choosing whether to send
    # timeoutMs.

    def set_io(
        self,
        serial: str,
        id_number: int,
        value: Any,
        *,
        confirm: bool = False,
        force: bool | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Write an ID's value. Also how you *fire* a ``momentaryOutput``/``delayedOutput`` -- the
        value sent is ignored on those, and the timer/delay configured on the ID is what runs."""
        body = {"value": value, **_drop_none(force=force, requestId=request_id)}
        if confirm:
            body["timeoutMs"] = 8000
        return self._request("PUT", f"/devices/{serial}/ids/{id_number}/value", json=body)

    def pulse_io(
        self,
        serial: str,
        id_number: int,
        value: Any,
        duration_ms: int,
        *,
        revert_state: Any = None,
        confirm: bool = False,
        request_id: str | None = None,
    ) -> dict:
        """Drive an ID for a fixed time, then revert -- the device runs the timer itself, so the
        revert still happens even if the network drops in between."""
        body = {
            "value": value,
            "durationMs": duration_ms,
            **_drop_none(revertState=revert_state, requestId=request_id),
        }
        if confirm:
            body["timeoutMs"] = 8000
        return self._request("POST", f"/devices/{serial}/ids/{id_number}/timer", json=body)

    def cancel_timer(
        self,
        serial: str,
        id_number: int,
        *,
        confirm: bool = False,
        request_id: str | None = None,
    ) -> dict:
        """Cancel a pending timer on an ID. The pin is restored to the value it held immediately
        before the timer started -- not the timer's configured revert value."""
        body = _drop_none(requestId=request_id)
        if confirm:
            body["timeoutMs"] = 8000
        return self._request("DELETE", f"/devices/{serial}/ids/{id_number}/timer", json=body)

    def set_rule(
        self,
        serial: str,
        rule_number: int,
        enabled: bool,
        *,
        confirm: bool = False,
        request_id: str | None = None,
    ) -> dict:
        """Enable or disable a rule, leaving its definition in place. Always send the state you
        want -- there is deliberately no toggle."""
        body = {"enabled": enabled, **_drop_none(requestId=request_id)}
        if confirm:
            body["timeoutMs"] = 8000
        return self._request("PATCH", f"/devices/{serial}/rules/{rule_number}", json=body)

    # ---- rules ----
    # A rule is logic that lives ON the device -- evaluated continuously, no cloud round trip, and
    # it keeps working offline. A rule's own `then` can fire any action EXCEPT createRule/deleteRule/
    # clearRules (getRules and refreshId are fine -- reading changes nothing).

    def list_rules(self, serial: str) -> dict:
        """Every rule on the device, in evaluation order."""
        return self._request("GET", f"/devices/{serial}/rules")

    def create_rule(self, serial: str, rule: dict) -> dict:
        """Create a rule, or replace an existing one by reusing its ``ruleNumber``.

        ``rule`` is a full RuleCreate body: ``{"ruleNumber": ..., "type": "digital"|"analog"|
        "schedule", "if": {...}, "then": {...}, "name"?, "enabled"?, "runIntervalMs"?,
        "onTrueJumpToRule"?, "onFalseJumpToRule"?, "timeoutMs"?, "requestId"?}`` -- see the
        OpenAPI spec's ``RuleCreate`` schema for the condition/action shapes per type.
        """
        return self._request("POST", f"/devices/{serial}/rules", json=rule)

    def delete_rule(
        self,
        serial: str,
        rule_number: int,
        *,
        timeout_ms: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Delete one rule by number."""
        body = _drop_none(timeoutMs=timeout_ms, requestId=request_id)
        return self._request("DELETE", f"/devices/{serial}/rules/{rule_number}", json=body)

    def clear_rules(
        self,
        serial: str,
        *,
        confirm: bool = False,
        timeout_ms: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        """Delete EVERY rule on a device. Cannot be undone.

        Unlike ``confirm`` everywhere else in this client (a convenience that just waits longer
        for the device's reply), ``confirm`` here is a **required wire field** the API refuses to
        act without. It defaults to ``False`` -- same as every other ``confirm`` in this client --
        but omitting it here is refused locally with a clear error rather than silently sending a
        fire-and-forget request; it is never inferred, so pass ``confirm=True`` explicitly every
        time you actually mean it.
        """
        if confirm is not True:
            raise ValueError(
                "Justworx.clear_rules requires confirm=True -- it deletes every rule on the "
                "device and cannot be undone"
            )
        body = {"confirm": True, **_drop_none(timeoutMs=timeout_ms, requestId=request_id)}
        return self._request("DELETE", f"/devices/{serial}/rules", json=body)
