"""Intrusion detection + connection-flow watching.

Reads Suricata/Snort JSON logs for attack signatures, and tracks network
flows (top talkers, scan-like activity) so the house agent sees "every move".
"""
import json
import os
import shutil
import subprocess

from common import get_logger

log = get_logger("ids")


def detect_engine(config: dict) -> str:
    preferred = config["ids"].get("engine", "auto")
    have_suri = bool(shutil.which("suricata"))
    have_snort = bool(shutil.which("snort"))
    if preferred == "suricata" and have_suri:
        return "suricata"
    if preferred == "snort" and have_snort:
        return "snort"
    if preferred == "auto":
        if have_suri:
            return "suricata"
        if have_snort:
            return "snort"
    return "none"


def _process_running(name: str) -> bool:
    try:
        out = subprocess.run(["pgrep", "-f", name],
                             capture_output=True).stdout.strip()
        return bool(out)
    except Exception:
        return False


def _tail_json(path: str, offsets: dict, limit: int = 5000) -> list[dict]:
    """Read new JSON-lines from a log file using an offset.

    Falls back to scanning from the end if the file was rotated/truncated.
    Caps returned events per cycle to avoid memory spikes on busy networks.
    """
    if not path or not os.path.exists(path):
        return []
    events = []
    try:
        size = os.path.getsize(path)
        last = offsets.get(path, 0)
        if last > size:           # truncated/rotated -> re-read tail
            last = max(0, size - 200_000)
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(last)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(events) >= limit:
                    break
            offsets[path] = fh.tell()
    except Exception as exc:
        log.error("error reading %s: %s", path, exc)
    return events


def collect_ids(config: dict, offsets: dict) -> list[dict]:
    engine = detect_engine(config)
    cfg = config["ids"]
    out = []
    try:
        if engine == "suricata":
            for ev in _tail_json(cfg.get("suricata_log", ""), offsets):
                if ev.get("event_type") == "alert":
                    a = ev.get("alert", {})
                    out.append({
                        "engine": "suricata",
                        "signature": a.get("signature"),
                        "severity": a.get("severity"),
                        "category": a.get("category"),
                        "src_ip": ev.get("src_ip"),
                        "dest_ip": ev.get("dest_ip"),
                        "proto": ev.get("proto"),
                        "timestamp": ev.get("timestamp"),
                    })
        elif engine == "snort":
            for ev in _tail_json(cfg.get("snort_log", ""), offsets):
                out.append({
                    "engine": "snort",
                    "signature": ev.get("msg") or ev.get("signature"),
                    "severity": ev.get("priority"),
                    "category": ev.get("classification"),
                    "src_ip": ev.get("src_ip") or ev.get("srcip"),
                    "dest_ip": ev.get("dest_ip") or ev.get("dstip"),
                    "proto": ev.get("proto"),
                    "timestamp": ev.get("timestamp"),
                })
    except Exception as exc:
        log.error("IDS collection failed: %s", exc)
    return out


def collect_flows(config: dict, offsets: dict) -> dict:
    if not config["flows"].get("watch_connections", True):
        return {}
    cfg = config["ids"]
    path = cfg.get("suricata_log", "")
    talkers = {}
    scans = []
    if shutil.which("suricata") and path and os.path.exists(path):
        try:
            for ev in _tail_json(path, offsets):
                if ev.get("event_type") == "flow":
                    src = ev.get("src_ip")
                    if src:
                        talkers[src] = talkers.get(src, 0) + 1
                elif ev.get("event_type") == "alert":
                    sig = (ev.get("alert") or {}).get("signature", "").lower()
                    if "scan" in sig or "spike" in sig:
                        if ev.get("src_ip"):
                            scans.append(ev["src_ip"])
        except Exception as exc:
            log.error("flow collection failed: %s", exc)
    top = sorted(talkers.items(), key=lambda x: -x[1])[:10]
    return {
        "top_talkers": [{"ip": ip, "flows": n} for ip, n in top],
        "scan_like_sources": list(set(scans)),
    }


def ids_status(config: dict) -> dict:
    engine = detect_engine(config)
    running = False
    if engine == "suricata":
        running = _process_running("suricata")
    elif engine == "snort":
        running = _process_running("snort")
    return {"engine": engine, "running": running}
