"""Alert dispatch to the website (primary) and optional direct channels.

The single house API key is sent on every request so the website knows
which home the report belongs to. All send functions are fail-safe: they
never raise, and the website send retries on transient errors.
"""
import json
import smtplib
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

from common import get_logger

log = get_logger("alerts")


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status in (200, 201, 202)


def send_to_website(cfg: dict, payload: dict, api_key: str,
                    retries: int = 3) -> bool:
    web = cfg.get("website", {})
    if not web.get("enabled"):
        return False
    url = f"{web['base_url'].rstrip('/')}{web.get('endpoint', '/v1/report')}"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "Authorization": f"Bearer {api_key}",
    }
    timeout = web.get("timeout_seconds", 10)
    last_err = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            ok = _post_json(url, payload, headers, timeout)
            if ok:
                return True
            log.warning("website returned non-2xx (attempt %d)", attempt)
        except urllib.error.HTTPError as exc:
            # 4xx = bad key/config, don't retry
            if 400 <= exc.code < 500:
                log.error("website rejected report: %s", exc.code)
                return False
            last_err = exc
        except Exception as exc:  # pragma: no cover - network/timeout
            last_err = exc
        if attempt < retries:
            time.sleep(min(2 ** attempt, 10))
    if last_err:
        log.error("website send failed after %d tries: %s", retries, last_err)
    return False


def send_telegram(cfg: dict, message: str) -> bool:
    t = cfg.get("telegram", {})
    if not t.get("enabled"):
        return False
    url = (f"https://api.telegram.org/bot{t['bot_token']}/sendMessage?"
           f"chat_id={t['chat_id']}&text={urllib.parse.quote(message)}")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        log.warning("telegram send failed: %s", exc)
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
    except Exception as exc:
        log.warning("discord send failed: %s", exc)
        return False


def send_email(cfg: dict, subject: str, body: str) -> bool:
    e = cfg.get("email", {})
    if not e.get("enabled"):
        return False
    if not e.get("smtp_host") or not e.get("user"):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = e["user"]
    msg["To"] = e["to"]
    msg.set_content(body)
    try:
        with smtplib.SMTP(e["smtp_host"], int(e.get("smtp_port", 587))) as s:
            s.starttls()
            s.login(e["user"], e["password"])
            s.send_message(msg)
        return True
    except Exception as exc:
        log.warning("email send failed: %s", exc)
        return False


def dispatch_event(cfg: dict, api_key: str, event: dict) -> None:
    """Send one event to all enabled channels (fail-safe)."""
    subject = f"[House] {event.get('type', 'event')}"
    body = json.dumps(event, indent=2)
    send_to_website(cfg, {"event": "alert", "alert": event}, api_key)
    send_telegram(cfg, body)
    send_discord(cfg, body)
    send_email(cfg, subject, body)
