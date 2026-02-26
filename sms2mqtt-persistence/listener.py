#!/usr/bin/env python3
"""
SMS2MQTT Persistence — MQTT listener that writes received/sent SMS to PostgreSQL.

Design:
- MQTT client runs in a background thread via loop_start(), so the network loop is
  never blocked by DB writes. This keeps the connection alive (keepalive pings) and
  avoids broker timeouts that caused repeated "Unspecified error" disconnects.
- on_message only enqueues (topic, payload); a single main thread drains the queue
  and writes to the DB. Bursts of messages are buffered in the queue so slow DB
  writes do not block the MQTT loop or cause message loss.
"""

import logging
import queue
import sys
import threading
import time

import certifi
import paho.mqtt.client as mqtt
from config import load_config, mask_password
from db import ensure_schema, get_connection
from persist import insert_sms, payload_to_row

# Max messages to buffer when DB is slow; drop oldest would require a different queue policy.
MQ_MAX_SIZE = 10_000


def parse_log_level(value: str) -> int:
    """Map LOG_LEVEL env to logging constant; invalid values fall back to INFO."""
    if not value:
        return logging.INFO
    v = str(value).strip().upper()
    return {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }.get(v, logging.INFO)


def setup_mqtt_ssl(client: mqtt.Client, use_tls: bool) -> None:
    if use_tls:
        client.tls_set(ca_certs=certifi.where())
        logging.getLogger(__name__).info("SSL/TLS configured for MQTT")
    else:
        logging.getLogger(__name__).debug("MQTT connecting without TLS")


def run_mqtt_loop(config: dict, logger: logging.Logger) -> None:
    """Run MQTT in a background thread (loop_start), main thread drains queue and writes to DB."""
    mq = config["mqtt"]
    state = {"connected": False, "lock": threading.Lock()}
    msg_queue: queue.Queue[tuple[str, bytes]] = queue.Queue(maxsize=MQ_MAX_SIZE)

    def on_connect(
        client: mqtt.Client, userdata: dict, flags: dict, reason_code, properties
    ) -> None:
        """Callback for MQTT connect (paho-mqtt CallbackAPIVersion.VERSION2)."""
        with state["lock"]:
            state["connected"] = True
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            logger.info("Connected to MQTT host")
            prefix = mq["prefix"]
            client.subscribe(f"{prefix}/received")
            client.subscribe(f"{prefix}/sent")
            logger.debug("Subscribed to %s/received and %s/sent", prefix, prefix)
        else:
            logger.error("MQTT connect failed, rc=%s", reason_code)

    def on_disconnect(
        client: mqtt.Client, userdata: dict, disconnect_flags, reason_code, properties
    ) -> None:
        """Callback for MQTT disconnect (paho-mqtt CallbackAPIVersion.VERSION2)."""
        with state["lock"]:
            state["connected"] = False
        logger.info("Disconnected from MQTT host")
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            logger.warning("Unexpected disconnect, reason code: %s", reason_code)

    def on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
        """Enqueue only; do not block with DB I/O so the network thread stays responsive."""
        try:
            msg_queue.put_nowait((msg.topic, msg.payload))
        except queue.Full:
            logger.error("Message queue full, dropping topic=%s", msg.topic)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        mq.get("client_id") or "sms2mqtt-persistence",
    )
    if mq.get("user") or mq.get("password"):
        client.username_pw_set(mq.get("user") or "", mq.get("password") or "")
    setup_mqtt_ssl(client, mq.get("use_tls", False))
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.user_data_set(state)

    keepalive_sec = 60
    try:
        client.connect(mq["host"], mq["port"], keepalive=keepalive_sec)
    except Exception as e:
        logger.error("MQTT connection failed: %s", e)
        raise

    with state["lock"]:
        state["connected"] = True
    client.loop_start()

    reconnect_delay_sec = 2.0
    last_reconnect_attempt = 0.0
    reconnect_attempt = 0
    db_config = config["db"]
    device_id = mq["prefix"]

    try:
        while True:
            # Reconnect if the background loop detected a disconnect.
            with state["lock"]:
                connected = state["connected"]
            if not connected:
                now = time.time()
                if now - last_reconnect_attempt >= reconnect_delay_sec:
                    reconnect_attempt += 1
                    last_reconnect_attempt = now
                    logger.debug("Reconnecting to MQTT (attempt %d)", reconnect_attempt)
                    try:
                        client.reconnect()
                        logger.info("Reconnected to MQTT")
                        reconnect_delay_sec = 2.0
                        reconnect_attempt = 0
                    except Exception as e:
                        logger.warning("MQTT reconnect failed: %s", e)
                        reconnect_delay_sec = min(reconnect_delay_sec * 2, 30.0)
                time.sleep(0.5)
                continue

            # Drain queue: write to DB (main thread only; does not block MQTT loop).
            try:
                topic, payload = msg_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            row = payload_to_row(topic, payload, device_id)
            if row is None:
                logger.error(
                    "Parse failed for topic=%s payload=%s",
                    topic,
                    payload[:200] if len(payload) < 200 else payload[:200] + b"...",
                )
                continue
            try:
                conn = get_connection(db_config)
                try:
                    row_id = insert_sms(conn, row)
                    if row_id is not None:
                        logger.debug(
                            "Persisted %s id=%s remote_number=%s",
                            row["direction"],
                            row_id,
                            row["remote_number"],
                        )
                    else:
                        logger.error(
                            "Insert failed for topic=%s remote_number=%s",
                            topic,
                            row.get("remote_number"),
                        )
                finally:
                    conn.close()
            except Exception as e:
                logger.error("DB error on message topic=%s: %s", topic, e)
    finally:
        client.loop_stop()


def main() -> None:
    try:
        config = load_config()
    except SystemExit as e:
        print(e.args[0], file=sys.stderr)
        sys.exit(1)

    log_level = parse_log_level(config["log_level"])
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.info("sms2mqtt-persistence starting, log_level=%s", logging.getLevelName(log_level))

    mq = config["mqtt"]
    db = config["db"]
    logger.debug(
        "config: MQTT host=%s port=%s prefix=%s user=%s password=%s use_tls=%s client_id=%s",
        mq["host"],
        mq["port"],
        mq["prefix"],
        mq["user"] or "(none)",
        mask_password(mq["password"]),
        mq["use_tls"],
        mq["client_id"],
    )
    logger.debug(
        "config: DB host=%s port=%s database=%s user=%s password=%s",
        db["host"],
        db["port"],
        db["database"],
        db["user"],
        mask_password(db["password"]),
    )
    logger.info("Config loaded")

    try:
        conn = get_connection(config["db"])
        conn.close()
    except Exception as e:
        logger.error("DB connection failed at startup: %s", e)
        sys.exit(1)

    ensure_schema(config["db"])

    run_mqtt_loop(config, logger)


if __name__ == "__main__":
    main()
