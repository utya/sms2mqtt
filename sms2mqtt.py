import logging
import time
from datetime import datetime
from typing import Optional, Tuple
import os
import signal
import paho.mqtt.client as mqtt
import gammu
import json
import certifi


def validate_send_payload(payload_bytes: bytes) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    """
    Parse and validate send payload. No I/O or globals — for unit testing.
    Returns (number, text, None) on success or (None, None, error_feedback) on error.
    error_feedback has keys "result" and "payload" (safe string for client).
    """
    try:
        payload_str = payload_bytes.decode("utf-8")
    except Exception as e:
        try:
            safe = payload_bytes.decode("utf-8", errors="replace")
        except Exception:
            safe = repr(payload_bytes)
        return (None, None, {"result": f"error : failed to decode JSON ({e})", "payload": safe})
    try:
        data = json.loads(payload_str, strict=False)
    except Exception as e:
        return (None, None, {"result": f"error : failed to decode JSON ({e})", "payload": payload_str})
    number = None
    text = None
    for key, value in data.items():
        if key.lower() == "number":
            number = value
        if key.lower() == "text":
            text = value
    if number is None or not isinstance(number, str) or not number.strip():
        return (None, None, {"result": "error : no number to send to", "payload": payload_str})
    if text is None or not isinstance(text, str):
        return (None, None, {"result": "error : no text body to send", "payload": payload_str})
    return (number, text, None)


def parse_log_level(value):
    """Map LOG_LEVEL env string to logging constant; invalid values fall back to INFO."""
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


stuck_sms_detected = False
last_stuck_sms = []

# MQTT connection state for reconnection with backoff
mqtt_connected = False
reconnect_delay_sec = 2.0
last_reconnect_attempt = 0.0

# callback when the broker responds to our connection request.
def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected, reconnect_delay_sec
    mqtt_connected = True
    reconnect_delay_sec = 2.0  # reset backoff on successful connect
    logging.info("Connected to MQTT host")
    client.publish(f"{mqttprefix}/connected", "1", 0, True)
    client.subscribe(f"{mqttprefix}/send")
    client.subscribe(f"{mqttprefix}/control")
    logging.info("Subscribed to %s/send and %s/control", mqttprefix, mqttprefix)

# callback when the client disconnects from the broker.
def on_mqtt_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    logging.info("Disconnected from MQTT host")
    if rc != 0:
        logging.warning("Unexpected disconnect, reason code: %s", rc)

# callback when a message has been received on a topic that the client subscribes to.
def on_mqtt_message(client, userdata, msg):
    try:
        logging.debug("MQTT received on %s: %s", msg.topic, msg.payload)
        logging.info("MQTT message on topic: %s", msg.topic)
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload, strict=False)
    except Exception as e:
        # Do not use payload here — it may be undefined if decode or json.loads failed
        try:
            safe_payload = (
                msg.payload.decode("utf-8", errors="replace")
                if isinstance(msg.payload, bytes)
                else str(msg.payload)
            )
        except Exception:
            safe_payload = repr(msg.payload)
        feedback = {"result": "error : failed to decode JSON", "payload": safe_payload}
        client.publish(f"{mqttprefix}/sent", json.dumps(feedback, ensure_ascii=False))
        logging.error("failed to decode JSON (%s), payload: %s", e, safe_payload)
        return

    # Handle action commands before processing SMS sending
    ALLOWED_ACTIONS = ("delete_stuck_sms",)
    if "action" in data:
        action = data["action"] if isinstance(data.get("action"), str) else None
        if action in ALLOWED_ACTIONS and action == "delete_stuck_sms":
            deleted = []
            for s in last_stuck_sms:
                try:
                    gammusm.DeleteSMS(Folder=0, Location=s['Location'])
                    deleted.append(s['Location'])
                except Exception as e:
                    logging.error(f"Failed to delete stuck SMS at {s['Location']}: {e}")
            result = {
                "result": "deleted" if deleted else "nothing",
                "deleted_locations": deleted
            }
            client.publish(f"{mqttprefix}/control_response", json.dumps(result))
            last_stuck_sms.clear()
            stuck_sms_detected = False
            logging.info(json.dumps(result))
            logging.info(f"Stuck SMS deleted: {deleted}")
        else:
            logging.warning("Unknown or invalid action received: %s", action)
        return

    # Send path: validate via pure function and use result
    number, text, error_feedback = validate_send_payload(msg.payload)
    if error_feedback is not None:
        client.publish(f"{mqttprefix}/sent", json.dumps(error_feedback, ensure_ascii=False))
        logging.error("%s", error_feedback.get("result", "validation error"))
        return

    for num in (number.split(";")):
        num = num.replace(' ','')
        if num == '':
            continue

        smsinfo = {
            'Class': -1,
            'Entries': [{
                'ID': 'ConcatenatedAutoTextLong',
                'Buffer' : text
            }]
        }

        try:
            logging.info(f'Sending SMS To {num} containing {text}')
            encoded = gammu.EncodeSMS(smsinfo)
            for message in encoded:
                message['SMSC'] = {'Location': 1}
                message['Number'] = num
                gammusm.SendSMS(message)
            feedback = {"result":"success", "datetime":time.strftime("%Y-%m-%d %H:%M:%S"), "number":num, "text":text}
            client.publish(f"{mqttprefix}/sent", json.dumps(feedback, ensure_ascii=False))
            logging.info(f'SMS sent to {num}')
        except Exception as e:
            logging.error("Send SMS failed for %s: %s", num, e)
            feedback = {
                "result": "error : send failed",
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "number": num,
                "text": text,
            }
            client.publish(f"{mqttprefix}/sent", json.dumps(feedback, ensure_ascii=False))

