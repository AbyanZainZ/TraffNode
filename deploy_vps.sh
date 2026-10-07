#!/usr/bin/env bash
# ==============================================================================
# TRAFFNODE — ONE-LINE VPS DEPLOYMENT SCRIPT (Ubuntu / Debian)
# Port: 8888 | Multi-Proxy Passive Income Engine
# ==============================================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}       TRAFFNODE ENGINE — ONE-LINE VPS INSTALLER (PORT 8888)                  ${NC}"
echo -e "${CYAN}==============================================================================${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Harap jalankan script ini sebagai root (sudo bash deploy_vps.sh)${NC}"
  exit 1
fi

INSTALL_DIR="/opt/traffnode"
echo -e "${GREEN}[1/6] Memperbarui sistem & menginstall dependensi...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl proxychains4 net-tools procps ufw

echo -e "${GREEN}[2/6] Menyiapkan binary resmi TraffMonetizer CLI (/usr/local/bin/cli)...${NC}"
TM_PATH="/usr/local/bin/cli"
TM_SYMLINK="/usr/local/bin/traffmonetizer"

if [ ! -f "$TM_PATH" ] && [ ! -f "$TM_SYMLINK" ]; then
    echo -e "${YELLOW}Mengunduh binary TraffMonetizer resmi dari Docker Hub...${NC}"
    curl -sL https://github.com/google/go-containerregistry/releases/latest/download/go-containerregistry_Linux_x86_64.tar.gz | tar -xz -C /usr/local/bin crane || true
    chmod +x /usr/local/bin/crane 2>/dev/null || true
    if [ -x "/usr/local/bin/crane" ]; then
        crane export traffmonetizer/cli_v2:latest - | tar -x -C / usr/local/bin/cli 2>/dev/null || true
    fi
    chmod +x "$TM_PATH" 2>/dev/null || true
    ln -sf "$TM_PATH" "$TM_SYMLINK" 2>/dev/null || true
fi

echo -e "${GREEN}[3/6] Menyiapkan direktori proyek di ${INSTALL_DIR}...${NC}"
if [ -f "app.py" ] && [ -d "static" ]; then
    echo -e "${CYAN}Menyalin file dari direktori saat ini...${NC}"
    mkdir -p "$INSTALL_DIR"
    cp -a . "$INSTALL_DIR/"
else
    REPO_URL="${1:-https://github.com/AbyanZainZ/TraffNode.git}"
    echo -e "${YELLOW}Mengunduh source code dari ${REPO_URL}...${NC}"
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" pull
    else
        rm -rf "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR"
    fi
fi

cd "$INSTALL_DIR"

echo -e "${GREEN}[4/6] Menyiapkan Python Virtual Environment...${NC}"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

echo -e "${GREEN}[5/6] Tuning Kernel Limits & Konfigurasi Firewall Port 8888...${NC}"
# Tuning file descriptors untuk mendukung ratusan node
ulimit -n 65535 2>/dev/null || true
sysctl -w fs.file-max=2097152 2>/dev/null || true

ufw allow 22/tcp comment "SSH" || true
ufw allow 8888/tcp comment "TraffNode Dashboard" || true
ufw --force enable || true

echo -e "${GREEN}[6/6] Mendaftarkan Systemd Service (traffnode.service)...${NC}"
cat << 'EOF' > /etc/systemd/system/traffnode.service
[Unit]
Description=TraffNode VPS Multi-Proxy Passive Income Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/traffnode
ExecStart=/opt/traffnode/venv/bin/python3 /opt/traffnode/app.py
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable traffnode
systemctl restart traffnode

# Detect public IP
SERVER_IP=$(curl -s -4 https://api.ipify.org || curl -s -4 https://ifconfig.me || echo "IP_VPS_ANDA")

echo ""
echo -e "${CYAN}==============================================================================${NC}"
echo -e "${GREEN}🎉 TRAFFNODE ENGINE BERHASIL DIINSTALL & DIAKTIFKAN DI VPS!${NC}"
echo -e "${CYAN}==============================================================================${NC}"
echo -e "Web Dashboard  : ${YELLOW}http://${SERVER_IP}:8888${NC}"
echo -e "Status Service : ${GREEN}systemctl status traffnode${NC}"
echo -e "Log Service    : ${GREEN}journalctl -u traffnode -f${NC}"
echo -e "${CYAN}==============================================================================${NC}"
echo -e "Buka browser Anda di: ${YELLOW}http://${SERVER_IP}:8888${NC} untuk mulai monetisasi proxy!"
