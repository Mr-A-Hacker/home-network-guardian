"""House-level API key.

The router is the single agent for the ENTIRE house. One key identifies the
home on your website. Generated once, stored locally, sent on every report.
"""
import secrets
import string
import hashlib
import json
import os
import time


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
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    api_key = generate_key()
    record = {
        "api_key": api_key,
        "fingerprint": key_fingerprint(api_key),
        "house_id": secrets.token_hex(8),
        "created_at": int(time.time()),
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    os.chmod(path, 0o600)
    return record


if __name__ == "__main__":
    rec = load_or_create_key()
    print("House ID :", rec["house_id"])
    print("API Key  :", rec["api_key"])
    print("Fingerprint:", rec["fingerprint"])
    print("\nPaste this ONE API Key into your website for the whole house.")
