# Architecture: Layered (split modules)

## Overview

Sms2mqtt is a small Python service split by layer: **mqtt_layer** (interface), **logic** (validation, no I/O), **gammu_layer** (modem I/O). The entry point **sms2mqtt.py** builds config and context, wires the layers, and runs the main loop. This keeps testing simple (logic has no MQTT/Gammu deps) and dependencies one-way.

## Decision Rationale

- **Project type:** Bridge service (GSM ↔ MQTT), single process, no database
- **Tech stack:** Python 3, paho-mqtt, python-gammu, Docker
- **Key factor:** Low domain complexity and single entry point; layered boundaries are enough

## Folder Structure

```
sms2mqtt/
├── sms2mqtt.py          # Entry point, config, wiring, main loop
├── mqtt_layer.py        # MQTT callbacks, publish/subscribe, loop_sms_receive, status
├── gammu_layer.py       # Gammu init, send_sms, fetch_sms_batch, signal/battery/network/datetime
├── logic.py             # Message validation, normalize_number, parse_log_level (no I/O)
├── Dockerfile
├── README.md
└── .ai-factory/
    ├── DESCRIPTION.md
    └── ARCHITECTURE.md
```

## Dependency Rules

- ✅ MQTT layer may call into logic and Gammu (orchestration)
- ✅ Logic may use Gammu layer for modem I/O
- ✅ Gammu layer must not depend on MQTT or business rules
- ❌ Do not put MQTT topic names or payload shapes inside Gammu code
- ❌ Do not put Gammu-specific types in MQTT callback signatures if you split modules

## Layer Responsibilities

1. **Interface (MQTT):** `on_mqtt_connect`, `on_mqtt_message`, `on_mqtt_disconnect`; subscribe/publish; JSON encode/decode and topic naming
2. **Logic:** Validate send payload (number, text); handle control actions; decide what to publish (sent/received/control_response)
3. **I/O (Gammu):** Init, SendSMS, GetNextSMS, DeleteSMS, LinkSMS, DecodeSMS; signal/battery/network/datetime

## Key Principles

1. **Config at startup:** Read env once; pass config (prefix, host, etc.) into the layers that need it, don’t read `os.getenv` deep in logic
2. **Errors to MQTT:** Publish errors to `{prefix}/sent` or `{prefix}/control_response` with a consistent JSON shape; log before publishing
3. **No business logic in Gammu calls:** Keep Gammu usage as thin I/O; validation and control flow stay in the logic layer

## Code Examples

### Interface layer: decode and delegate

```python
def on_mqtt_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload, strict=False)
    except Exception as e:
        feedback = {"result": f"error: failed to decode JSON ({e})", "payload": payload}
        client.publish(f"{mqttprefix}/sent", json.dumps(feedback, ensure_ascii=False))
        return
    if "action" in data:
        handle_control(client, data)
        return
    handle_send_sms(client, data, payload)
```

### Logic layer: validate then call I/O

```python
def handle_send_sms(client, data, raw_payload):
    number = data.get("number") or ""
    text = data.get("text")
    if not number or not isinstance(number, str):
        publish_error(client, "no number to send to", raw_payload)
        return
    if not isinstance(text, str):
        publish_error(client, "no text body to send", raw_payload)
        return
    for num in number.replace(" ", "").split(";"):
        if not num:
            continue
        try:
            send_sms_via_gammu(num, text)
            publish_sent_ok(client, num, text)
        except Exception as e:
            publish_sent_error(client, num, text, str(e))
```

### I/O layer: no MQTT or topic names

```python
def send_sms_via_gammu(number: str, text: str) -> None:
    smsinfo = {"Class": -1, "Entries": [{"ID": "ConcatenatedAutoTextLong", "Buffer": text}]}
    encoded = gammu.EncodeSMS(smsinfo)
    for message in encoded:
        message["SMSC"] = {"Location": 1}
        message["Number"] = number
        gammusm.SendSMS(message)
```

## Anti-Patterns

- ❌ Don’t put `client.publish(...)` inside Gammu helper functions; keep publish in MQTT/logic layer
- ❌ Don’t hardcode topic names in multiple places; use a single prefix variable (e.g. `mqttprefix`)
- ❌ Don’t skip publishing errors to MQTT; callers need feedback on invalid payloads or send failures
