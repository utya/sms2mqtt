"""Unit tests for payload parsing and row mapping. No MQTT or real DB."""

import json

# Import from parent package
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persist import parse_received, parse_sent, payload_to_row


def test_parse_received_valid():
    payload = {"datetime": "2025-02-24 12:00:00", "number": "+79001234567", "text": "Hello"}
    row = parse_received(payload)
    assert row is not None
    assert row["direction"] == "received"
    assert row["remote_number"] == "+79001234567"
    assert row["text"] == "Hello"
    assert row["mqtt_datetime"] == "2025-02-24 12:00:00"
    assert row["result"] is None


def test_parse_received_missing_number():
    payload = {"datetime": "2025-02-24 12:00:00", "text": "Hello"}
    assert parse_received(payload) is None


def test_parse_received_number_not_string():
    payload = {"number": 79001234567, "text": "Hi"}
    assert parse_received(payload) is None


def test_parse_sent_success():
    payload = {
        "result": "success",
        "datetime": "2025-02-24 12:01:00",
        "number": "+79007654321",
        "text": "Sent ok",
    }
    row = parse_sent(payload)
    assert row is not None
    assert row["direction"] == "sent"
    assert row["remote_number"] == "+79007654321"
    assert row["result"] == "success"


def test_parse_sent_error():
    payload = {
        "result": "error : send failed",
        "datetime": "2025-02-24 12:02:00",
        "number": "+79001111111",
        "text": "Fail",
    }
    row = parse_sent(payload)
    assert row is not None
    assert row["direction"] == "sent"
    assert row["result"] == "error : send failed"


def test_parse_sent_missing_number():
    payload = {"result": "success", "text": "No number"}
    assert parse_sent(payload) is None


def test_payload_to_row_received_with_device_id():
    topic = "mybridge/received"
    payload_bytes = json.dumps(
        {"datetime": "2025-02-24 12:00:00", "number": "+7999", "text": "Hi"}
    ).encode("utf-8")
    row = payload_to_row(topic, payload_bytes, device_id="mybridge")
    assert row is not None
    assert row["direction"] == "received"
    assert row["remote_number"] == "+7999"
    assert row["device_id"] == "mybridge"


def test_payload_to_row_sent_with_device_id():
    topic = "sms2mqtt/sent"
    payload_bytes = json.dumps(
        {
            "result": "success",
            "datetime": "2025-02-24 12:00:00",
            "number": "+7888",
            "text": "Ok",
        }
    ).encode("utf-8")
    row = payload_to_row(topic, payload_bytes, device_id="sms2mqtt")
    assert row is not None
    assert row["direction"] == "sent"
    assert row["remote_number"] == "+7888"
    assert row["device_id"] == "sms2mqtt"


def test_payload_to_row_invalid_json():
    topic = "sms2mqtt/received"
    payload_bytes = b"not json"
    assert payload_to_row(topic, payload_bytes, device_id="x") is None


def test_payload_to_row_invalid_utf8():
    topic = "sms2mqtt/received"
    payload_bytes = b"\xff\xfe"
    assert payload_to_row(topic, payload_bytes, device_id="x") is None


def test_payload_to_row_unknown_topic():
    topic = "sms2mqtt/other"
    payload_bytes = json.dumps({"number": "+7", "text": "x"}).encode("utf-8")
    assert payload_to_row(topic, payload_bytes, device_id="x") is None


def test_payload_to_row_missing_fields_returns_none():
    topic = "sms2mqtt/received"
    payload_bytes = json.dumps({}).encode("utf-8")
    assert payload_to_row(topic, payload_bytes, device_id="x") is None
