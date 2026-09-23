"""Hand-typed shapes for the Justworx API (``/api/v2``), read straight from the canonical
OpenAPI spec (`JustworxCloud/OpenAPI <https://github.com/JustworxCloud/OpenAPI>`_) rather than
generated -- there is no Python equivalent of the TypeScript SDK's ``openapi-typescript`` step
in this package. These are
``TypedDict``\\ s: documentation and editor/type-checker support only, never validated at
runtime. If the contract changes, update this file by hand and re-check it against the spec --
do not assume it stayed in sync.

Every response method returns a plain ``dict`` at runtime; these types just describe its shape.
"""

from __future__ import annotations

from typing import Literal, TypedDict

PinState = Literal["high", "low"]

IdValueField = float | str | None
"""digital*/interrupt -> "high"/"low"; analogInput -> a number; textVariable -> a string;
math2xId -> a number. `None` when nothing has been read yet."""

IdTypeReported = Literal[
    "digitalInput", "digitalOutput", "digitalPullup", "analogInput", "interrupt",
    "momentaryOutput", "delayedOutput", "textVariable", "math2xId", "unsupported",
]


class Capability(TypedDict, total=False):
    """What an ID *means*, as authored on the product template -- the layer that lets a caller
    present it as a garage door rather than pin 11. Absent (``None`` on the ID) where the author
    hasn't given it one."""

    type: str | None
    """One of Switch, Light, Lock, GarageDoor, Cover, ContactSensor, MotionSensor,
    TemperatureSensor, AnalogGauge -- or a future value this SDK hasn't been told about yet."""
    names: list[str]
    """Friendly names/spoken keywords, most-preferred first. Use names[0] as the label."""
    secure: bool
    """The platform requires a second confirmation before actuating (defaults true for Lock and
    GarageDoor)."""


class IdState(TypedDict, total=False):
    """One configured ID on a device, with its last known value. `Device.ids` items and
    `GET /devices/{serial}/ids/{idNumber}` both return this shape."""

    idNumber: int
    type: IdTypeReported
    value: IdValueField
    at: str | None
    name: str | None
    capability: Capability | None
    stateKeywords: dict[str, str] | None


class DeviceRuleSummary(TypedDict, total=False):
    ruleNumber: int
    type: Literal["digital", "analog", "schedule"] | None
    enabled: bool


class NetworkInfo(TypedDict, total=False):
    carrier: str | None
    signal: int | None


class Location(TypedDict, total=False):
    latitude: float
    longitude: float
    at: str


class DeviceSummary(TypedDict, total=False):
    serial: str
    name: str | None
    online: bool
    lastSeenAt: str | None
    access: Literal["owner", "shared"]


class Device(DeviceSummary, total=False):
    """The full device twin -- `GET /devices/{serial}`."""

    connection: str | None
    network: NetworkInfo | None
    location: Location | None
    ids: list[IdState]
    rules: list[DeviceRuleSummary]
    at: str


class DevicePage(TypedDict, total=False):
    items: list[DeviceSummary]
    nextCursor: str | None


LogEntryKind = Literal["device", "action", "presence"]
LogEntryCategory = Literal["alert", "action", "state", "connection", None]


class LogEntryActor(TypedDict, total=False):
    userId: str
    name: str | None
    surface: Literal["app", "public", None]


class LogEntry(TypedDict, total=False):
    """One entry from `GET /devices/{serial}/log`. Fields beyond at/kind/type/category depend on
    what the entry is -- absent means not applicable, never unknown."""

    at: str
    kind: LogEntryKind
    type: str | None
    category: LogEntryCategory
    idNumber: int | None
    value: IdValueField
    ruleNumber: int | None
    telemetryId: int | None
    action: str | None
    result: Literal["added", "replaced", None]
    message: str | None
    actor: LogEntryActor | None
    firedByRule: int | None


class DeviceLogPage(TypedDict, total=False):
    serial: str
    items: list[LogEntry]
    nextCursor: str | None
    at: str


RuleReadType = Literal[
    "digital", "analog", "schedule", "device_copy", "compare_and_run", "analog_float", None
]
"""A device can run 6 rule types (3 arrive from a product template); this API can only CREATE
3 of them -- see RuleCreateType. Declaring only 3 here would make a perfectly ordinary device's
rule fail validation."""

RuleCreateType = Literal["digital", "analog", "schedule"]


# Functional TypedDict syntax, not the class form used above -- `if` is a Python keyword and
# cannot be a class-body field name, but IS a valid TypedDict key via this form. The dict you get
# back at runtime has a real "if" key; this documents it accurately instead of renaming it away.
Rule = TypedDict(
    "Rule",
    {
        "ruleNumber": int,
        "name": str | None,
        "type": RuleReadType,
        "enabled": bool,
        "runIntervalMs": int | None,
        "onTrueJumpToRule": int | None,
        "onFalseJumpToRule": int | None,
        "if": dict,
        "then": dict,
    },
    total=False,
)
"""One rule, as returned by `GET /devices/{serial}/rules` or embedded in `Device.rules`."""


class RulesPage(TypedDict, total=False):
    serial: str
    items: list[Rule]
    at: str
