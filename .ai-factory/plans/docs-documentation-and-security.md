# Implementation Plan: Documentation and security

Branch: docs/documentation-and-security
Created: 2025-02-24

## Settings
- Testing: no
- Logging: standard (no new code; existing logging unchanged)
- Docs: yes (this plan delivers README and security documentation)

## Goal
Complete ROADMAP milestone "Documentation and security": in README document all environment variables (including USETLS, DEVICE, DEVMODE), all MQTT topics (control, control_response, stuck_status), add TLS and secrets recommendations, and a note on ACL for the control topic.

## Tasks

### Phase 1: Environment variables

- [x] **Task 1: Document missing environment variables in README**
  - **File:** `README.md`
  - In the "Environment variables" (or "Configure" / env) section, add or complete entries for:
    - **DEVICE**: Path to GSM modem device. Default: `/dev/mobile`. Example: `/dev/ttyUSB0` or `/dev/serial/by-id/...`. Note that inside Docker the host device is often mapped to `/dev/mobile`.
    - **USETLS**: Enable MQTT over TLS. Values: `true`, `1`, `yes` (case-insensitive). Default: off. When enabled, the client uses system CA bundle (certifi). For TLS, typically use port 8883.
    - **DEVMODE**: If set to `1`, the process waits for Enter before starting the main loop (useful for attaching a debugger). Default: `0`.
    - **SMS_MAX_TEXT_LENGTH**: Optional. Maximum length of SMS text in send payload; if exceeded, validation returns an error. Omit or leave empty for no limit.
  - Keep existing entries (PIN, GAMMUOPTION, MOREINFO, HEARTBEAT, HOST, PORT, PREFIX, CLIENTID, USER, PASSWORD, LOG_LEVEL) consistent in style.
  - **Deliverable:** README lists every env var used by `sms2mqtt.py` with purpose and default where applicable.

### Phase 2: MQTT topics

- [x] **Task 2: Document control, control_response, and stuck_status in README**
  - **File:** `README.md`
  - In "Other topics" (or a dedicated "MQTT topics" section), add:
    - **{prefix}/control** (subscribe): Control channel. JSON payload with `"action": "delete_stuck_sms"` to delete SMS stuck in incomplete multipart state. Other actions are ignored (logged as unknown).
    - **{prefix}/control_response** (publish): Response to control commands. Example: `{"result": "deleted", "deleted_locations": [1, 2]}` or `{"result": "nothing", "deleted_locations": []}`.
    - **{prefix}/stuck_status** (publish): Published when an incomplete multipart SMS is detected. Payload: `status`, `received_parts`, `expected_parts`, `number`, `datetime`, `locations`. Clients can use this to trigger cleanup via `control` with `delete_stuck_sms`.
  - Optionally add a short "Topics summary" table: topic name, direction (in/out), purpose.
  - **Deliverable:** All topics used in `mqtt_layer.py` (send, sent, received, connected, signal, control, control_response, stuck_status, battery, network, datetime) are listed with purpose and payload format where relevant.

### Phase 3: Security

- [x] **Task 3: Add Security section to README (TLS, secrets, ACL)**
  - **File:** `README.md`
  - Add or expand a **Security** section with:
    - **TLS:** Recommend using `USETLS=true` and port 8883 for production. Mention that the app uses the default CA bundle (certifi); for custom CAs or client certs, code changes would be needed.
    - **Secrets:** Do not put real SIM PIN or MQTT passwords in examples or in files under version control. Use environment variables, Docker secrets, or `.env` files that are not committed. The existing "Security" note in "How-to / Install" can be kept and referenced from this section.
    - **ACL:** Authorization to send SMS or run control actions is determined only by MQTT broker ACL (who can publish to `{prefix}/send` and `{prefix}/control`). Recommend restricting publish access to these topics to trusted clients; document that there is no application-level auth beyond MQTT.
  - **Deliverable:** README gives clear recommendations for TLS, handling secrets, and broker ACL for control/send topics.

### Phase 4: Consistency and roadmap

- [x] **Task 4: Update ROADMAP and optional AGENTS.md**
  - **Files:** `.ai-factory/ROADMAP.md`, optionally `AGENTS.md`
  - In ROADMAP.md: mark "Documentation and security" as completed (e.g. change `- [ ]` to `- [x]` and add completion date to the Completed table).
  - In AGENTS.md: if the "Documentation" table or project structure mentions README scope, ensure it reflects "env vars, topics, security (TLS, secrets, ACL)".
  - **Deliverable:** Roadmap and AI context files are consistent with the new documentation.

---

## Verification
- README contains every env var from `build_config_from_env()` (DEVICE, PIN, GAMMUOPTION, MOREINFO, HEARTBEAT, PREFIX, HOST, PORT, CLIENTID, USER, PASSWORD, USETLS, SMS_MAX_TEXT_LENGTH, LOG_LEVEL) and DEVMODE from main.
- README documents control, control_response, stuck_status and matches behaviour in `mqtt_layer.py`.
- Security section covers TLS, secrets, and ACL for control/send.
- ROADMAP shows the milestone as done.
