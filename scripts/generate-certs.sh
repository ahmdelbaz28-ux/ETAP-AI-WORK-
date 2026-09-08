#!/usr/bin/env bash
# =============================================================================
# AhmedETAP Platform — TLS Certificate Generation Script
# =============================================================================
set -euo pipefail

SSL_DIR="${SSL_DIR:-./ssl}"
mkdir -p "$SSL_DIR"

KEY_FILE="$SSL_DIR/etap.key"
CERT_FILE="$SSL_DIR/etap.crt"
DAYS="${DAYS:-365}"
# C1: RSA 4096 (production-grade encryption, hardened from legacy 2048)
RSA_BITS=4096

echo "[INFO] Generating self-signed TLS certificate (RSA ${RSA_BITS})..."
openssl req -x509 -nodes -days "$DAYS" -newkey "rsa:${RSA_BITS}" \
  -keyout "$KEY_FILE" -out "$CERT_FILE" \
  -subj "/C=US/ST=State/L=City/O=AhmedETAP/OU=Engineering/CN=localhost"

chmod 600 "$KEY_FILE" 2>/dev/null || true
chmod 644 "$CERT_FILE" 2>/dev/null || true

echo "[INFO] TLS certificate generated successfully in $SSL_DIR (RSA ${RSA_BITS})"
