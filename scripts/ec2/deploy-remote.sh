#!/usr/bin/env bash
set -euo pipefail

[[ "${DEPLOY_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::DEPLOY_SHA invalido." >&2; exit 1; }
ssh_dir="${RUNNER_TEMP:?RUNNER_TEMP ausente}/siopa-ec2"
port="${EC2_PORT:-22}"

# prepare-ssh.sh restricts these arguments to shell-safe DNS/user/path values.
# Quote each argument again because SSH passes a command string to the remote shell.
ssh -i "$ssh_dir/key" -p "$((10#$port))" \
    -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=15 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$ssh_dir/known_hosts" \
    -o GlobalKnownHostsFile=/dev/null \
    "${EC2_USER}@${EC2_HOST}" \
    "bash -s -- '$EC2_PROJECT_DIR' '$REPO_URL' '$DEPLOY_SHA'" <<'REMOTE'
set -euo pipefail
project_dir="$1"
repo_url="$2"
deploy_sha="$3"

mkdir -p "$project_dir"
if [ ! -d "$project_dir/.git" ]; then
    git clone "$repo_url" "$project_dir"
fi
cd "$project_dir"
# Preserve .env, data and any server-side edits. Do not reset or clean this tree.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "O repositorio no servidor tem alteracoes locais. Revise antes do deploy." >&2
    exit 1
fi
git fetch --prune origin main
# An older CI run must never roll production back after main has advanced.
if [ "$(git rev-parse origin/main)" != "$deploy_sha" ]; then
    echo "main avancou desde este CI. Nenhuma stack foi alterada; aguarde o proximo deploy." >&2
    exit 1
fi
git checkout --detach "$deploy_sha"
bash scripts/ec2/deploy.sh
REMOTE

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    printf 'Deploy EC2 concluido para o commit `%s`.\n' "$DEPLOY_SHA" >> "$GITHUB_STEP_SUMMARY"
fi
