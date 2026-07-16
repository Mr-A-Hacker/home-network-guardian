# Home Network Guardian — Router House Agent

One agent that runs **on your router** and watches the **entire house**:
every device that joins or leaves the LAN, every network flow, and every
IDS alert. All reports go to **your website using ONE API key per house**
— no per-device keys.

Works on any Linux/BSD router: **OpenWrt / LEDE, pfSense / OPNsense,
Debian/Ubuntu, Raspberry Pi (as router), Alpine**.

## What it watches
- **Every device** — continuous `nmap` + `arp-scan`; reports joins, leaves,
  and the full present-device list. Learns known MACs in `known_devices.json`.
- **Every move** — Suricata/Snort IDS alerts (port scans, brute force,
  malware sigs) plus connection-flow tracking (top talkers, scan-like
  activity) from `eve.json`.
- **One house key** — the router is a single agent; the `hng_house_…` key
  identifies the home on your website.

## Install (one command, as root)
Using local files:
```bash
sudo bash install.sh
```
Or clone straight from GitHub:
```bash
sudo bash install.sh https://github.com/Mr-A-Hacker/home-network-guardian
```
`install.sh` auto-detects the package manager (`opkg`/`apk`/`pkg`/`apt`/`yum`),
installs `python3 nmap arp-scan suricata`, generates the **one house key**,
and installs a systemd service (or notes OpenWrt init).

On first run it prints the `hng_house_…` API key. Paste it into your website
once — that's the only key the house needs.

## Configure (`config.json`)
- `house.subnet` — your LAN, e.g. `"192.168.1.0/24"`.
- `house.scan_interval_seconds` — how often to re-scan (default 60).
- `house.interface` — `"auto"` or `"br-lan"` / `"eth0"`.
- `discovery.alert_on_new_device` / `alert_on_device_left` — toggle join/leave alerts.
- `flows.watch_connections` / `alert_on_scan_like_activity` — "every move" tracking.
- `ids.engine` — `"auto"`, `"suricata"`, or `"snort"`.
- `alerts.website.base_url` — your site. Leave `api_key` empty (auto-filled).

## Website API contract
POST `{base_url}/v1/report` with header `X-API-Key: hng_house_xxx`:
```json
{
  "house_id": "abcd1234...",
  "event": "status",
  "agent_version": "1.0.0",
  "timestamp": 1700000000,
  "uptime_ok": true,
  "devices": {
    "total_present": 7,
    "known_count": 6,
    "present": [ ... ],
    "joined": [ ... ],
    "left": [ ... ]
  },
  "ids_alerts": [ { "signature": "...", "src_ip": "..." } ],
  "flows": { "top_talkers": [ ... ], "scan_like_sources": [ ... ] },
  "ids": { "engine": "suricata", "running": true },
  "tools": { "nmap": true, "arp_scan": true, "suricata": true, "snort": false }
}
```
Your backend validates the ONE house key, then shows all devices + activity
for that home in the dashboard.

## Logs
All activity is logged to stdout and `guardian.log` (rotated manually or via
logrotate). Each cycle is isolated: a failure in discovery, IDS, or flows will
not crash the agent.
