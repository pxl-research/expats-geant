# Custom Keycloak image: bakes the realm export and the init script INTO the
# image so no host bind mounts are needed. This is what makes deployment work
# on hosts that only have the pushed image and none of the repo files (e.g.
# Portainer stacks deployed from prebuilt images).
#
# Build context is the repo root:
#   docker build -f keycloak/Dockerfile -t <registry>/expats-keycloak:latest .
FROM quay.io/keycloak/keycloak:26.0

# Realm import: Keycloak imports any *.json here on `start-dev --import-realm`.
COPY keycloak/realm-export.json /opt/keycloak/data/import/realm-export.json

# Redirect-URI init script, run by the one-shot keycloak-init service.
COPY scripts/keycloak-init.sh /opt/keycloak/bin/keycloak-init.sh
