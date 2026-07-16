#!/usr/bin/env bash
# =====================================================================
#  Home Network Guardian - router house agent installer
#  Targets ANY Linux/BSD router (OpenWrt, pfSense/OPNsense, Debian/RPi...).
#  Run as root:  sudo bash install.sh
# =====================================================================
set -euo pipefail

# Optional: clone from git instead of using local files.
#   sudo bash install.sh https://github.com/youruser/home-network-guardian
REPO_URL="${1:-https://github.com/YOURUSER/home-network-guardian}"

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd 2>/dev/null || pwd)"

# If the agent files aren't next to this script (e.g. piped via curl),
# clone the repo automatically so the one-liner works.
if [ ! -f "$AGENT_DIR/guardian_agent.py" ]; then
    echo "==> Agent files not local; cloning from $REPO_URL"
    TMP="$(mktemp -d)"
    ( command -v git >/dev/null 2>&1 && git clone --depth 1 "$REPO_URL" "$TMP/repo" ) || {
        echo "!! git not available or clone failed. Run inside the cloned repo instead."
        exit 1
    }
    AGENT_DIR="$TMP/repo/guardian_agent"
fi
cd "$AGENT_DIR"

echo "==> Home Network Guardian installer (router / house agent)"

# ---- 1. Detect package manager ---------------------------------------
if command -v opkg >/dev/null 2>&1; then
    PM="opkg"; PKG_UPDATE="opkg update"; PKG_INSTALL="opkg install"
elif command -v apk >/dev/null 2>&1; then
    PM="apk"; PKG_UPDATE="apk update"; PKG_INSTALL="apk add"
elif command -v pkg >/dev/null 2>&1; then
    PM="pkg"; PKG_UPDATE="pkg update"; PKG_INSTALL="pkg install -y"
elif command -v apt-get >/dev/null 2>&1; then
    PM="apt"; PKG_UPDATE="apt-get update"; PKG_INSTALL="apt-get install -y"
elif command -v yum >/dev/null 2>&1; then
    PM="yum"; PKG_UPDATE="yum makecache"; PKG_INSTALL="yum install -y"
else
    echo "!! No supported package manager (opkg/apk/pkg/apt/yum)."
    exit 1
fi
echo "==> Package manager: $PM"

# ---- 2. Install OS packages ------------------------------------------
$PKG_UPDATE
echo "==> Installing python3, nmap, arp-scan, suricata ..."
$PKG_INSTALL python3 nmap arp-scan suricata || {
    echo "!! Suricata may be unavailable; agent still works with discovery only."
    $PKG_INSTALL python3 nmap arp-scan || true
}

# ---- 3. Generate the ONE house API key -------------------------------
echo "==> Generating house API key (one key for the whole house)..."
python3 api_key.py

chmod +x guardian_agent.py

# ---- 4. Install as a service (best effort) ---------------------------
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
    echo "==> Installing systemd service..."
    cat >/etc/systemd/system/guardian.service <<EOF
[Unit]
Description=Home Network Guardian (house agent)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$AGENT_DIR
ExecStart=/usr/bin/python3 $AGENT_DIR/guardian_agent.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now guardian.service
    echo "==> Started. Logs: journalctl -u guardian -f"
elif [ "$PM" = "opkg" ]; then
    echo "==> OpenWrt: add a procd init script to autostart (see README)."
else
    echo "==> No systemd. Run manually: sudo python3 guardian_agent.py"
fi

echo
echo "==> Copy the hng_house_... API key above into your website for this house."
echo "==> Done."
