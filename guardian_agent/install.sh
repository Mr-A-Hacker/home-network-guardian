#!/usr/bin/env bash
# =====================================================================
#  Home Network Guardian - router house agent installer
#  Targets ANY Linux/BSD router (OpenWrt, pfSense/OPNsense, Debian/RPi...).
#  Run as root:  sudo bash install.sh
#  Optional: pass a repo URL to self-clone:
#    sudo bash install.sh https://github.com/you/home-network-guardian
# =====================================================================
set -euo pipefail

REPO_URL="${1:-https://github.com/Mr-A-Hacker/home-network-guardian}"

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd 2>/dev/null || pwd)"

# If the agent files aren't next to this script (e.g. piped via curl),
# clone the repo automatically so the one-liner works.
if [ ! -f "$AGENT_DIR/guardian_agent.py" ]; then
    echo "==> Agent files not local; cloning from $REPO_URL"
    TMP="$(mktemp -d)"
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 "$REPO_URL" "$TMP/repo"
    else
        echo "!! git not available. Install git or run inside the cloned repo."
        exit 1
    fi
    AGENT_DIR="$TMP/repo/guardian_agent"
fi
cd "$AGENT_DIR"

# Locate a working python3
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
    echo "!! python3 not found after install. Aborting."
    exit 1
fi

echo "==> Home Network Guardian installer (router / house agent)"
echo "==> Agent dir: $AGENT_DIR"

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
if ! $PKG_INSTALL python3 nmap arp-scan suricata; then
    echo "!! Suricata may be unavailable; agent still works with discovery only."
    $PKG_INSTALL python3 nmap arp-scan || true
fi

# ---- 3. Generate the ONE house API key -------------------------------
echo "==> Generating house API key (one key for the whole house)..."
KEY_OUT="$("$PY" api_key.py)"
echo "$KEY_OUT"
HOUSE_KEY="$(echo "$KEY_OUT" | awk -F': ' '/API Key/{print $2}')"

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
ExecStart=$PY $AGENT_DIR/guardian_agent.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now guardian.service
    echo "==> Started. Logs: journalctl -u guardian -f"
elif [ "$PM" = "opkg" ]; then
    echo "==> OpenWrt detected. Create /etc/init.d/guardian (procd) to autostart."
    echo "   Then: /etc/init.d/guardian enable && /etc/init.d/guardian start"
else
    echo "==> No systemd. Run manually: sudo $PY guardian_agent.py"
fi

echo
echo "==================================================================="
echo "  HOUSE API KEY: ${HOUSE_KEY}"
echo "  Copy this ONE key into your website for the whole house."
echo "==================================================================="
echo "==> Done."
