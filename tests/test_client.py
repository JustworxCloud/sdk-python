"""Unit tests against the CURRENT /api/v2 contract, mocked at the transport layer via
httpx.MockTransport -- no real network call, no server involved. Response shapes are taken
from openapi/v2/*.yaml's own examples, not invented.
"""

from __future__ import annotations

import json as jsonlib

import httpx
import pytest

from justworx import Justworx, JustworxError

BASE = "https://mock.test/api/v2"
API_KEY = "jwx_live_test_0123456789"


def _body(request: httpx.Request) -> dict:
    return jsonlib.loads(request.content) if request.content else {}


def make_router(handler):
    """Wrap a routing function as an httpx.MockTransport-backed Justworx client."""
    return Justworx(API_KEY, base_url=BASE, transport=httpx.MockTransport(handler))


def router(request: httpx.Request) -> httpx.Response:
    method = request.method
    path = request.url.path.replace("/api/v2", "")
    body = _body(request)

    if method == "GET" and path == "/me":
        return httpx.Response(200, json={
            "accountId": "acct_0001", "authType": "api_key", "userId": None,
            "scopes": ["devices:read", "devices:command", "devices:configure", "devices:own", "events:read"],
        })

    if method == "GET" and path == "/devices":
        if not request.url.params.get("cursor"):
            return httpx.Response(200, json={
                "items": [{"serial": "ABCD1234", "name": "Main Gate", "online": True,
                           "lastSeenAt": "2026-08-13T09:41:58.000Z", "access": "owner"}],
                "nextCursor": "page2",
            })
        return httpx.Response(200, json={
            "items": [{"serial": "EFGH5678", "name": "Side Gate", "online": False,
                       "lastSeenAt": None, "access": "owner"}],
            "nextCursor": None,
        })

    if method == "GET" and path == "/devices/ZZZZ9999":
        return httpx.Response(404, json={"error": "NOT_FOUND", "detail": "No such device."})

    if method == "GET" and path == "/devices/ABCD1234":
        return httpx.Response(200, json={
            "serial": "ABCD1234", "name": "Main Gate", "online": True,
            "lastSeenAt": "2026-08-13T09:41:58.000Z", "access": "owner",
            "connection": "cellular", "network": {"carrier": "Vodacom", "signal": -71},
            "location": None,
            "ids": [{"idNumber": 10, "type": "digitalOutput", "value": "low", "at": "2026-08-13T09:41:55.000Z"}],
            "rules": [{"ruleNumber": 1, "type": "digital", "enabled": True}],
            "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "PUT" and path == "/devices/ABCD1234/ids/10/value":
        if body.get("timeoutMs"):
            return httpx.Response(200, json={
                "status": "confirmed", "serial": "ABCD1234", "requestId": body.get("requestId"),
                "idNumber": 10, "value": body["value"], "at": "2026-08-13T09:42:03.000Z",
            })
        return httpx.Response(202, json={"status": "sent", "serial": "ABCD1234", "requestId": body.get("requestId")})

    if method == "POST" and path == "/devices/ABCD1234/ids/10/timer":
        if body.get("timeoutMs"):
            return httpx.Response(200, json={
                "status": "confirmed", "serial": "ABCD1234", "requestId": body.get("requestId"),
                "idNumber": 10, "value": body["value"], "revertsInMs": body["durationMs"],
                "at": "2026-08-13T09:42:03.000Z",
            })
        return httpx.Response(202, json={"status": "sent", "serial": "ABCD1234", "requestId": body.get("requestId")})

    if method == "DELETE" and path == "/devices/ABCD1234/ids/10/timer":
        if body.get("timeoutMs"):
            return httpx.Response(200, json={
                "status": "confirmed", "serial": "ABCD1234", "requestId": body.get("requestId"),
                "idNumber": 10, "restoredTo": "low", "at": "2026-08-13T09:42:03.000Z",
            })
        return httpx.Response(202, json={"status": "sent", "serial": "ABCD1234", "requestId": body.get("requestId")})

    if method == "PATCH" and path == "/devices/ABCD1234/rules/1":
        return httpx.Response(200, json={
            "status": "confirmed", "serial": "ABCD1234", "requestId": body.get("requestId"),
            "ruleNumber": 1, "enabled": body["enabled"], "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "GET" and path == "/devices/ABCD1234/log":
        return httpx.Response(200, json={
            "serial": "ABCD1234",
            "items": [{"at": "2026-08-13T09:41:57.000Z", "kind": "device", "type": "value_reported",
                       "category": "state", "idNumber": 10, "value": "low"}],
            "nextCursor": None, "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "GET" and path == "/devices/ABCD1234/rules":
        return httpx.Response(200, json={
            "serial": "ABCD1234",
            "items": [{"ruleNumber": 1, "type": "digital", "enabled": True}],
            "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "POST" and path == "/devices/ABCD1234/rules":
        return httpx.Response(200, json={
            "status": "sent", "serial": "ABCD1234", "requestId": body.get("requestId"),
            "ruleNumber": body["ruleNumber"], "type": body["type"], "result": "ok",
            "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "DELETE" and path == "/devices/ABCD1234/rules/12":
        return httpx.Response(200, json={
            "status": "sent", "serial": "ABCD1234", "ruleNumber": 12, "at": "2026-08-13T09:42:03.000Z",
        })

    if method == "DELETE" and path == "/devices/ABCD1234/rules":
        if body.get("confirm") is not True:
            return httpx.Response(400, json={"error": "INVALID_FIELDS", "detail": "confirm: true is required"})
        return httpx.Response(200, json={
            "status": "sent", "serial": "ABCD1234", "requestId": body.get("requestId"),
            "cleared": 2, "result": "ok", "at": "2026-08-13T09:42:03.000Z",
        })

    return httpx.Response(404, json={"error": "NOT_FOUND", "detail": f"no mock for {method} {path}"})


@pytest.fixture
def jwx():
    with make_router(router) as client:
        yield client


def test_whoami(jwx):
    me = jwx.whoami()
    assert me["accountId"] == "acct_0001"
    assert me["authType"] == "api_key"
    assert me["userId"] is None
    assert len(me["scopes"]) == 5


def test_list_devices_and_devices_iterator_follows_cursor(jwx):
    page = jwx.list_devices(online=True)
    assert page["items"][0]["serial"] == "ABCD1234"
    assert page["nextCursor"] == "page2"

    all_serials = [d["serial"] for d in jwx.devices()]
    assert all_serials == ["ABCD1234", "EFGH5678"]


def test_get_device_returns_twin_unknown_serial_raises(jwx):
    d = jwx.get_device("ABCD1234")
    assert d["ids"][0]["idNumber"] == 10
    assert d["rules"][0]["ruleNumber"] == 1

    with pytest.raises(JustworxError) as exc_info:
        jwx.get_device("ZZZZ9999")
    assert exc_info.value.status == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_set_io_confirm_vs_fire_and_forget(jwx):
    confirmed = jwx.set_io("ABCD1234", 10, "high", confirm=True)
    assert confirmed["status"] == "confirmed"
    assert confirmed["idNumber"] == 10
    assert confirmed["value"] == "high"

    sent = jwx.set_io("ABCD1234", 10, "low")
    assert sent["status"] == "sent"


def test_pulse_io_maps_duration_and_revert_state(jwx):
    confirmed = jwx.pulse_io("ABCD1234", 10, "high", 3000, revert_state="low", confirm=True)
    assert confirmed["status"] == "confirmed"
    assert confirmed["revertsInMs"] == 3000

    sent = jwx.pulse_io("ABCD1234", 10, "high", 3000)
    assert sent["status"] == "sent"


def test_cancel_timer(jwx):
    confirmed = jwx.cancel_timer("ABCD1234", 10, confirm=True)
    assert confirmed["status"] == "confirmed"
    assert confirmed["restoredTo"] == "low"

    sent = jwx.cancel_timer("ABCD1234", 10)
    assert sent["status"] == "sent"


def test_set_rule(jwx):
    res = jwx.set_rule("ABCD1234", 1, False, confirm=True)
    assert res["status"] == "confirmed"
    assert res["ruleNumber"] == 1
    assert res["enabled"] is False


def test_get_device_log(jwx):
    log = jwx.get_device_log("ABCD1234")
    assert log["serial"] == "ABCD1234"
    assert len(log["items"]) >= 1


def test_list_rules(jwx):
    res = jwx.list_rules("ABCD1234")
    assert res["serial"] == "ABCD1234"
    assert res["items"][0]["ruleNumber"] == 1


def test_create_rule_posts_full_body(jwx):
    res = jwx.create_rule("ABCD1234", {
        "ruleNumber": 12, "type": "digital",
        "if": {"id": 5, "state": "high"},
        "then": {"type": "refreshId", "idNumber": 14},
    })
    assert res["status"] == "sent"
    assert res["ruleNumber"] == 12
    assert res["type"] == "digital"


def test_delete_rule(jwx):
    res = jwx.delete_rule("ABCD1234", 12)
    assert res["status"] == "sent"
    assert res["ruleNumber"] == 12


def test_clear_rules_refuses_locally_without_confirm_true(jwx):
    with pytest.raises(ValueError, match="confirm=True"):
        jwx.clear_rules("ABCD1234", confirm=False)
    with pytest.raises(ValueError, match="confirm=True"):
        jwx.clear_rules("ABCD1234")  # confirm omitted entirely -- keyword-only, defaults to False


def test_clear_rules_with_confirm_true(jwx):
    res = jwx.clear_rules("ABCD1234", confirm=True)
    assert res["status"] == "sent"
    assert res["cleared"] == 2


def test_context_manager_closes_client():
    client = make_router(router)
    with client as jwx:
        jwx.whoami()
    assert client._client.is_closed


def test_missing_api_key_raises():
    with pytest.raises(ValueError, match="api_key"):
        Justworx("")
