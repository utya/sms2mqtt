"""
MQTT interface layer: callbacks, subscribe/publish, topic naming.
Orchestrates logic (validation) and gammu_layer (send/receive/status); owns JSON and topics.
"""

import json
import logging
import time

import certifi
import paho.mqtt.client as mqtt

import gammu_layer as gammu_io
from logic import validate_send_payload

# Set by main after ctx is created; used by shutdown when signal fires
_app_ctx = [None]
# When callbacks get userdata=None (e.g. tests), tests can assert _compat_mqtt_connected[0]
_compat_mqtt_connected = [True]

ALLOWED_ACTIONS = ("delete_stuck_sms",)


def setup_mqtt_ssl(client: mqtt.Client, use_tls: bool = False) -> None:
    """Configure TLS on MQTT client if use_tls."""
    try:
        if use_tls:
            client.tls_set(ca_certs=certifi.where())
            logging.info("SSL/TLS configured successfully")
        else:
            logging.info("Connecting without SSL/TLS")
    except Exception as e:
        logging.error("Error configuring SSL/TLS: %s", e)
        raise SystemExit(1)


def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    """Callback for MQTT connect (paho-mqtt CallbackAPIVersion.VERSION2)."""
    prefix = userdata.config.prefix if userdata else "sms2mqtt"
    if userdata:
        userdata.mqtt_connected = True
        userdata.reconnect_delay_sec = 2.0
    else:
        _compat_mqtt_connected[0] = True
    logging.info("Connected to MQTT host")
    client.publish(f"{prefix}/connected", "1", 0, True)
    client.subscribe(f"{prefix}/send")
    client.subscribe(f"{prefix}/control")
    logging.info("Subscribed to %s/send and %s/control", prefix, prefix)


