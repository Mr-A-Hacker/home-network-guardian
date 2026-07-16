"""Intrusion detection + connection-flow watching.

Reads Suricata/Snort JSON logs for attack signatures, and tracks network
flows (top talkers, scan-like activity) so the house agent sees "every move".
"""
import json
import os
import shutil
import subprocess
import time


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


def _tail_json(path: str, offsets: dict) -> list[dict]:
    if not os.path.exists(path):
        return []
    alerts = []
    try:
        size = os.path.getsize(path)
        last = offsets.get(path, 0)
        if last > size:
            last = 0
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(last)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    alerts.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            offsets[path] = fh.tell()
    except Exception:
        return alerts
    return alerts


def collect_ids(config: dict, offsets: dict) -> list[dict]:
    engine = detect_engine(config)
    cfg = config["ids"]
    out = []
    if engine == "suricata":
        for ev in _tail_json(cfg.get("suricata_log", ""), offsets):
            if ev.get("event_type") == "alert":
                a = ev.get("alert", {})
                out.append({
                    "engine": "suricata",
                    "signature": a.get("signature"),
                    "severity": a.get("severity"),
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
                "src_ip": ev.get("src_ip") or ev.get("srcip"),
                "dest_ip": ev.get("dest_ip") or ev.get("dstip"),
                "proto": ev.get("proto"),
                "timestamp": ev.get("timestamp") or time.time(),
            })
    return out


def collect_flows(config: dict, offsets: dict) -> dict:
    """Track connection flows from Suricata eve.json (event_type == flow)."""
    if not config["flows"].get("watch_connections"):
        return {}
    cfg = config["ids"]
    talkers = {}
    scans = []
    if shutil.which("suricata") and os.path.exists(cfg.get("suricata_log", "")):
        for ev in _tail_json(cfg["suricata_log"], offsets):
            if ev.get("event_type") == "flow":
                src = ev.get("src_ip")
                if src:
                    talkers[src] = talkers.get(src, 0) + 1
            if ev.get("event_type") == "alert":
                # port-scan / scan signatures
                sig = (ev.get("alert") or {}).get("signature", "").lower()
                if "scan" in sig or "spike" in sig:
                    scans.append(ev.get("src_ip"))
    top = sorted(talkers.items(), key=lambda x: -x[1])[:10]
    return {
        "top_talkers": [{"ip": ip, "flows": n} for ip, n in top],
        "scan_like_sources": list(set(scans)),
    }


def ids_status(config: dict) -> dict:
    engine = detect_engine(config)
    running = False
    if engine == "suricata":
        running = subprocess.run(["pgrep", "-f", "suricata"],
                                 capture_output=True).stdout.strip() != b""
    elif engine == "snort":
        running = subprocess.run(["pgrep", "-f", "snort"],
                                 capture_output=True).stdout.strip() != b""
    return {"engine": engine, "running": running}
