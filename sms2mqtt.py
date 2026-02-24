"""
SMS-to-MQTT bridge: entry point and wiring.
Builds config and context, initializes Gammu and MQTT, runs main loop.
"""
import logging
import os
import signal
import time
from types import SimpleNamespace

import gammu
import paho.mqtt.client as mqtt

from logic import parse_log_level
import gammu_layer as gammu_io
import mqtt_layer


def build_config_from_env() -> SimpleNamespace:
    """Build config from environment. No secrets in logs."""
    logging.debug("Building config from env")
    device = os.getenv("DEVICE", "/dev/mobile")
    pincode = os.getenv("PIN")
    gammuoption = os.getenv("GAMMUOPTION", "")
    moreinfo = bool(os.getenv("MOREINFO"))
    heartbeat = bool(os.getenv("HEARTBEAT"))
    prefix = os.getenv("PREFIX", "sms2mqtt")
    host = os.getenv("HOST", "localhost")
    port = int(os.getenv("PORT", "1883"))
    client_id = os.getenv("CLIENTID", "sms2mqtt")
    user = os.getenv("USER")
    password = os.getenv("PASSWORD")
    use_tls = str(os.getenv("USETLS", "")).lower() in ("true", "1", "yes")
    try:
        _max = os.getenv("SMS_MAX_TEXT_LENGTH", "").strip()
        max_text_length = int(_max) if _max else None
        if max_text_length is not None and max_text_length <= 0:
            max_text_length = None
    except ValueError:
        max_text_length = None
    config = SimpleNamespace(
        device=device,
        pincode=pincode,
        gammuoption=gammuoption,
        moreinfo=moreinfo,
        heartbeat=heartbeat,
        prefix=prefix,
        host=host,
        port=port,
        client_id=client_id,
        user=user,
        password=password,
        use_tls=use_tls,
        max_text_length=max_text_length,
    )
    logging.debug("Config keys: %s", [k for k in dir(config) if not k.startswith("_")])
    return config


def build_runtime_context(config: SimpleNamespace) -> SimpleNamespace:
    """Build runtime context. client and gammusm set by caller."""
    logging.debug("Building runtime context")
    ctx = SimpleNamespace(
        config=config,
        client=None,
        gammusm=None,
        mqtt_connected=True,
        reconnect_delay_sec=2.0,
        last_reconnect_attempt=0.0,
        stuck_sms_detected=False,
        last_stuck_sms=[],
        old_signal_info="",
        old_battery_charge="",
        old_network_info="",
        old_time=time.time(),
    )
    logging.info("Context initialized")
    return ctx


# Re-export for tests and backward compatibility
from logic import validate_send_payload, normalize_number  # noqa: E402
from mqtt_layer import on_mqtt_connect, on_mqtt_disconnect, on_mqtt_message  # noqa: E402
# For tests that call on_mqtt_disconnect(None, None, rc): mutable so they can assert mqtt_connected[0] is False
mqtt_connected = mqtt_layer._compat_mqtt_connected


if __name__ == "__main__":
    from datetime import datetime

    log_level = parse_log_level(os.getenv("LOG_LEVEL", "INFO"))
    logging.basicConfig(format="%(asctime)s: %(message)s", level=log_level, datefmt="%H:%M:%S")

    versionnumber = "1.4.6"
    logging.info("Log level: %s", logging.getLevelName(log_level))
    logging.info("===== sms2mqtt v%s =====", versionnumber)

    if os.getenv("DEVMODE", "0") == "1":
        logging.info("DEVMODE mode: press Enter to continue")
        try:
            input()
            logging.info("")
        except EOFError:
            while True:
                time.sleep(3600)

    try:
        config = build_config_from_env()
    except Exception as e:
        logging.error("Failed to build config from env: %s", e, exc_info=True)
        raise

    signal.signal(signal.SIGINT, mqtt_layer.shutdown)
    signal.signal(signal.SIGTERM, mqtt_layer.shutdown)

    gammurc_path = "/app/gammurc"
    gammu_io.write_gammurc(gammurc_path, config.device, config.gammuoption)
    gammusm = gammu_io.init_state_machine(gammurc_path, config.pincode)

    version_tuple = gammu.Version()
    logging.info(
        "Gammu runtime: v%s Python-gammu: v%s Manufacturer: %s IMEI: %s SIMIMSI: %s",
        version_tuple[0],
        version_tuple[1],
        gammusm.GetManufacturer(),
        gammusm.GetIMEI(),
        gammusm.GetSIMIMSI(),
    )
    if config.heartbeat:
        gammusm.SetDateTime(datetime.now())
    logging.info("Gammu initialized")

    client = mqtt.Client(config.client_id)
    client.username_pw_set(config.user, config.password)
    mqtt_layer.setup_mqtt_ssl(client, config.use_tls)

    ctx = build_runtime_context(config)
    ctx.client = client
    ctx.gammusm = gammusm
    mqtt_layer._app_ctx[0] = ctx

    client.user_data_set(ctx)
    client.on_connect = mqtt_layer.on_mqtt_connect
    client.on_disconnect = mqtt_layer.on_mqtt_disconnect
    client.on_message = mqtt_layer.on_mqtt_message
    client.will_set(f"{config.prefix}/connected", "0", 0, True)
    client.connect(config.host, config.port)
    ctx.mqtt_connected = True

    reconnect_attempt = 0
    while True:
        time.sleep(1)
        if not ctx.mqtt_connected:
            now = time.time()
            if now - ctx.last_reconnect_attempt >= ctx.reconnect_delay_sec:
                reconnect_attempt += 1
                ctx.last_reconnect_attempt = now
                logging.debug("Reconnecting to MQTT (attempt %d)", reconnect_attempt)
                try:
                    client.reconnect()
                    logging.info("Reconnected to MQTT")
                    reconnect_attempt = 0
                except Exception as e:
                    logging.error("MQTT reconnect failed: %s", e)
                    ctx.reconnect_delay_sec = min(ctx.reconnect_delay_sec * 2, 60.0)
            client.loop()
            continue
        mqtt_layer.loop_sms_receive(ctx)
        mqtt_layer.get_signal_info(ctx)
        if config.moreinfo:
            mqtt_layer.get_battery_charge(ctx)
            mqtt_layer.get_network_info(ctx)
        if config.heartbeat:
            mqtt_layer.get_datetime(ctx)
        client.loop()
