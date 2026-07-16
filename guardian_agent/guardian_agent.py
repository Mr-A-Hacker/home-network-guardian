#!/usr/bin/env python3
"""Home Network Guardian - router house agent.

One agent on the router watches the WHOLE house: every device that joins or
leaves, every network flow, and every IDS alert. All reports go to your
website using ONE house API key.

Usage:
    python3 guardian_agent.py            # run the watch loop
    python3 guardian_agent.py --once     # single scan + report, then exit
    python3 guardian_agent.py --config /path/config.json
"""
import argparse
import json
import os
import signal
import sys
import time

from common import (AGENT_VERSION, atomic_write_json, get_logger, load_config)

import api_key
import alerts as alerting
import watcher
import ids

log = get_logger("guardian")

CONFIG_PATH = "config.json"
STATE_PATH = "agent_state.json"


def load_state(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            log.warning("state file corrupt, starting fresh")
    return {"last_snapshot": {}, "log_offsets": {}, "last_report_ts": 0}


def preflight(config: dict) -> dict:
    """Report tool/engine availability so the website shows setup status."""
    import shutil
    tools = {
        "nmap": bool(shutil.which("nmap")),
        "arp_scan": bool(shutil.which("arp-scan")),
        "suricata": bool(shutil.which("suricata")),
        "snort": bool(shutil.which("snort")),
    }
    ids_st = ids.ids_status(config)
    if not tools["nmap"] and not tools["arp_scan"]:
        log.warning("No discovery tool available (install nmap or arp-scan)")
    if ids_st["engine"] == "none":
        log.warning("No IDS engine available (install suricata or snort)")
    log.info("preflight: %s | ids=%s", tools, ids_st)
    return {"tools": tools, "ids": ids_st}


def build_report(config, key_rec, dev, new_alerts, flows, health) -> dict:
    return {
        "house_id": key_rec["house_id"],
        "event": "status",
        "agent_version": AGENT_VERSION,
        "timestamp": int(time.time()),
        "house_name": config["house"].get("name", "home"),
        "uptime_ok": health["ok"],
        "devices": {
            "total_present": dev["total_present"],
            "known_count": dev["known_device_count"],
            "present": dev["present"],
            "joined": dev["joined"],
            "left": dev["left"],
        },
        "ids_alerts": new_alerts,
        "flows": flows,
        "ids": health["ids"],
        "tools": health["tools"],
    }


def run_once(config, state, key_rec) -> dict:
    """One scan cycle. Returns the report; never raises."""
    health = preflight(config)

    try:
        dev = watcher.watch(config, state)
    except Exception as exc:
        log.error("watcher crashed: %s", exc)
        dev = {"total_present": 0, "known_device_count": 0,
               "present": [], "joined": [], "left": []}

    try:
        new_alerts = ids.collect_ids(config, state["log_offsets"])
    except Exception as exc:
        log.error("ids collection crashed: %s", exc)
        new_alerts = []

    try:
        flows = ids.collect_flows(config, state["log_offsets"])
    except Exception as exc:
        log.error("flow collection crashed: %s", exc)
        flows = {}

    # Device join/leave alerts
    if config["discovery"].get("alert_on_new_device"):
        for d in dev["joined"]:
            alerting.dispatch_event(config, key_rec["api_key"], {
                "type": "device_joined", "ip": d.get("ip"),
                "mac": d.get("mac"), "vendor": d.get("vendor"),
            })
    if config["discovery"].get("alert_on_device_left"):
        for d in dev["left"]:
            alerting.dispatch_event(config, key_rec["api_key"], {
                "type": "device_left", "ip": d.get("ip"),
                "mac": d.get("mac"), "vendor": d.get("vendor"),
            })

    for a in new_alerts:
        alerting.dispatch_event(config, key_rec["api_key"], {
            "type": "ids_alert", **a,
        })

    if flows.get("scan_like_sources") and \
       config["flows"].get("alert_on_scan_like_activity", True):
        alerting.dispatch_event(config, key_rec["api_key"], {
            "type": "scan_like_activity",
            "sources": flows["scan_like_sources"],
        })

    report = build_report(config, key_rec, dev, new_alerts, flows, health)
    ok = alerting.send_to_website(config, report, key_rec["api_key"])
    report["_delivered"] = ok
    if ok:
        state["last_report_ts"] = int(time.time())
    else:
        log.warning("report not delivered to website this cycle")
    return report


def main():
    ap = argparse.ArgumentParser(description="Home Network Guardian agent")
    ap.add_argument("--config", default=CONFIG_PATH, help="path to config.json")
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        log.error("config not found: %s", args.config)
        sys.exit(1)

    config = load_config(args.config)
    key_rec = api_key.load_or_create_key()
    log.info("house_id=%s api_key=%s", key_rec["house_id"], key_rec["api_key"])

    web = config["alerts"]["website"]
    if web.get("enabled") and not web.get("api_key"):
        web["api_key"] = key_rec["api_key"]

    state = load_state(STATE_PATH)
    if "log_offsets" not in state:
        state["log_offsets"] = {}

    stop = {"flag": False}

    def shutdown(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    interval = max(5, int(config["house"]["scan_interval_seconds"]))
    log.info("watching house every %ds (version %s)", interval, AGENT_VERSION)

    if args.once:
        run_once(config, state, key_rec)
        atomic_write_json(STATE_PATH, state)
        log.info("single run complete")
        return

    while not stop["flag"]:
        try:
            run_once(config, state, key_rec)
        except Exception as exc:
            log.error("unexpected cycle error: %s", exc)
        atomic_write_json(STATE_PATH, state)
        for _ in range(interval):
            if stop["flag"]:
                break
            time.sleep(1)

    log.info("stopped")


if __name__ == "__main__":
    main()
