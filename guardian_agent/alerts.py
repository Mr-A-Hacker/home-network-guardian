"""Alert dispatch to the website (primary) and optional direct channels.

The single house API key is sent on every request so the website knows
which home the report belongs to.
"""
import json
import smtplib
import urllib.request
from email.message import EmailMessage


def send_to_website(cfg: dict, payload: dict, api_key: str) -> bool:
    web = cfg.get("website", {})
    if not web.get("enabled"):
        return False
    url = f"{web['base_url'].rstrip('/')}{web.get('endpoint', '/v1/report')}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=web.get("timeout_seconds", 10)) as resp:
            return resp.status in (200, 201, 202)
    except Exception:
        return False


def send_telegram(cfg: dict, message: str) -> bool:
    import urllib.parse
    t = cfg.get("telegram", {})
    if not t.get("enabled"):
        return False
    url = (f"https://api.telegram.org/bot{t['bot_token']}/sendMessage?"
           f"chat_id={t['chat_id']}&text={urllib.parse.quote(message)}")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def send_discord(cfg: dict, message: str) -> bool:
    d = cfg.get("discord", {})
    if not d.get("enabled"):
        return False
    data = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        d["webhook_url"], data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def dispatch_event(cfg: dict, api_key: str, event: dict) -> None:
    """Send one event (device join/leave, IDS alert, scan) to all channels."""
    subject = f"[House] {event.get('type', 'event')}"
    body = json.dumps(event, indent=2)
    send_to_website(cfg, {"event": "alert", "alert": event}, api_key)
    send_telegram(cfg, body)
    send_discord(cfg, body)
