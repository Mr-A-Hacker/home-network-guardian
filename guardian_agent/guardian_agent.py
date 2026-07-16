#!/usr/bin/env python3
"""Home Network Guardian - router house agent.

One agent on the router watches the WHOLE house: every device that joins or
leaves, every network flow, and every IDS alert. All reports go to your
website using ONE house API key.
"""
import json
import os
import signal
import sys
import time

import api_key
import alerts as alerting
import watcher
import ids

CONFIG_PATH = "config.json"
STATE_PATH = "agent_state.json"


def load_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_state(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return {"last_snapshot": {}, "log_offsets": {}}


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    key_rec = api_key.load_or_create_key()
    print(f"[guardian] house_id={key_rec['house_id']} api_key={key_rec['api_key']}")

    state = load_state(STATE_PATH)
    if "log_offsets" not in state:
        state["log_offsets"] = {}

    if config["alerts"]["website"].get("enabled") and \
       not config["alerts"]["website"].get("api_key"):
        config["alerts"]["website"]["api_key"] = key_rec["api_key"]

    stop = {"flag": False}

    def shutdown(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    interval = config["house"]["scan_interval_seconds"]
    print(f"[guardian] watching house every {interval}s")

    while not stop["flag"]:
        report = {
            "house_id": key_rec["house_id"],
            "event": "status",
            "timestamp": int(time.time()),
            "house_name": config["house"].get("name", "home"),
        }

        # --- Every device: joins / leaves / present ---
        dev = watcher.watch(config, state)
        report["devices"] = {
            "total_present": dev["total_present"],
            "known_count": dev["known_device_count"],
            "present": dev["present"],
            "joined": dev["joined"],
            "left": dev["left"],
        }
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

        # --- Every move: IDS alerts + flows ---
        new_alerts = ids.collect_ids(config, state["log_offsets"])
        report["ids_alerts"] = new_alerts
        for a in new_alerts:
            alerting.dispatch_event(config, key_rec["api_key"], {
                "type": "ids_alert", **a,
            })

        flows = ids.collect_flows(config, state["log_offsets"])
        report["flows"] = flows
        if flows.get("scan_like_sources"):
            alerting.dispatch_event(config, key_rec["api_key"], {
                "type": "scan_like_activity",
                "sources": flows["scan_like_sources"],
            })

        report["ids"] = ids.ids_status(config)

        # Heartbeat / full status to the website
        alerting.send_to_website(config, report, key_rec["api_key"])

        save_state(STATE_PATH, state)

        for _ in range(interval):
            if stop["flag"]:
                break
            time.sleep(1)

    print("[guardian] stopped")


if __name__ == "__main__":
    main()
