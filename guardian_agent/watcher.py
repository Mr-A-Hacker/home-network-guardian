"""LAN watcher: sees every device and every move.

Combines nmap + arp-scan for device discovery and tracks the full device
state over time so the agent can report joins, leaves, and active devices.
This is the "watch every device" core of the house agent.
"""
import json
import os
import re
import shutil
import subprocess
import time

from common import atomic_write_json, get_logger

log = get_logger("watcher")

_MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


def _which(tool):
    return shutil.which(tool)


def nmap_scan(subnet: str) -> list[dict]:
    if not _which("nmap"):
        log.warning("nmap not installed - skipping nmap scan")
        return []
    try:
        out = subprocess.run(["nmap", "-sn", "-oX", "-", subnet],
                             capture_output=True, text=True, timeout=180).stdout
    except subprocess.TimeoutExpired:
        log.warning("nmap scan timed out on %s", subnet)
        return []
    except Exception as exc:
        log.error("nmap scan failed: %s", exc)
        return []
    hosts = []
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(out)
    except Exception:
        return hosts
    for host in root.iter("host"):
        addr = mac = vendor = None
        for a in host.findall("address"):
            if a.get("addrtype") == "ipv4":
                addr = a.get("addr")
            elif a.get("addrtype") == "mac":
                mac = a.get("addr")
                vendor = a.get("vendor")
        hosts.append({"ip": addr, "mac": mac.lower() if mac else None,
                      "vendor": vendor})
    return hosts


def arp_scan(interface: str = "auto") -> list[dict]:
    if not _which("arp-scan"):
        log.warning("arp-scan not installed - skipping arp-scan")
        return []
    cmd = ["arp-scan", "--localnet"]
    if interface != "auto":
        cmd = ["arp-scan", "-I", interface, "--localnet"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=180).stdout
    except subprocess.TimeoutExpired:
        log.warning("arp-scan timed out")
        return []
    except Exception as exc:
        log.error("arp-scan failed: %s", exc)
        return []
    hosts = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and _MAC_RE.fullmatch(parts[1]):
            hosts.append({"ip": parts[0], "mac": parts[1].lower(),
                          "vendor": " ".join(parts[2:]) or None})
    return hosts


def load_known(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        log.warning("could not read known devices file %s", path)
        return {}


def scan_once(config: dict) -> dict:
    """Return current device snapshot keyed by MAC."""
    cfg = config["house"]
    hosts = []
    if config["discovery"].get("use_nmap"):
        hosts += nmap_scan(cfg["subnet"])
    if config["discovery"].get("use_arp_scan"):
        hosts += arp_scan(cfg.get("interface", "auto"))

    snap = {}
    for h in hosts:
        if h.get("mac"):
            snap[h["mac"]] = h
    return snap


def diff_state(previous: dict, current: dict) -> dict:
    prev_macs = set(previous)
    cur_macs = set(current)
    return {
        "joined": [current[m] for m in (cur_macs - prev_macs)],
        "left": [previous[m] for m in (prev_macs - cur_macs)],
        "present": [current[m] for m in (cur_macs & prev_macs)],
        "total_present": len(cur_macs),
    }


def watch(config: dict, state: dict) -> dict:
    """Full house scan: returns device diff + persistent known-device map."""
    known_file = config["discovery"].get("known_devices_file", "known_devices.json")
    known = load_known(known_file)

    current = scan_once(config)
    previous = state.get("last_snapshot", {})
    result = diff_state(previous, current)

    state["last_snapshot"] = current
    now = int(time.time())
    for mac, dev in current.items():
        if mac not in known:
            known[mac] = {**dev, "first_seen": now, "last_seen": now}
        else:
            known[mac]["last_seen"] = now
    try:
        atomic_write_json(known_file, known)
    except Exception as exc:
        log.error("failed to persist known devices: %s", exc)

    result["known_device_count"] = len(known)
    return result
