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

### Tenant Group Mapping

For multi-tenant deployments, Keycloak groups map OIDC users to tenants. The bundled realm export includes example groups (`faculty-a`, `faculty-b`) and a `group-membership` protocol mapper that injects group names into the JWT `groups` claim.

To assign a user to a tenant: Keycloak admin → **Users** → select user → **Groups** tab → add the group matching the tenant slug. See [DEPLOYMENT.md § Multi-Tenant Setup](DEPLOYMENT.md#multi-tenant-setup) for the full configuration.

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

> Normally you don't need this. The one-shot `keycloak-init` service registers the `cue-api` client's redirect URIs (for `localhost` and `PUBLIC_HOST`) automatically on every deploy, and re-applies them after a port or host change. Use the steps below only for a manual one-off change.

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

This is the one case where the explicit redirect-URI overrides *are* the right tool. `PUBLIC_HOST` derivation always produces `http://<host>:<port>/...`, which can't express `https` or a proxy on the standard port — so behind TLS termination (nginx, Caddy, etc.) set the overrides explicitly:

```
OIDC_ISSUER_URL=https://keycloak.yourdomain.com/realms/expats
OIDC_REDIRECT_URI=https://yourdomain.com/auth/callback
SHAPE_OIDC_REDIRECT_URI=https://yourdomain.com/shape/auth/callback
```

(For plain-HTTP deployments, do **not** set these — use `PUBLIC_HOST` and let them be derived; a stray value here overrides it.) The matching client redirect URIs are registered automatically by `keycloak-init`; to change them by hand use `kcadm.sh` as shown above, or Keycloak admin → **Clients** → `cue-api` → **Valid redirect URIs**.

### Persistent Keycloak Data

The realm is baked into the Keycloak image (`keycloak/Dockerfile`) and re-imported on a fresh start, so no import bind mount is needed. To also persist runtime changes (users, regenerated secrets) across container recreation, add a named volume for the embedded DB:

```yaml
keycloak:
  volumes:
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
| `PUBLIC_HOST` | _(unset)_ | Browser-facing host/IP of the server. **Set this** for non-localhost deployments — all public URLs, OIDC redirect URIs, and `KC_HOSTNAME(_ADMIN)` are derived from it. |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Keycloak admin console password (also used by the `keycloak-init` service) |
| `OIDC_ISSUER_URL` | `http://keycloak:8080/realms/expats` _(set by compose)_ | Internal URL the API uses to reach Keycloak. Leave as the `keycloak` service name under compose; the `localhost` form is only for bare-metal runs. |
| `OIDC_CLIENT_ID` | `cue-api` | OIDC client id |
| `OIDC_CLIENT_SECRET` | — | Client secret (regenerate from Keycloak admin) |
| `OIDC_REDIRECT_URI` | _(derived from `PUBLIC_HOST`)_ | **Optional override** — normally leave unset; takes precedence over `PUBLIC_HOST`, so a stray value pins logins to it. Set only for HTTPS / reverse-proxy URLs. |
| `SHAPE_OIDC_REDIRECT_URI` | _(derived from `PUBLIC_HOST`)_ | **Optional override** for the Shape callback. Same caveat as above. |
| `KEYCLOAK_PUBLIC_URL` | _(derived from `PUBLIC_HOST`)_ | Optional override for the browser-facing Keycloak base URL. |
| `KC_HOSTNAME_ADMIN` | `http://${PUBLIC_HOST}:8080` | Admin-console redirect hostname; derived from `PUBLIC_HOST`. |
