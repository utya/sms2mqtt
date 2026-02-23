# Implementation Plan: Testing foundation

Branch: feature/testing-foundation  
Created: 2025-02-23

## Settings
- Testing: yes
- Logging: standard (INFO for key events)
- Docs: no

## Overview

Add minimal unit tests for send-path parsing and validation: JSON decode, UTF-8 handling, `number`/`text` presence and types, error feedback shape. No MQTT or Gammu in tests. Achieved by extracting a pure validation function and testing it; existing test pattern in `tests/test_config_and_mqtt.py` (unittest + mocks for gammu/paho) will be reused.

## Tasks

### Phase 1: Extract validation logic

- [x] **Task 1: Extract send payload validation into a pure function**  
  **File:** `sms2mqtt.py`  
  **Deliverable:** Add a function, e.g. `validate_send_payload(payload_bytes: bytes) -> Tuple[Optional[str], Optional[str], Optional[dict]]`. Returns `(number, text, None)` on success or `(None, None, error_feedback)` on error. Behaviour: decode payload as UTF-8 (on failure return error with safe payload representation); parse JSON with `strict=False` (on failure return error); ensure `number` is present, a non-empty string; ensure `text` is present, a string. Error feedback dict must include keys `"result"` and `"payload"` (safe string for client). Keep the function free of I/O and globals so it is easy to unit test.  
  **Logging:** No logging inside the pure function; caller (`on_mqtt_message`) keeps existing INFO/ERROR logging.  
  **Dependency:** None.

- [x] **Task 2: Refactor on_mqtt_message to use the validation function**  
  **File:** `sms2mqtt.py`  
  **Deliverable:** For the send path (when `'action' not in data`): after successful `payload.decode("utf-8")` and `json.loads(payload)`, call `validate_send_payload(msg.payload)` (or pass decoded string if you prefer a signature that accepts str; then validation handles decode internally or you keep decode in callback). If validation returns an error dict, publish it to `{prefix}/sent` and return; otherwise use returned `number` and `text` for the existing send loop. Preserve control-action handling and existing decode/JSON error handling (with safe_payload).  
  **Logging:** Keep current INFO/ERROR logs in `on_mqtt_message` (standard level).  
  **Dependency:** Task 1.

### Phase 2: Tests

- [x] **Task 3: Add unit tests for send validation**  
  **File:** `tests/test_send_validation.py` (new)  
  **Deliverable:** Use the same import pattern as `tests/test_config_and_mqtt.py`: mock `gammu` and `paho.mqtt` before importing `sms2mqtt`, then test `validate_send_payload` (or the chosen function name). Cover: (1) valid JSON with `number` and `text` (string) → success; (2) missing `number` → error dict with `result` and `payload`; (3) missing `text` → error dict; (4) `number` not a string or empty string → error; (5) `text` not a string → error; (6) invalid JSON → error; (7) non-UTF-8 payload (e.g. bytes with invalid UTF-8) → error and safe `payload` in response. Assert on structure of error dict (`"result"`, `"payload"`). Use `unittest`.  
  **Logging:** Tests do not require specific logging; implementation uses standard INFO/ERROR in the callback.  
  **Dependency:** Task 2.

## Notes

- Existing `tests/test_config_and_mqtt.py` already mocks `gammu` and `paho.mqtt`; reuse that pattern so `import sms2mqtt` works in CI without real deps.
- If `validate_send_payload` is defined to take `bytes`, the callback passes `msg.payload`; if it takes `str`, decode in callback and pass the string (and handle decode errors in callback as today).
- Semicolon-separated numbers: validation can return the raw `number` string; the existing send loop already splits by `;`. No change required for that behaviour.
