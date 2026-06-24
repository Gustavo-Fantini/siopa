#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
    echo "execute este script com sudo" >&2
    exit 1
fi

PROJECT_DIR="${PROJECT_DIR:-/srv/siopa}"
DEPLOY_USER="${DEPLOY_USER:-${SUDO_USER:-ubuntu}}"

apt-get update
apt-get install -y ca-certificates curl git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | tee /etc/apt/sources.list.d/docker.list >/dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker

if id "$DEPLOY_USER" >/dev/null 2>&1; then
    usermod -aG docker "$DEPLOY_USER"
fi

mkdir -p "$PROJECT_DIR"
chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$PROJECT_DIR"

cat <<EOF
Bootstrap concluido.

Proximos passos:
1. saia e entre novamente na sessao SSH para o grupo docker ser aplicado
2. clone o repositorio em: $PROJECT_DIR
3. copie .env.production.example para .env
4. execute: bash scripts/ec2/deploy.sh
EOF
