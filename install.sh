#!/bin/bash
# camera-streamer Web UI — Installer
# https://github.com/D4n13l000/camera-streamer-ui
#
# Tested on: OctoPi 1.0.0+ (64-bit, arm64), Raspberry Pi 3B+ / 4 / 5
# Camera:    Raspberry Pi Camera Module 3 (IMX708)
# Requires:  camera-streamer already installed and running

set -e

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $1"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
section() { echo -e "\n${BOLD}── $1 ──${NC}"; }

# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║       camera-streamer Web UI Installer       ║"
echo "  ║   github.com/D4n13l000/camera-streamer-ui   ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Detect user ───────────────────────────────────────────────────────────────
INSTALL_USER="${SUDO_USER:-$USER}"
if [[ "$INSTALL_USER" == "root" ]]; then
    INSTALL_USER="pi"
fi
HOME_DIR=$(eval echo "~$INSTALL_USER")
INSTALL_DIR="$HOME_DIR/camera-streamer-ui"
VENV_DIR="$INSTALL_DIR/venv"

info "Installing for user: $INSTALL_USER"
info "Install directory:   $INSTALL_DIR"

# ── Checks ────────────────────────────────────────────────────────────────────
section "Pre-flight checks"

# Must run as root (for systemd + sudo cp)
if [[ $EUID -ne 0 ]]; then
    error "Please run as root:  sudo bash install.sh"
fi

# camera-streamer service must exist
if ! systemctl list-unit-files | grep -q "camera-streamer"; then
    error "camera-streamer service not found.\nPlease install camera-streamer first:\nhttps://github.com/ayufan/camera-streamer"
fi

# Detect config file path
CONFIG_PATH=""
CANDIDATE_PATHS=(
    "/etc/camera-streamer.conf.d/libcamera.conf"
    "/etc/camera-streamer/libcamera.conf"
    "/boot/camera-streamer/libcamera.conf"
)
for p in "${CANDIDATE_PATHS[@]}"; do
    if [[ -f "$p" ]]; then
        CONFIG_PATH="$p"
        break
    fi
done

if [[ -z "$CONFIG_PATH" ]]; then
    warn "Could not auto-detect camera-streamer config file."
    warn "Searched in:"
    for p in "${CANDIDATE_PATHS[@]}"; do echo "  $p"; done
    read -rp "Enter the full path to your libcamera.conf: " CONFIG_PATH
    [[ -f "$CONFIG_PATH" ]] || error "File not found: $CONFIG_PATH"
fi
ok "Config file: $CONFIG_PATH"

# Detect camera-streamer API port
API_PORT=8080
if ss -tlnp 2>/dev/null | grep -q ":8081"; then
    warn "Port 8080 not detected. Trying 8081..."
    API_PORT=8081
fi
ok "Camera API port: $API_PORT"

# Detect a free port for the UI (default 5001, skip 5000 which OctoPrint uses)
UI_PORT=5001
if ss -tlnp 2>/dev/null | grep -q ":5001"; then
    UI_PORT=5002
    warn "Port 5001 in use, using 5002 instead."
fi
ok "Web UI port: $UI_PORT"

# Python3 available?
python3 --version &>/dev/null || error "python3 not found."
ok "Python3 found: $(python3 --version)"

# ── Install files ─────────────────────────────────────────────────────────────
section "Installing files"

mkdir -p "$INSTALL_DIR"
cp "$(dirname "$0")/camera_ui.py" "$INSTALL_DIR/camera_ui.py"
chown -R "$INSTALL_USER:$INSTALL_USER" "$INSTALL_DIR"
ok "Copied camera_ui.py to $INSTALL_DIR"

# Patch config path and ports into the script
sed -i "s|CONFIG_PATH = \"/etc/camera-streamer.conf.d/libcamera.conf\"|CONFIG_PATH = \"$CONFIG_PATH\"|g" "$INSTALL_DIR/camera_ui.py"
sed -i "s|CAMERA_API  = \"http://localhost:8080\"|CAMERA_API  = \"http://localhost:$API_PORT\"|g" "$INSTALL_DIR/camera_ui.py"
sed -i "s|port=5001|port=$UI_PORT|g" "$INSTALL_DIR/camera_ui.py"
ok "Patched config path and ports"

# ── Config file permissions ────────────────────────────────────────────────────
section "Config file permissions"

chmod 664 "$CONFIG_PATH"
chown root:"$INSTALL_USER" "$CONFIG_PATH"
ok "Set permissions on $CONFIG_PATH"

# ── Python virtual environment ────────────────────────────────────────────────
section "Python virtual environment"

if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating venv at $VENV_DIR ..."
    sudo -u "$INSTALL_USER" python3 -m venv "$VENV_DIR"
    ok "venv created"
else
    ok "venv already exists"
fi

info "Installing Flask and requests..."
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/pip" install --quiet flask requests
ok "Dependencies installed"

# ── Sudo rule for systemctl restart ───────────────────────────────────────────
section "Sudo permissions"

SUDOERS_FILE="/etc/sudoers.d/camera-streamer-ui"
cat > "$SUDOERS_FILE" <<EOF
# camera-streamer Web UI — allow service restart and config write without password
$INSTALL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart camera-streamer-libcamera
$INSTALL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart camera-streamer
$INSTALL_USER ALL=(ALL) NOPASSWD: /bin/cp /tmp/camera-ui.conf $CONFIG_PATH
$INSTALL_USER ALL=(ALL) NOPASSWD: /bin/rm /tmp/camera-ui.conf
$INSTALL_USER ALL=(ALL) NOPASSWD: /sbin/reboot
EOF
chmod 440 "$SUDOERS_FILE"
ok "Sudoers rule written to $SUDOERS_FILE"

# ── Systemd service ───────────────────────────────────────────────────────────
section "Systemd service"

SERVICE_FILE="/etc/systemd/system/camera-streamer-ui.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=camera-streamer Web UI
After=network.target camera-streamer-libcamera.service

[Service]
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/camera_ui.py
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5
User=$INSTALL_USER

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable camera-streamer-ui
systemctl restart camera-streamer-ui
ok "Service installed and started"

# ── Done ──────────────────────────────────────────────────────────────────────
PI_IP=$(hostname -I | awk '{print $1}')
echo -e "\n${GREEN}${BOLD}Installation complete!${NC}"
echo -e "────────────────────────────────────────────────"
echo -e "  Open in browser:  ${CYAN}http://${PI_IP}:${UI_PORT}${NC}"
echo -e "  Service status:   sudo systemctl status camera-streamer-ui"
echo -e "  View logs:        sudo journalctl -u camera-streamer-ui -f"
echo -e "────────────────────────────────────────────────\n"
