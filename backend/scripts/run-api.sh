#!/usr/bin/env bash
# Sobe a API real (Claude) lendo a chave do Keychain do macOS.
# A chave nunca é impressa nem gravada em arquivo do projeto.
#
# Uso (a partir de qualquer pasta):   backend/scripts/run-api.sh
# Guardar a chave uma única vez, no seu terminal (o -w sem valor PEDE a chave sem ecoar
# e sem deixá-la no histórico do shell):
#   security add-generic-password -a "$USER" -s skillgap-anthropic-key -w
# Trocar depois: repita com -U   (security add-generic-password -U -a "$USER" -s skillgap-anthropic-key -w)
# Remover:       security delete-generic-password -a "$USER" -s skillgap-anthropic-key
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${ANTHROPIC_API_KEY:-}" ] && command -v security >/dev/null 2>&1; then
  ANTHROPIC_API_KEY="$(security find-generic-password -a "$USER" -s skillgap-anthropic-key -w 2>/dev/null || true)"
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY não encontrada (nem no ambiente, nem no Keychain)." >&2
  echo "Guarde-a com:  security add-generic-password -a \"\$USER\" -s skillgap-anthropic-key -w" >&2
  exit 1
fi
export ANTHROPIC_API_KEY

# shellcheck disable=SC1091
source .venv/bin/activate
# 127.0.0.1: a API só é acessível a partir desta máquina (sem autenticação própria).
exec uvicorn skillgap.api:create_app --factory --host 127.0.0.1 --port "${PORT:-8000}"
