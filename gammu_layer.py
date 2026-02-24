"""
Gammu I/O layer: modem init, send/receive SMS, signal/battery/network/datetime.
No MQTT, no topic names, no business logic — thin wrapper over gammu.
"""

import gammu


def write_gammurc(path: str, device: str, gammuoption: str = "") -> None:
    """Write Gammu config file to path."""
    with open(path, "w") as f:
        f.write(f"""
[gammu]
device = {device}
connection = at
{gammuoption}
""")


def init_state_machine(gammurc_path: str, pincode: str = None) -> gammu.StateMachine:
    """Init Gammu state machine; enter PIN if required. Returns ready StateMachine."""
    sm = gammu.StateMachine()
    sm.ReadConfig(Filename=gammurc_path)
    sm.Init()
    if sm.GetSecurityStatus() == "PIN" and pincode:
        sm.EnterSecurityCode("PIN", pincode)
    return sm


def send_sms(sm: gammu.StateMachine, number: str, text: str) -> None:
    """Encode and send one SMS. No MQTT."""
    smsinfo = {
        "Class": -1,
        "Entries": [{"ID": "ConcatenatedAutoTextLong", "Buffer": text}],
    }
    encoded = gammu.EncodeSMS(smsinfo)
    for message in encoded:
        message["SMSC"] = {"Location": 1}
        message["Number"] = number
        sm.SendSMS(message)


def fetch_sms_batch(sm: gammu.StateMachine) -> list:
    """Fetch all pending SMS from modem. Returns list of raw SMS dicts (GetNextSMS results)."""
    allsms = []
    start = True
    while True:
        try:
            if start:
                sms = sm.GetNextSMS(Folder=0, Start=True)
                start = False
            else:
                sms = sm.GetNextSMS(Folder=0, Location=sms[0]["Location"])
            allsms.append(sms)
        except gammu.ERR_EMPTY:
            break
    return allsms


def link_sms(allsms: list) -> list:
    """Link SMS parts into concatenated messages. Pure gammu helper."""
    return gammu.LinkSMS(allsms)


def decode_sms(sms: list) -> dict:
    """Decode multipart SMS. Pure gammu helper."""
    return gammu.DecodeSMS(sms)


def delete_sms(sm: gammu.StateMachine, folder: int, location: int) -> None:
    """Delete one SMS at folder/location."""
    sm.DeleteSMS(Folder=folder, Location=location)


def get_signal_quality(sm: gammu.StateMachine) -> dict:
    """Return signal quality dict from modem."""
    return sm.GetSignalQuality()


def get_battery_charge(sm: gammu.StateMachine) -> dict:
    """Return battery charge dict from modem."""
    return sm.GetBatteryCharge()


def get_network_info(sm: gammu.StateMachine) -> dict:
    """Return network info dict from modem."""
    return sm.GetNetworkInfo()


def get_datetime_ts(sm: gammu.StateMachine) -> float:
    """Return modem datetime as Unix timestamp."""
    return sm.GetDateTime().timestamp()
