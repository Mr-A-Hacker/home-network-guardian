# Home Network Guardian

A router-only monitoring agent that watches your **entire house** from the
router: every device that joins/leaves the LAN, every network flow, and every
IDS alert — all reported to your website using **one API key per house**.

Works on any Linux/BSD router: OpenWrt / LEDE, pfSense / OPNsense,
Debian/Ubuntu, Raspberry Pi (as router), Alpine.

## Features
- **Every device** — continuous `nmap` + `arp-scan`; reports joins, leaves, and
  the full present-device list. Learns known MACs in `known_devices.json`.
- **Every move** — Suricata/Snort IDS alerts (port scans, brute force, malware
  sigs) plus connection-flow tracking (top talkers, scan-like activity).
- **One house key** — the router is a single agent; the `hng_house_…` key
  identifies the home on your website.
- **Resilient** — per-cycle error isolation, atomic state writes, retry with
  backoff on website sends, structured logging to `guardian.log`.

## Quick start (on the router, as root)
Clone then install:
```bash
git clone https://github.com/Mr-A-Hacker/home-network-guardian.git
cd home-network-guardian/guardian_agent
sudo bash install.sh
```
Or self-cloning one-liner:
```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/Mr-A-Hacker/home-network-guardian/main/guardian_agent/install.sh)"
```
On first run it prints a `hng_house_…` API key. Paste it into your website
once — that's the only key the whole house needs.

Run a single scan and exit:
```bash
sudo python3 guardian_agent.py --once
```

See [`guardian_agent/README.md`](guardian_agent/README.md) for full config
and the website API contract.
