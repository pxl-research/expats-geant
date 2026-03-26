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

### Change the Client Secret

The default client secret in `keycloak/realm-export.json` is `change-me`. Update it before production:

1. Keycloak admin → **Clients** → `cue-api` → **Credentials** → **Regenerate**
2. Update `OIDC_CLIENT_SECRET` in your `.env`

### Use HTTPS

Configure TLS termination at your reverse proxy (nginx, Caddy, etc.) and update the realm redirect URIs:

```
OIDC_ISSUER_URL=https://keycloak.yourdomain.com/realms/expats
OIDC_REDIRECT_URI=https://cue-api.yourdomain.com/auth/callback
```

Update the client redirect URI in Keycloak admin → **Clients** → `cue-api` → **Valid redirect URIs**.

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
| `OIDC_REDIRECT_URI` | — | `http://localhost:8001/auth/callback` |