# function used to parse received sms
def loop_sms_receive():

    global stuck_sms_detected, last_stuck_sms
    stuck_sms_detected = False
    last_stuck_sms = []

    # process Received SMS
    allsms = []
    start=True
    while True:
        try:
            if start:
                sms = gammusm.GetNextSMS(Folder=0, Start=True)
                start=False
            else:
                sms = gammusm.GetNextSMS(Folder=0, Location=sms[0]['Location'])
            allsms.append(sms)
        except gammu.ERR_EMPTY as e:
            break

    if not len(allsms):
        return

    alllinkedsms=gammu.LinkSMS(allsms)

    for sms in alllinkedsms:
        if sms[0]['UDH']['Type'] == 'NoUDH':
            message = {"datetime":str(sms[0]['DateTime']), "number":sms[0]['Number'], "text":sms[0]['Text']}
            payload = json.dumps(message, ensure_ascii=False)
            client.publish(f"{mqttprefix}/received", payload)
            logging.info(payload)
            try:
                gammusm.DeleteSMS(Folder=0, Location=sms[0]['Location'])
            except Exception as e:
                logging.error(f'ERROR: Unable to delete SMS: {e}')
        elif sms[0]['UDH']['AllParts'] != -1:
            if len(sms) == sms[0]['UDH']['AllParts']:
                decodedsms = gammu.DecodeSMS(sms)
                message = {"datetime":str(sms[0]['DateTime']), "number":sms[0]['Number'], "text":decodedsms['Entries'][0]['Buffer']}
                payload = json.dumps(message, ensure_ascii=False)
                client.publish(f"{mqttprefix}/received", payload)
                logging.info(payload)
                for part in sms:
                    gammusm.DeleteSMS(Folder=0, Location=part['Location'])
            else:
                stuck_sms_detected = True
                last_stuck_sms.extend(sms)
                logging.info(f"Incomplete Multipart SMS ({len(sms)}/{sms[0]['UDH']['AllParts']}): waiting for parts")
                client.publish(f"{mqttprefix}/stuck_status", json.dumps({
                    "status": "stuck",
                    "received_parts": len(sms),
                    "expected_parts": sms[0]['UDH']['AllParts'],
                    "number": sms[0].get("Number", "unknown"),
                    "datetime": str(sms[0].get("DateTime", "")),
                    "locations": [s['Location'] for s in sms],
                }))
                continue
        else:
            logging.info('***************** Unsupported SMS type *****************')
            logging.info('===============sms=================')
            logging.info(sms)
            logging.info('===============decodedsms=================')
            decodedsms = gammu.DecodeSMS(sms)
            logging.info(decodedsms)
            logging.info('================================')
            gammusm.DeleteSMS(Folder=0, Location=sms[0]['Location'])
            
# function used to obtain signal quality        
def get_signal_info():
    global old_signal_info
    try:
        signal_info = gammusm.GetSignalQuality()
        if signal_info != old_signal_info:
            signal_payload = json.dumps(signal_info)
            client.publish(f"{mqttprefix}/signal", signal_payload)
            old_signal_info = signal_info
    except Exception as e:
        logging.error(f'ERROR: Unable to check signal quality: {e}')

old_signal_info = ""



# function used to obtain battery charge
def get_battery_charge():
    global old_battery_charge
    try:
        battery_charge = gammusm.GetBatteryCharge()
        if battery_charge != old_battery_charge:
            battery_payload = json.dumps(battery_charge)
            client.publish(f"{mqttprefix}/battery", battery_payload)
            old_battery_charge = battery_charge
    except Exception as e:
        logging.error(f'ERROR: Unable to check battery charge: {e}')

old_battery_charge = ""

# function used to obtain network info
def get_network_info():
    global old_network_info
    try:
        network_info = gammusm.GetNetworkInfo()
        if network_info != old_network_info:
            network_payload = json.dumps(network_info)
            client.publish(f"{mqttprefix}/network", network_payload)
            old_network_info = network_info
    except Exception as e:
        logging.error(f'ERROR: Unable to check network info: {e}')

