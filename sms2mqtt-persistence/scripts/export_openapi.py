#!/usr/bin/env python3
"""
Export OpenAPI schema from the persistence API to a JSON file.
Run from repo root: uv run --project sms2mqtt-persistence python sms2mqtt-persistence/scripts/export_openapi.py
Or from sms2mqtt-persistence: uv run python scripts/export_openapi.py
"""
import json
import os
import sys

# Add parent so api module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import create_app

# Minimal config for schema generation (no env required)
config = {
    "db": {"host": "", "port": 5432, "database": "", "user": "", "password": ""},
    "firebase_credentials": None,
}
app = create_app(config)
spec = app.openapi()

# Write to docs/openapi.json (repo root)
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out_path = os.path.join(repo_root, "docs", "openapi.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=2, ensure_ascii=False)
print("Written:", out_path)
