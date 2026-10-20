#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="${SCRIPT_DIR}/../secrets"

APP_UID="${APP_UID:-1000}"
APP_GID="${APP_GID:-1000}"

PRIVATE_KEY="${SECRETS_DIR}/jwe_private.pem"
PUBLIC_KEY="${SECRETS_DIR}/jwe_public.pem"

mkdir -p "${SECRETS_DIR}"

if [[ -f "${PRIVATE_KEY}" && "${1:-}" != "--force" ]]; then
    echo "Chaves já existem em ${SECRETS_DIR}. Use --force para sobrescrever."
    echo "Reaplicando apenas dono e permissões..."
else
    openssl genpkey \
        -algorithm RSA \
        -pkeyopt rsa_keygen_bits:3072 \
        -out "${PRIVATE_KEY}"

    openssl rsa -in "${PRIVATE_KEY}" -pubout -out "${PUBLIC_KEY}"

    echo "Par de chaves gerado em ${SECRETS_DIR}."
fi

chmod 600 "${PRIVATE_KEY}"
chmod 644 "${PUBLIC_KEY}"

if [[ "$(id -u)" -eq 0 ]]; then
    chown "${APP_UID}:${APP_GID}" "${PRIVATE_KEY}" "${PUBLIC_KEY}"
elif [[ "$(stat -c '%u' "${PRIVATE_KEY}")" != "${APP_UID}" ]]; then
    echo "Ajustando dono para ${APP_UID}:${APP_GID} (requer sudo)..."
    sudo chown "${APP_UID}:${APP_GID}" "${PRIVATE_KEY}" "${PUBLIC_KEY}"
fi

echo "Dono e permissões ajustados para UID ${APP_UID}, GID ${APP_GID}."