old_network_info = ""

# function used to obtain datetime
def get_datetime():
    global old_time
    try:
        now = gammusm.GetDateTime().timestamp()
        if (now - old_time) > 60:
            client.publish(f"{mqttprefix}/datetime", now)
            old_time = now
    except Exception as e:
        logging.error(f'ERROR: Unable to check datetime: {e}')

old_time = time.time()

def shutdown(signum=None, frame=None):
    client.publish(f"{mqttprefix}/connected", "0", 0, True)
    client.disconnect()

def setup_mqtt_ssl(client, use_tls=False):
    try:
        if use_tls:
            client.tls_set(ca_certs=certifi.where())
            logging.info("SSL/TLS configured successfully")
        else:
            logging.info("Connecting without SSL/TLS")
    except Exception as e:
        logging.error(f"Error configuring SSL/TLS: {e}")
        exit(1)

if __name__ == "__main__":
    log_level = parse_log_level(os.getenv("LOG_LEVEL", "INFO"))
    logging.basicConfig(format="%(asctime)s: %(message)s", level=log_level, datefmt="%H:%M:%S")

    versionnumber = "1.4.6"

    logging.info("Log level: %s", logging.getLevelName(log_level))
    logging.info("===== sms2mqtt v%s =====", versionnumber)
	
    # devmode is used to start container but not the code itself, then you can connect interactively and run this script by yourself
    # docker exec -it sms2mqtt /bin/sh
    if os.getenv("DEVMODE",0) == "1":
        logging.info('DEVMODE mode : press Enter to continue')
        try:
            input()
            logging.info('')
        except EOFError as e:
            # EOFError means we're not in interactive so loop forever
            while 1:
                time.sleep(3600)


    device = os.getenv("DEVICE","/dev/mobile")
    pincode = os.getenv("PIN")
    gammuoption = os.getenv("GAMMUOPTION","")
    moreinfo = bool(os.getenv("MOREINFO"))
    heartbeat = bool(os.getenv("HEARTBEAT"))
    mqttprefix = os.getenv("PREFIX","sms2mqtt")
    mqtthost = os.getenv("HOST","localhost")
    mqttport = int(os.getenv("PORT",1883))
    mqttclientid = os.getenv("CLIENTID","sms2mqtt")
    mqttuser = os.getenv("USER")
    mqttpassword = os.getenv("PASSWORD")
    use_tls = str(os.getenv("USETLS", "")).lower() in ('true', '1', 'yes')

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    gammurcfile = open("/app/gammurc", 'w')
    gammurcfile.write(f"""
[gammu]
device = {device}
connection = at
{gammuoption}
""")
    gammurcfile.close()

    gammusm = gammu.StateMachine()
    gammusm.ReadConfig(Filename="/app/gammurc")
    gammusm.Init()

    if gammusm.GetSecurityStatus() == 'PIN':
        gammusm.EnterSecurityCode('PIN',pincode)

    versionTuple = gammu.Version()
    logging.info(f'Gammu runtime: v{versionTuple[0]}')
    logging.info(f'Python-gammu runtime: v{versionTuple[1]}')
    logging.info(f'Manufacturer: {gammusm.GetManufacturer()}')
    logging.info(f'IMEI: {gammusm.GetIMEI()}')
    logging.info(f'SIMIMSI: {gammusm.GetSIMIMSI()}')    

    if heartbeat:
        gammusm.SetDateTime(datetime.now())

    logging.info('Gammu initialized')

    client = mqtt.Client(mqttclientid)
    client.username_pw_set(mqttuser, mqttpassword)
    setup_mqtt_ssl(client,use_tls)
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    client.on_message = on_mqtt_message
    client.will_set(f"{mqttprefix}/connected", "0", 0, True)
    client.connect(mqtthost, mqttport)
    mqtt_connected = True  # assume connected until on_disconnect sets False

    reconnect_attempt = 0
    while True:
        time.sleep(1)
        # Reconnect with backoff when disconnected
        if not mqtt_connected:
            now = time.time()
            if now - last_reconnect_attempt >= reconnect_delay_sec:
                reconnect_attempt += 1
                last_reconnect_attempt = now
                logging.debug("Reconnecting to MQTT (attempt %d)", reconnect_attempt)
                try:
                    client.reconnect()
                    logging.info("Reconnected to MQTT")
                    reconnect_attempt = 0
                except Exception as e:
                    logging.warning("MQTT reconnect failed: %s", e)
                    reconnect_delay_sec = min(reconnect_delay_sec * 2, 60.0)
            client.loop()
            continue
        loop_sms_receive()
        get_signal_info()
        if moreinfo:
            get_battery_charge()
            get_network_info()
        if heartbeat:
            get_datetime()
        client.loop()
