#!/bin/bash
set -euo pipefail

echo "=== Deploying TurboBond Server on VPS ==="

# Ensure Docker is installed
if ! command -v docker &> /dev/null; then
    echo "[TurboBond] Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker.io
    sudo systemctl enable --now docker
fi

sudo mkdir -p /opt/turbobond-server/config

cat << 'DOCKERFILE' | sudo tee /opt/turbobond-server/Dockerfile
FROM ubuntu:24.04
RUN apt-get update -qq && \
    apt-get install -y -qq curl ca-certificates iproute2 iptables openssl libevent-2.1-7t64 && \
    ARCH=$(dpkg --print-architecture) && \
    curl -sLO https://github.com/mp0rta/mqvpn/releases/latest/download/mqvpn_0.16.3_${ARCH}.deb && \
    dpkg -i mqvpn_0.16.3_${ARCH}.deb && \
    rm mqvpn_0.16.3_${ARCH}.deb && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 443/udp

ENTRYPOINT ["/entrypoint.sh"]
DOCKERFILE

cat << 'ENTRY' | sudo tee /opt/turbobond-server/entrypoint.sh
#!/bin/bash
set -e

# Graceful shutdown on SIGTERM from docker stop
cleanup() {
    echo "[TurboBond] Received shutdown signal, stopping mqvpn..."
    kill -TERM "$MQVPN_PID" 2>/dev/null
    wait "$MQVPN_PID" 2>/dev/null
    exit 0
}
trap cleanup SIGTERM SIGINT

if [ ! -f /etc/mqvpn/server.crt ]; then
    echo "[TurboBond] Generating TLS certs..."
    openssl req -x509 -newkey rsa:2048 -nodes -keyout /etc/mqvpn/server.key -out /etc/mqvpn/server.crt -days 3650 -subj "/CN=TurboBond"
fi

mkdir -p /dev/net
if [ ! -c /dev/net/tun ]; then
    mknod /dev/net/tun c 10 200
fi

echo 1 > /proc/sys/net/ipv4/ip_forward 2>/dev/null || true

iptables -t nat -C POSTROUTING -s 10.8.0.0/24 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -j MASQUERADE
iptables -C FORWARD -s 10.8.0.0/24 -j ACCEPT 2>/dev/null || iptables -A FORWARD -s 10.8.0.0/24 -j ACCEPT
iptables -C FORWARD -d 10.8.0.0/24 -m state --state RELATED,ESTABLISHED 2>/dev/null || iptables -A FORWARD -d 10.8.0.0/24 -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "[TurboBond] Server starting mqvpn on 0.0.0.0:443..."
mqvpn --config /etc/mqvpn/server.conf &
MQVPN_PID=$!
wait "$MQVPN_PID"
ENTRY

sudo chmod +x /opt/turbobond-server/entrypoint.sh

# Generate server.conf if not already present
if [ ! -f /opt/turbobond-server/config/server.conf ]; then
    KEY=$(openssl rand -base64 32)
    cat << CFG | sudo tee /opt/turbobond-server/config/server.conf
[Interface]
Listen = 0.0.0.0:443
Subnet = 10.8.0.0/24

[TLS]
Cert = /etc/mqvpn/server.crt
Key = /etc/mqvpn/server.key

[Auth]
Key = $KEY

[Multipath]
Scheduler = wlb
CC = bbr2
CFG
fi

# Enable host forwarding
sudo sysctl -w net.ipv4.ip_forward=1
sudo sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.conf
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# Allow UDP 443 through ufw
sudo ufw allow 443/udp

# Build Docker image
cd /opt/turbobond-server
sudo docker build -t turbobond-server:latest .

# Stop existing container if running
sudo docker rm -f turbobond-server 2>/dev/null || true

# Run container with host network and NET_ADMIN privileges
sudo docker run -d \
    --name turbobond-server \
    --restart always \
    --net=host \
    --cap-add=NET_ADMIN \
    --device=/dev/net/tun \
    -v /opt/turbobond-server/config:/etc/mqvpn \
    turbobond-server:latest

echo "============================================================"
echo "TURBOBOND SERVER READY (UAE NORTH)!"
echo -n "AUTH KEY: "
sudo grep -i "^Key =" /opt/turbobond-server/config/server.conf | awk '{print $3}'
echo "============================================================"
