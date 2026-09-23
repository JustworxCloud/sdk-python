# justworx-sdk

The official **Python SDK** for the Justworx API (`/api/v2`) -- a thin, ergonomic client over
`httpx`. Sibling to [`@justworxcloud/sdk`](https://github.com/JustworxCloud/sdk) (TypeScript);
same contract, same method behaviour, Python's own keyword-argument idiom instead of an options
object.

## Install

```sh
pip install justworx-sdk
```

## Use

```python
from justworx import Justworx, JustworxError

jwx = Justworx(api_key="jwx_live_...")  # or an OAuth2 access token

# who am I?
me = jwx.whoami()

# list devices, or iterate them all (auto-pagination)
page = jwx.list_devices(online=True)
for d in jwx.devices():
    print(d["serial"], d["name"])

# read one device's live state (the twin)
device = jwx.get_device("ABCD1234")

# actuate -- confirm=True waits for the device's real answer
jwx.set_io("ABCD1234", 10, "high", confirm=True)
jwx.pulse_io("ABCD1234", 10, "high", 3000, revert_state="low")
jwx.cancel_timer("ABCD1234", 10)
jwx.set_rule("ABCD1234", 1, False)

# on-device automations -- run on the device itself, keep working offline
rules = jwx.list_rules("ABCD1234")
jwx.create_rule("ABCD1234", {
    "ruleNumber": 12, "type": "digital",
    "if": {"id": 5, "state": "high"},
    "then": {"type": "refreshId", "idNumber": 14},
})
jwx.delete_rule("ABCD1234", 12)
jwx.clear_rules("ABCD1234", confirm=True)  # confirm is REQUIRED here -- deletes ALL rules

# a device's history (commands sent, replies received, values reported, connection changes)
log = jwx.get_device_log("ABCD1234")

# errors are typed
try:
    jwx.get_device("nope")
except JustworxError as e:
    if e.status == 404:
        ...

jwx.close()  # or: with Justworx(api_key=...) as jwx: ...
```

Every method is a deliberate port of the TypeScript SDK's `client.js` -- same endpoints, same
required/optional fields, same `confirm`/`timeoutMs` convention. If you already know one, you know
the other. A few things are intentionally Python-idiomatic rather than mirrored: a `close()`/
context-manager (real connection pool, unlike `openapi-fetch`), network failures raised as
`JustworxConnectionError` instead of the raw `httpx` exception, and named keyword arguments on
`list_devices`/`devices()` instead of an arbitrary query object.

## Auth

Pass a `jwx_live_…` **API key** (server-to-server), or an **OAuth2 access token** from
`https://oauth.justworx.com` (scopes: `devices:read`, `devices:command`, `devices:configure`,
`devices:own`, `events:read`) -- the SDK just sends whatever bearer you give it.

## The `confirm` convention

Every write call defaults to fire-and-forget: the request returns `202 sent` as soon as the
command reaches the device's queue. Pass `confirm=True` to wait instead for the device's real
answer (up to 8 seconds) and get back a `confirmed` result with the actual state.

`Justworx.clear_rules()` is the one exception -- there, `confirm` is not this waiting convenience
at all. It is a **required wire field**: the API will not delete every rule on a device without
`confirm: true` in the request body, and this client enforces that locally (raises `ValueError`
before making any request) rather than silently sending a no-op call. Never infer it from a vague
"clean up the rules" -- always confirm with the caller first.

## Rules

A rule is logic that lives **on the device itself** -- evaluated continuously, no cloud round
trip, and it keeps working when the device is offline. A rule's own `then` can fire almost any
action the API supports, **except** `createRule`/`deleteRule`/`clearRules` (rule management
cannot itself be a rule's action -- `getRules` and `refreshId` are fine, since reading changes
nothing). See the OpenAPI spec's `RuleCreate` schema for the exact condition (`if`) shape per
rule `type` (`digital`/`analog`/`schedule`).

## Known gap: capability actuation

Each ID may carry a `capability` (`type`/`names`/`secure`, e.g. `GarageDoor` / `["Door"]`) when
the owner has authored one -- `get_device()` returns it per ID under `ids[i]["capability"]`, and
`capability["names"][0]` is the human label to show, when present. There is, however, no
capability-*command* endpoint on `/api/v2` -- actuation always stays at the raw ID level via
`set_io()`/`pulse_io()` against that ID's number. This SDK does not invent one.

## Events

Justworx's own live feed is a WebSocket (`wss://api.justworx.com/api/v2/stream`), not covered by
this SDK yet. Device **history** (as opposed to the live feed) is `jwx.get_device_log(serial)`.

## Testing your own code against this SDK

Inject a custom transport instead of hitting the real API:

```python
import httpx
from justworx import Justworx

def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"accountId": "acct_test", "authType": "api_key", "userId": None, "scopes": []})

jwx = Justworx("jwx_live_test", transport=httpx.MockTransport(handler))
assert jwx.whoami()["accountId"] == "acct_test"
```

## Develop

```sh
pip install -e ".[dev]"
pytest
```

## Layout

```
src/justworx/client.py    the Justworx client (httpx-based)
src/justworx/errors.py    JustworxError, JustworxConnectionError
src/justworx/types.py     hand-typed TypedDict shapes (documentation only, not runtime-validated)
src/justworx/__init__.py  public exports
tests/test_client.py      unit tests against a mocked transport (httpx.MockTransport)
```

`types.py` is hand-maintained, not generated -- there is no Python equivalent of the TypeScript
SDK's `openapi-typescript` step in this package. If the API contract changes, check it against
the canonical spec ([`JustworxCloud/OpenAPI`](https://github.com/JustworxCloud/OpenAPI)) by hand.