def on_mqtt_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Callback for MQTT disconnect (paho-mqtt CallbackAPIVersion.VERSION2)."""
    if userdata:
        userdata.mqtt_connected = False
    else:
        _compat_mqtt_connected[0] = False
    logging.info("Disconnected from MQTT host")
    rc = getattr(reason_code, "value", reason_code)
    if rc != 0:
        logging.warning("Unexpected disconnect, reason code: %s", reason_code)


def on_mqtt_message(client, userdata, msg):
    ctx = userdata
    if not ctx:
        logging.error("on_mqtt_message: no userdata (context)")
        return
    prefix = ctx.config.prefix
    gsm = ctx.gammusm

    try:
        logging.debug(
            "MQTT received on %s payload_len=%s", msg.topic, len(msg.payload) if msg.payload else 0
        )
        logging.info("MQTT message on topic: %s", msg.topic)
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload, strict=False)
    except Exception as e:
        try:
            safe_payload = (
                msg.payload.decode("utf-8", errors="replace")
                if isinstance(msg.payload, bytes)
                else str(msg.payload)
            )
        except Exception:
            safe_payload = repr(msg.payload)
        feedback = {"result": "error : failed to decode JSON", "payload": safe_payload}
        client.publish(f"{prefix}/sent", json.dumps(feedback, ensure_ascii=False))
        logging.error("failed to decode JSON (%s), payload: %s", e, safe_payload)
        return

    if "action" in data:
        action = data["action"] if isinstance(data.get("action"), str) else None
        if action in ALLOWED_ACTIONS and action == "delete_stuck_sms":
            deleted = []
            for s in ctx.last_stuck_sms:
                try:
                    gammu_io.delete_sms(gsm, 0, s["Location"])
                    deleted.append(s["Location"])
                except Exception as e:
                    logging.error("Failed to delete stuck SMS at %s: %s", s["Location"], e)
            result = {"result": "deleted" if deleted else "nothing", "deleted_locations": deleted}
            client.publish(f"{prefix}/control_response", json.dumps(result))
            ctx.last_stuck_sms.clear()
            ctx.stuck_sms_detected = False
            logging.info("Stuck SMS deleted: %s", deleted)
        else:
            logging.warning("Unknown or invalid action received: %s", action)
        return

    max_len = getattr(ctx.config, "max_text_length", None)
    number, text, error_feedback = validate_send_payload(msg.payload, max_text_length=max_len)
    if error_feedback is not None:
        client.publish(f"{prefix}/sent", json.dumps(error_feedback, ensure_ascii=False))
        logging.error("%s", error_feedback.get("result", "validation error"))
        return

    for num in number.split(";"):
        num = num.replace(" ", "").strip()
        if not num:
            continue
        try:
            logging.info("Sending SMS to %s", num)
            gammu_io.send_sms(gsm, num, text)
            feedback = {
                "result": "success",
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "number": num,
                "text": text,
            }
            client.publish(f"{prefix}/sent", json.dumps(feedback, ensure_ascii=False))
            logging.info("SMS sent to %s", num)
        except Exception as e:
            logging.error("Send SMS failed for %s: %s", num, e)
            feedback = {
                "result": "error : send failed",
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "number": num,
                "text": text,
            }
            client.publish(f"{prefix}/sent", json.dumps(feedback, ensure_ascii=False))


def loop_sms_receive(ctx) -> None:
    """Fetch SMS from modem, publish to MQTT, update stuck state."""
    logging.debug("loop_sms_receive start")
    ctx.stuck_sms_detected = False
    ctx.last_stuck_sms.clear()

    allsms = gammu_io.fetch_sms_batch(ctx.gammusm)
    if not allsms:
        return

    alllinkedsms = gammu_io.link_sms(allsms)
    prefix = ctx.config.prefix

    for sms in alllinkedsms:
        if sms[0]["UDH"]["Type"] == "NoUDH":
            message = {
                "datetime": str(sms[0]["DateTime"]),
                "number": sms[0]["Number"],
                "text": sms[0]["Text"],
            }
            payload = json.dumps(message, ensure_ascii=False)
            ctx.client.publish(f"{prefix}/received", payload)
            logging.info("Received SMS: %s", payload)
            try:
                gammu_io.delete_sms(ctx.gammusm, 0, sms[0]["Location"])
            except Exception as e:
                logging.error("Unable to delete SMS: %s", e)
        elif sms[0]["UDH"]["AllParts"] != -1:
            if len(sms) == sms[0]["UDH"]["AllParts"]:
                decodedsms = gammu_io.decode_sms(sms)
                message = {
                    "datetime": str(sms[0]["DateTime"]),
                    "number": sms[0]["Number"],
                    "text": decodedsms["Entries"][0]["Buffer"],
                }
                payload = json.dumps(message, ensure_ascii=False)
                ctx.client.publish(f"{prefix}/received", payload)
                logging.info("Received multipart SMS: %s", payload)
                for part in sms:
                    gammu_io.delete_sms(ctx.gammusm, 0, part["Location"])
            else:
                ctx.stuck_sms_detected = True
                ctx.last_stuck_sms.extend(sms)
                logging.info(
                    "Incomplete multipart SMS (%s/%s): waiting for parts",
                    len(sms),
                    sms[0]["UDH"]["AllParts"],
                )
                ctx.client.publish(
                    f"{prefix}/stuck_status",
                    json.dumps(
                        {
                            "status": "stuck",
                            "received_parts": len(sms),
                            "expected_parts": sms[0]["UDH"]["AllParts"],
                            "number": sms[0].get("Number", "unknown"),
                            "datetime": str(sms[0].get("DateTime", "")),
                            "locations": [s["Location"] for s in sms],
                        }
                    ),
                )
                continue
        else:
            logging.info("Unsupported SMS type")
            try:
                gammu_io.delete_sms(ctx.gammusm, 0, sms[0]["Location"])
            except Exception as e:
                logging.error("Unable to delete unsupported SMS: %s", e)


# Minimum interval (seconds) between signal/battery/network publishes to avoid log spam
STATUS_PUBLISH_INTERVAL_SEC = 15


def get_signal_info(ctx) -> None:
    try:
        signal_info = gammu_io.get_signal_quality(ctx.gammusm)
        if signal_info == ctx.old_signal_info:
            return
        last = getattr(ctx, "last_signal_publish_time", 0)
        now = time.time()
        if last == 0 or (now - last) >= STATUS_PUBLISH_INTERVAL_SEC:
            ctx.client.publish(f"{ctx.config.prefix}/signal", json.dumps(signal_info))
            ctx.old_signal_info = signal_info
            ctx.last_signal_publish_time = now
            logging.info("Signal info published")
    except Exception as e:
        logging.error("Unable to check signal quality: %s", e)


def get_battery_charge(ctx) -> None:
    try:
        battery_charge = gammu_io.get_battery_charge(ctx.gammusm)
        if battery_charge != ctx.old_battery_charge:
            ctx.client.publish(f"{ctx.config.prefix}/battery", json.dumps(battery_charge))
            ctx.old_battery_charge = battery_charge
            logging.info("Battery charge published")
    except Exception as e:
        logging.error("Unable to check battery charge: %s", e)


def get_network_info(ctx) -> None:
    try:
        network_info = gammu_io.get_network_info(ctx.gammusm)
        if network_info != ctx.old_network_info:
            ctx.client.publish(f"{ctx.config.prefix}/network", json.dumps(network_info))
            ctx.old_network_info = network_info
            logging.info("Network info published")
    except Exception as e:
        logging.error("Unable to check network info: %s", e)


def get_datetime(ctx) -> None:
    try:
        now = gammu_io.get_datetime_ts(ctx.gammusm)
        if (now - ctx.old_time) > 60:
            ctx.client.publish(f"{ctx.config.prefix}/datetime", now)
            ctx.old_time = now
            logging.info("Datetime published")
    except Exception as e:
        logging.error("Unable to check datetime: %s", e)


def shutdown(signum=None, frame=None, ctx=None):
    c = ctx if ctx is not None else _app_ctx[0]
    if c:
        c.client.publish(f"{c.config.prefix}/connected", "0", 0, True)
        c.client.disconnect()
        logging.debug("Shutdown: published 0 and disconnected")
    else:
        logging.warning("Shutdown called but no context set")
