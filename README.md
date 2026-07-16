# Home Network Guardian

A router-only monitoring agent that watches your **entire house** from the
router: every device that joins/leaves the LAN, every network flow, and every
IDS alert — all reported to your website using **one API key per house**.

Works on any Linux/BSD router: OpenWrt / LEDE, pfSense / OPNsense,
Debian/Ubuntu, Raspberry Pi (as router), Alpine.

## Quick start (on the router)
```bash
# Clone then install (as root):
git clone https://github.com/YOURUSER/home-network-guardian.git
cd home-network-guardian/guardian_agent
sudo bash install.sh
```
Or one-liner (clones to /opt/guardian then installs):
```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/YOURUSER/home-network-guardian/main/guardian_agent/install.sh)"
```
Note: the one-liner downloads `install.sh` which itself can clone a repo if
you pass a URL: `sudo bash install.sh https://github.com/YOURUSER/home-network-guardian`
On first run it prints a `hng_house_…` API key. Paste it into your website
once — that's the only key the whole house needs.

See [`guardian_agent/README.md`](guardian_agent/README.md) for full config
and the website API contract.
