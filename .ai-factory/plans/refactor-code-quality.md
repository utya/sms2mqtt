# Implementation Plan: Code quality (optional)

Branch: refactor/code-quality  
Created: 2025-02-24

## Settings
- **Testing:** yes — extend tests for validation (normalization, length limits); keep existing tests passing
- **Logging:** level from env (`LOG_LEVEL`); all exceptions log at **ERROR**; **DEBUG** maximum detail; **INFO** for key events only
- **Docs:** no — do not update README or other docs in this refactor

## Goals
- Reduce global state: config and runtime in one place, pass into callbacks/functions (per `.ai-factory/ARCHITECTURE.md` and RECOMMENDATIONS-PLAN §7.1).
- Optional: phone number normalization (digits + `+`), configurable text length limit.

## Commit Plan
- **Commit 1** (after tasks 1–2): `refactor: add config and runtime context, wire from main`
- **Commit 2** (after tasks 3–4): `refactor: remove globals from callbacks and loop/status functions`
- **Commit 3** (after tasks 5–6): `feat: optional number normalization and text length limit + tests`

---

## Tasks

### Phase 1: Config and context

- [x] **Task 1: Introduce config and runtime context**
  - Build a **config** object from env at startup (single place in `if __name__ == "__main__"`): prefix, host, port, client_id, user, password, use_tls, device, pincode, gammuoption, moreinfo, heartbeat, etc. Use a dataclass or a simple namespace (e.g. `types.SimpleNamespace`); no behaviour, only data.
  - Introduce a **runtime context** object holding: `client`, `gammusm`, `config`, and connection state (`mqtt_connected`, `reconnect_delay_sec`, `last_reconnect_attempt`), plus state for stuck SMS (`stuck_sms_detected`, `last_stuck_sms`) and status caches (`old_signal_info`, `old_battery_charge`, `old_network_info`, `old_time`). All previously global mutable state lives here.
  - File: `sms2mqtt.py`.
  - Logging: DEBUG at context creation (list config keys, no secrets); INFO once "Context initialized". Exceptions during init: ERROR with full context.

- [x] **Task 2: Wire context via MQTT userdata and main loop**
  - Set `client.user_data_set(ctx)` before `client.connect(...)` so that every callback receives `(client, userdata, ...)` with `userdata` being the context.
  - In main loop, use `ctx` instead of globals for reconnect logic and for passing into `loop_sms_receive`, `get_signal_info`, etc. (signatures will be updated in Task 4.)
  - File: `sms2mqtt.py`.
  - Logging: DEBUG on reconnect attempt with attempt number; INFO on reconnect success. Exceptions: ERROR.

### Phase 2: Remove globals from callbacks and helpers

- [x] **Task 3: Refactor MQTT callbacks to use userdata (context)**
  - `on_mqtt_connect(client, userdata, flags, rc)`: use `userdata.prefix` (or `userdata.config.prefix`), no global `mqttprefix`; set `userdata.mqtt_connected = True`, reset backoff on context.
  - `on_mqtt_disconnect(client, userdata, rc)`: set `userdata.mqtt_connected = False`; log; no globals.
  - `on_mqtt_message(client, userdata, msg)`: get prefix, client, gammusm, and stuck-SMS state from `userdata`; publish using `userdata.config` for prefix; update `userdata.last_stuck_sms` / `userdata.stuck_sms_detected` instead of globals. Ensure no reference to global `mqttprefix`, `client`, `gammusm`, `last_stuck_sms`, `stuck_sms_detected`.
  - File: `sms2mqtt.py`.
  - Logging: DEBUG for each message received (topic, payload length); INFO for subscribe; all exceptions ERROR with message and context.

- [x] **Task 4: Refactor loop_sms_receive and status functions to take context**
  - `loop_sms_receive(ctx)`: receive context; use `ctx.client`, `ctx.gammusm`, `ctx.config` (prefix), and update `ctx.stuck_sms_detected`, `ctx.last_stuck_sms`. Remove global references.
  - `get_signal_info(ctx)`, `get_battery_charge(ctx)`, `get_network_info(ctx)`, `get_datetime(ctx)`: take context; read/write `ctx.old_signal_info`, etc.; use `ctx.client` and `ctx.config` for publish and prefix.
  - `shutdown`: take context (or set up so signal handler has access to ctx) and use `ctx.client` for disconnect/publish.
  - Main loop and any other call sites must pass `ctx` into these functions.
  - File: `sms2mqtt.py`.
  - Logging: DEBUG at start of each status fetch; INFO when value changed and published; exceptions ERROR.

### Phase 3: Optional validation improvements and tests

- [x] **Task 5: Optional — number normalization and text length limit**
  - **Number normalization:** Add a small pure function `normalize_number(raw: str) -> str`: keep only digits and leading `+`; optionally strip spaces and collapse multiple `+` to one at start. Call it from `validate_send_payload` (or apply to parsed number before return) so that returned `number` is normalized. For semicolon-separated numbers, normalize each segment. Document behaviour in docstring (e.g. "E.164-like: digits and optional leading +").
  - **Text length limit:** Add optional max length (env `SMS_MAX_TEXT_LENGTH` or constant, e.g. 1600). In `validate_send_payload`, if text exceeds limit, return error_feedback with a clear message (e.g. "text exceeds max length N"). Keep validation pure (no I/O, no globals).
  - File: `sms2mqtt.py`.
  - Logging: DEBUG when normalizing number (input → output); when rejecting due to length, log at INFO or WARNING with length and limit. Exceptions in validation: ERROR.

- [x] **Task 6: Tests for normalization and length limit**
  - Extend `tests/test_send_validation.py`: tests for `validate_send_payload` with number normalization (e.g. spaces, dashes removed; leading + kept; multiple numbers normalized).
  - Add tests for text length: valid at limit, over limit returns error with "max length" or similar in result; optional test for `SMS_MAX_TEXT_LENGTH` if read from env (via patch).
  - Ensure no regressions: existing tests still pass. Run test suite after changes.
  - File: `tests/test_send_validation.py` (and possibly `sms2mqtt.py` if env is used).
  - No new logging in tests.

---

## Summary
- **Tasks 1–2:** Config + context, wired from main and via userdata.
- **Tasks 3–4:** All callbacks and loop/status functions use context only; no globals for config or runtime state.
- **Tasks 5–6:** Optional normalization and length limit + tests.

After implementation, run the full test suite and manual smoke test (send/receive) if possible.
