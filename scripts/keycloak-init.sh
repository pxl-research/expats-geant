#!/usr/bin/env bash
# Idempotent Keycloak client configuration, run as a one-shot sidecar on every
# stack deploy (see the `keycloak-init` service in docker-compose.yml).
#
# Why this exists:
#   - The realm in keycloak/realm-export.json is only imported on Keycloak's
#     FIRST start. On an existing volume, editing that file changes nothing.
#   - setup_keycloak.sh registers redirect URIs from the host via
#     `docker compose exec`, which is awkward/impossible from a Portainer UI.
#
# This script runs INSIDE a Keycloak image (kcadm.sh + bash available, but no
# python3), talks to the keycloak service over the compose network, and sets
# the cue-api client's redirect URIs / web origins to the current ports for
# both localhost and ${PUBLIC_HOST}. Safe to run repeatedly.
set -euo pipefail

KCADM=/opt/keycloak/bin/kcadm.sh
SERVER="${KC_INIT_SERVER:-http://keycloak:8080}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
HOST="${PUBLIC_HOST:-}"

CUE_PORT=8801
SHAPE_PORT=8802
CUE_UI_PORT=8811
SHAPE_UI_PORT=8812

echo "[keycloak-init] waiting for Keycloak admin at ${SERVER} ..."
for i in $(seq 1 60); do
  if "$KCADM" config credentials --server "$SERVER" --realm master \
      --user "$ADMIN_USER" --password "$ADMIN_PASS" >/dev/null 2>&1; then
    echo "[keycloak-init] authenticated."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "[keycloak-init] ERROR: Keycloak admin never became reachable." >&2
    exit 1
  fi
  sleep 5
done

echo "[keycloak-init] waiting for 'expats' realm + cue-api client (realm import) ..."
CID=""
for i in $(seq 1 60); do
  CID=$("$KCADM" get clients -r expats -q clientId=cue-api --fields id 2>/dev/null \
    | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
    | head -1 || true)
  [ -n "$CID" ] && break
  if [ "$i" -eq 60 ]; then
    echo "[keycloak-init] ERROR: cue-api client not found in 'expats' realm." >&2
    exit 1
  fi
  sleep 5
done
echo "[keycloak-init] found cue-api client: ${CID}"

REDIRECTS="\"http://localhost:${CUE_UI_PORT}/auth/callback\",\"http://localhost:${SHAPE_UI_PORT}/auth/callback\""
ORIGINS="\"http://localhost:${CUE_PORT}\",\"http://localhost:${CUE_UI_PORT}\",\"http://localhost:${SHAPE_PORT}\",\"http://localhost:${SHAPE_UI_PORT}\""
LOGOUT="http://localhost:${CUE_UI_PORT}##http://localhost:${SHAPE_UI_PORT}"

if [ -n "$HOST" ]; then
  REDIRECTS="${REDIRECTS},\"http://${HOST}:${CUE_UI_PORT}/auth/callback\",\"http://${HOST}:${SHAPE_UI_PORT}/auth/callback\""
  ORIGINS="${ORIGINS},\"http://${HOST}:${CUE_PORT}\",\"http://${HOST}:${CUE_UI_PORT}\",\"http://${HOST}:${SHAPE_PORT}\",\"http://${HOST}:${SHAPE_UI_PORT}\""
  LOGOUT="${LOGOUT}##http://${HOST}:${CUE_UI_PORT}##http://${HOST}:${SHAPE_UI_PORT}"
  echo "[keycloak-init] registering redirect URIs for localhost and ${HOST}"
else
  echo "[keycloak-init] PUBLIC_HOST unset — registering localhost redirect URIs only"
fi

"$KCADM" update "clients/${CID}" -r expats \
  -s "redirectUris=[${REDIRECTS}]" \
  -s "webOrigins=[${ORIGINS}]" \
  -s "attributes.\"post.logout.redirect.uris\"=\"${LOGOUT}\""

echo "[keycloak-init] done. cue-api redirect URIs updated; Keycloak applies changes immediately."
