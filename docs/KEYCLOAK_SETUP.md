# Keycloak Setup Guide

This guide covers optional federation and production hardening for the bundled Keycloak instance.

## Quick Start

The bundled Keycloak service (in `docker-compose.yml`) auto-imports the `expats` realm from `keycloak/realm-export.json` on first startup. No manual configuration is required for local development.

```bash
docker-compose up
# Keycloak available at: http://localhost:8080
# Admin console:         http://localhost:8080/admin  (admin / admin)
# Realm:                 expats
# Client:                cue-api  (secret: change-me)
```

**Change the admin password** before exposing Keycloak publicly:

```bash
# .env
KEYCLOAK_ADMIN_PASSWORD=strong-random-password
```

---

## Federating External Identity Providers

Keycloak can federate with external providers, allowing users to log in with their existing institutional or social accounts. All federation is configured in the Keycloak admin console under **Identity Providers**.

### Google

1. Create OAuth credentials at <https://console.cloud.google.com/apis/credentials>
   - Authorized redirect URI: `http://localhost:8080/realms/expats/broker/google/endpoint`
2. In Keycloak admin → **Identity Providers** → **Add provider** → **Google**
3. Enter Client ID and Client Secret from Google Console
4. Save — users now see "Login with Google" on the Keycloak login page

### Microsoft / Azure AD

1. Register an app at <https://portal.azure.com> → **App registrations**
   - Redirect URI: `http://localhost:8080/realms/expats/broker/microsoft/endpoint`
2. In Keycloak admin → **Identity Providers** → **Add provider** → **Microsoft**
3. Enter Application (client) ID and client secret
4. Save

### LDAP / Active Directory

1. In Keycloak admin → **User Federation** → **Add LDAP provider**
2. Configure connection URL, bind credentials, user search base
3. Enable periodic sync
4. Map LDAP attributes to Keycloak profile fields as needed

---

## Production Hardening

### Password Policy

The bundled realm configures a NIST-aligned password policy: minimum 12 characters, cannot match username or email. This is applied on first Keycloak import via `realm-export.json`.

For existing deployments (realm already imported), apply the policy manually:

1. Keycloak admin → **Realm Settings** → **Authentication** → **Password Policy**
2. Add policies: `length(12)`, `notUsername`, `notEmail`
3. Save

### Multi-Factor Authentication (MFA)

TOTP-based MFA is pre-configured as opt-in: users can enable it from their Keycloak account settings. This is applied on first import via `realm-export.json`.

To make MFA mandatory for all users:

1. Keycloak admin → **Authentication** → **Required Actions**
2. Set **Configure OTP** to **Default Action** (checked)
3. All users will be prompted to set up TOTP on next login

### Change the Client Secret

The default client secret in `keycloak/realm-export.json` is `change-me`. Update it before production:

1. Keycloak admin → **Clients** → `cue-api` → **Credentials** → **Regenerate**
2. Update `OIDC_CLIENT_SECRET` in your `.env`

### Updating Redirect URIs Without Browser Access

The Keycloak admin console redirects to `http://keycloak:8080/admin/` (Docker-internal), which is not reachable from an external browser. Use the admin CLI from inside the container instead:

```bash
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin --password <password>

docker compose exec keycloak /opt/keycloak/bin/kcadm.sh get clients -r expats \
  --fields id,clientId   # note the id of cue-api

docker compose exec keycloak /opt/keycloak/bin/kcadm.sh update clients/<CLIENT_ID> \
  -r expats \
  -s 'redirectUris=[...]' \
  -s 'webOrigins=[...]' \
  -s 'attributes."post.logout.redirect.uris"="[...]"'
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full non-localhost deployment walkthrough.

### Use HTTPS

Configure TLS termination at your reverse proxy (nginx, Caddy, etc.) and update the realm redirect URIs:

```
OIDC_ISSUER_URL=https://keycloak.yourdomain.com/realms/expats
OIDC_REDIRECT_URI=https://yourdomain.com:8002/auth/callback
```

Update the client redirect URI using `kcadm.sh` as shown above, or via Keycloak admin → **Clients** → `cue-api` → **Valid redirect URIs**.

### Persistent Keycloak Data

Add a named volume in `docker-compose.yml` to persist realm configuration across container restarts:

```yaml
keycloak:
  volumes:
    - ./keycloak:/opt/keycloak/data/import
    - keycloak_data:/opt/keycloak/data/h2   # persist embedded DB

volumes:
  keycloak_data:
    driver: local
```

For production use a dedicated PostgreSQL database instead of the embedded H2.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Keycloak admin console password |
| `OIDC_ISSUER_URL` | — | Keycloak realm URL, e.g. `http://localhost:8080/realms/expats` |
| `OIDC_CLIENT_ID` | — | `cue-api` |
| `OIDC_CLIENT_SECRET` | — | Client secret (regenerate from Keycloak admin) |
| `OIDC_REDIRECT_URI` | `http://localhost:8002/auth/callback` | Where Keycloak sends the browser after cue login |
| `SHAPE_OIDC_REDIRECT_URI` | `http://localhost:8004/auth/callback` | Where Keycloak sends the browser after shape login |
| `KEYCLOAK_PUBLIC_URL` | — | Public browser-accessible base URL of Keycloak (e.g. `http://10.0.0.1:8080`); rewrites the internal hostname in OIDC redirects |
| `KC_HOSTNAME_ADMIN` | `http://keycloak:8080` | Hostname used for admin console redirects; set to your server URL for external access |
