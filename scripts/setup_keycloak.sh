#!/usr/bin/env bash
set -euo pipefail

ADMIN_PASSWORD="${1:-}"
if [ -z "$ADMIN_PASSWORD" ]; then
  echo "Usage: $0 <keycloak-admin-password> [public-host]"
  echo "  Registers redirect URIs in Keycloak for non-localhost deployments."
  echo "  public-host defaults to PUBLIC_HOST from .env if not provided."
  exit 1
fi

HOST="${2:-}"
if [ -z "$HOST" ]; then
  if [ -f .env ]; then
    HOST=$(grep -E '^PUBLIC_HOST=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
  fi
fi

if [ -z "$HOST" ]; then
  echo "Error: No public host specified."
  echo "  Either pass it as the second argument or set PUBLIC_HOST in .env"
  exit 1
fi

KCADM="docker compose exec keycloak /opt/keycloak/bin/kcadm.sh"

echo "Authenticating with Keycloak..."
$KCADM config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password "$ADMIN_PASSWORD"

echo "Looking up clients in 'expats' realm..."
CLIENT_IDS=$($KCADM get clients -r expats --fields id,clientId 2>/dev/null)

CUE_CLIENT_ID=$(echo "$CLIENT_IDS" | python3 -c "
import json, sys
for c in json.load(sys.stdin):
    if c['clientId'] == 'cue-api':
        print(c['id'])
        break
")

if [ -z "$CUE_CLIENT_ID" ]; then
  echo "Error: cue-api client not found in Keycloak."
  exit 1
fi

echo "Found cue-api client: $CUE_CLIENT_ID"
echo "Registering redirect URIs for host: $HOST"

$KCADM update "clients/$CUE_CLIENT_ID" \
  -r expats \
  -s "redirectUris=[
    \"http://localhost:8811/auth/callback\",
    \"http://localhost:8812/auth/callback\",
    \"http://${HOST}:8811/auth/callback\",
    \"http://${HOST}:8812/auth/callback\"
  ]" \
  -s "webOrigins=[
    \"http://localhost:8801\",
    \"http://localhost:8811\",
    \"http://localhost:8802\",
    \"http://localhost:8812\",
    \"http://${HOST}:8801\",
    \"http://${HOST}:8811\",
    \"http://${HOST}:8802\",
    \"http://${HOST}:8812\"
  ]" \
  -s "attributes.\"post.logout.redirect.uris\"=\"http://localhost:8811##http://localhost:8812##http://${HOST}:8811##http://${HOST}:8812\""

echo "Done. Redirect URIs registered for localhost and $HOST."
echo "No restart needed - Keycloak applies changes immediately."
