"""Shared helpers: logging, config defaults, safe file IO, versioning.

Used by every module so behaviour (log format, config fallbacks) is
consistent across the agent.
"""
import json
import logging
import os
import socket
import tempfile

AGENT_VERSION = "1.0.0"

LOG_FILE = "guardian.log"


def get_logger(name: str = "guardian") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass
    return logger


def hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def default_config() -> dict:
    """Sane defaults merged under user config (so missing keys never crash)."""
    return {
        "house": {
            "name": hostname(),
            "scan_interval_seconds": 60,
            "interface": "auto",
            "subnet": "192.168.1.0/24",
        },
        "discovery": {
            "use_nmap": True,
            "use_arp_scan": True,
            "use_arpwatch": False,
            "known_devices_file": "known_devices.json",
            "alert_on_new_device": True,
            "alert_on_device_left": True,
        },
        "flows": {
            "watch_connections": True,
            "track_top_talkers": True,
            "alert_on_scan_like_activity": True,
        },
        "ids": {
            "engine": "auto",
            "suricata_log": "/var/log/suricata/eve.json",
            "snort_log": "/var/log/snort/alert.json",
        },
        "alerts": {
            "website": {
                "enabled": True,
                "base_url": "https://your-website.example.com/api",
                "endpoint": "/v1/report",
                "api_key": "",
                "timeout_seconds": 10,
                "max_retries": 3,
            },
            "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
            "discord": {"enabled": False, "webhook_url": ""},
            "email": {"enabled": False, "smtp_host": "", "smtp_port": 587,
                      "user": "", "password": "", "to": ""},
        },
    }


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins)."""
    out = dict(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str) -> dict:
    user = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                user = json.load(fh)
        except Exception:
            user = {}
    return deep_merge(default_config(), user)


def atomic_write_json(path: str, data: dict) -> None:
    """Write JSON atomically (temp file + rename) to avoid corruption."""
    dir_name = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
