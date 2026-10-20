#!/usr/bin/env bash
set -euo pipefail

fail() {
    echo "::error::$1" >&2
    exit 1
}

missing=()
for name in EC2_HOST EC2_USER EC2_PROJECT_DIR EC2_SSH_KEY EC2_KNOWN_HOSTS; do
    if [[ -z "${!name:-}" ]]; then
        missing+=("$name")
    fi
done
if ((${#missing[@]})); then
    fail "Deploy EC2 habilitado, mas faltam secrets: ${missing[*]}. Configure Settings > Secrets and variables > Actions ou o environment production. Veja docs/GITHUB_ACTIONS_SECRETS.md."
fi

port="${EC2_PORT:-22}"
[[ "$port" =~ ^[0-9]{1,5}$ ]] || fail "EC2_PORT deve ser uma porta numerica entre 1 e 65535."
((10#$port >= 1 && 10#$port <= 65535)) || fail "EC2_PORT deve estar entre 1 e 65535."
[[ "$EC2_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]*$ ]] || fail "EC2_HOST deve conter somente o DNS ou IP, sem protocolo, porta ou usuario."
[[ "$EC2_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || fail "EC2_USER deve ser um nome de usuario Linux."
[[ "$EC2_PROJECT_DIR" =~ ^/[a-zA-Z0-9_./-]+$ && "$EC2_PROJECT_DIR" != */../* && "$EC2_PROJECT_DIR" != */.. ]] || fail "EC2_PROJECT_DIR deve ser um caminho absoluto sem espacos nem segmentos '..', por exemplo /srv/siopa."

ssh_dir="${RUNNER_TEMP:?RUNNER_TEMP ausente}/siopa-ec2"
umask 077
mkdir -p "$ssh_dir"
chmod 700 "$ssh_dir"
printf '%s\n' "$EC2_SSH_KEY" | tr -d '\r' > "$ssh_dir/key"
printf '%s\n' "$EC2_KNOWN_HOSTS" | tr -d '\r' > "$ssh_dir/known_hosts"
chmod 600 "$ssh_dir/key" "$ssh_dir/known_hosts"

# Never print key material or attempt interactive passphrase prompts.
ssh-keygen -y -P '' -f "$ssh_dir/key" >/dev/null 2>&1 || fail "EC2_SSH_KEY invalida ou protegida por senha. Use uma chave de deploy dedicada, sem senha, no secret."
lookup="$EC2_HOST"
if ((10#$port != 22)); then
    lookup="[$EC2_HOST]:$((10#$port))"
fi
ssh-keygen -F "$lookup" -f "$ssh_dir/known_hosts" >/dev/null 2>&1 || fail "EC2_KNOWN_HOSTS nao contem a chave fixada para EC2_HOST e EC2_PORT. Confira o fingerprint por um canal confiavel."
ssh-keygen -l -f "$ssh_dir/known_hosts" >/dev/null 2>&1 || fail "EC2_KNOWN_HOSTS nao contem uma chave publica SSH valida."
echo "Configuracao SSH validada; nenhuma conexao ao servidor foi feita nesta etapa."
