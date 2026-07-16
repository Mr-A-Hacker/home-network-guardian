"""House-level API key.

The router is the single agent for the ENTIRE house. One key identifies the
home on your website. Generated once, stored locally, sent on every report.
"""
import hashlib
import json
import os
import secrets
import string
import time

from common import atomic_write_json, get_logger

log = get_logger("api_key")

KEY_FILE = "house_key.json"
KEY_PREFIX = "hng_house_"


def generate_key(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{KEY_PREFIX}{raw}"


def key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def load_or_create_key(path: str = KEY_FILE) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            log.warning("existing key file unreadable, regenerating")
    api_key = generate_key()
    record = {
        "api_key": api_key,
        "fingerprint": key_fingerprint(api_key),
        "house_id": secrets.token_hex(8),
        "created_at": int(time.time()),
    }
    try:
        atomic_write_json(path, record)
        os.chmod(path, 0o600)
    except Exception as exc:
        log.error("could not persist house key: %s", exc)
    return record


if __name__ == "__main__":
    rec = load_or_create_key()
    print("House ID :", rec["house_id"])
    print("API Key  :", rec["api_key"])
    print("Fingerprint:", rec["fingerprint"])
    print("\nPaste this ONE API Key into your website for the whole house.")
