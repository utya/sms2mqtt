[← Configuration](configuration.md) · [Back to README](../README.md) · [Security →](security.md)

# MQTT Topics

Default prefix is `sms2mqtt`. All topics use `{prefix}/...`.

## Overview

| Topic | Direction | Description |
|-------|-----------|-------------|
| `{prefix}/send` | in | Send SMS (JSON: number, text) |
| `{prefix}/sent` | out | Send confirmation or error |
| `{prefix}/received` | out | Incoming SMS |
| `{prefix}/connected` | out | Connection status (0 or 1) |
| `{prefix}/signal` | out | Signal quality |
| `{prefix}/control` | in | Control commands (e.g. delete_stuck_sms) |
| `{prefix}/control_response` | out | Response to control commands |
| `{prefix}/stuck_status` | out | Incomplete multipart SMS detected |
| `{prefix}/battery` | out | Battery (if MOREINFO) |
| `{prefix}/network` | out | Network (if MOREINFO) |
| `{prefix}/datetime` | out | Device timestamp (if HEARTBEAT) |

## Send SMS

1. Publish to **{prefix}/send**:
   ```json
   {"number": "+33612345678", "text": "This is a test message"}
   ```
2. A confirmation is published to **{prefix}/sent**, e.g.:
   ```json
   {"result": "success", "datetime": "2021-01-23 13:00:00", "number": "+33612345678", "text": "This is a test message"}
   ```

Supported:

- Multiple numbers: semicolon-separated in `number`; one confirmation per number.
- Long messages (multi-part).
- Unicode and emoji.

## Receive SMS

Incoming SMS are published to **{prefix}/received**:

```json
{"datetime": "2021-01-23 13:30:00", "number": "+31415926535", "text": "Hi"}
```

Long SMS are supported; MMS are not.

## Status and control

- **{prefix}/connected** — `0` or `1` (broker connection).
- **{prefix}/signal** — Signal quality when it changes, e.g. `{"SignalStrength": -71, "SignalPercent": 63, "BitErrorRate": -1}`.
- **{prefix}/control** — Publish `{"action": "delete_stuck_sms"}` to delete SMS stuck in incomplete multipart state. Other actions are ignored (logged).
- **{prefix}/control_response** — Response to control, e.g. `{"result": "deleted", "deleted_locations": [1, 2]}` or `{"result": "nothing", "deleted_locations": []}`.
- **{prefix}/stuck_status** — Published when incomplete multipart SMS is detected (payload includes status, received_parts, expected_parts, number, datetime, locations). Use `delete_stuck_sms` on `{prefix}/control` to clean up.

## Optional topics (MOREINFO)

- **{prefix}/battery** — Battery and charge state when it changes.
- **{prefix}/network** — Network state when it changes.

## Optional topic (HEARTBEAT)

- **{prefix}/datetime** — Current GSM device timestamp each loop, e.g. `1634671168.531913`.

## See Also

- [Configuration](configuration.md) — PREFIX and MOREINFO/HEARTBEAT
- [Security](security.md) — who can publish to send/control
- [Persistence](persistence.md) — storing received/sent in PostgreSQL
