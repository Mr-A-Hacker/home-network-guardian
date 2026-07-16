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
import xml.etree.ElementTree as ET


_MAC_RE = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")


def _which(tool):
    return shutil.which(tool)


def nmap_scan(subnet: str) -> list[dict]:
    if not _which("nmap"):
        return []
    try:
        out = subprocess.run(["nmap", "-sn", "-oX", "-", subnet],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return []
    hosts = []
    try:
        root = ET.fromstring(out)
    except ET.ParseError:
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
        return []
    cmd = ["arp-scan", "--localnet"]
    if interface != "auto":
        cmd = ["arp-scan", "-I", interface, "--localnet"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=120).stdout
    except Exception:
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
        return {}


def save_known(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


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


def diff_state(config: dict, previous: dict, current: dict) -> dict:
    """Compute joins / leaves / stable between two snapshots."""
    prev_macs = set(previous)
    cur_macs = set(current)

    joined = [current[m] for m in (cur_macs - prev_macs)]
    left = [previous[m] for m in (prev_macs - cur_macs)]
    present = [current[m] for m in (cur_macs & prev_macs)]

    return {
        "joined": joined,
        "left": left,
        "present": present,
        "total_present": len(cur_macs),
    }


def watch(config: dict, state: dict) -> dict:
    """Full house scan: returns device diff + persistent known-device map."""
    known_file = config["discovery"].get("known_devices_file", "known_devices.json")
    known = load_known(known_file)

    current = scan_once(config)
    previous = state.get("last_snapshot", {})

    result = diff_state(config, previous, current)

    # Persist snapshot and learn new devices as "known" once seen.
    state["last_snapshot"] = current
    for mac, dev in current.items():
        if mac not in known:
            known[mac] = {**dev, "first_seen": int(__import__("time").time())}
    save_known(known_file, known)

    result["known_device_count"] = len(known)
    return result
