#!/usr/bin/env python3
"""
SMS2MQTT Persistence — MQTT listener that writes received/sent SMS to PostgreSQL.
Connects to MQTT, subscribes to {prefix}/received and {prefix}/sent, persists to DB (Task 5).
"""

import logging
import sys
import time

import certifi
import paho.mqtt.client as mqtt
from config import load_config, mask_password
from db import get_connection
from persist import insert_sms, payload_to_row


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
    """Create MQTT client, connect, subscribe, run loop with reconnect backoff."""
    mq = config["mqtt"]
    state = {"connected": False}

    def on_connect(
        client: mqtt.Client, userdata: dict, flags: dict, reason_code, properties
    ) -> None:
        """Callback for MQTT connect (paho-mqtt CallbackAPIVersion.VERSION2)."""
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
        state["connected"] = False
        logger.info("Disconnected from MQTT host")
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            logger.warning("Unexpected disconnect, reason code: %s", reason_code)

    def on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage) -> None:
        device_id = mq["prefix"]
        row = payload_to_row(msg.topic, msg.payload, device_id)
        if row is None:
            logger.error(
                "Parse failed for topic=%s payload=%s",
                msg.topic,
                msg.payload[:200] if len(msg.payload) < 200 else msg.payload[:200] + b"...",
            )
            return
        db_config = config["db"]
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
                        msg.topic,
                        row.get("remote_number"),
                    )
            finally:
                conn.close()
        except Exception as e:
            logger.error("DB error on message topic=%s: %s", msg.topic, e)

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

    try:
        client.connect(mq["host"], mq["port"])
    except Exception as e:
        logger.error("MQTT connection failed: %s", e)
        raise

    state["connected"] = True
    reconnect_delay_sec = 2.0
    last_reconnect_attempt = 0.0
    reconnect_attempt = 0

    while True:
        time.sleep(1)
        if not state["connected"]:
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
        client.loop()


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

    run_mqtt_loop(config, logger)


if __name__ == "__main__":
    main()
