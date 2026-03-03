# Authentication Options

This document summarises the authentication approaches considered for this project,
their trade-offs, and the open questions that need a decision.

## Decision

**Chosen approach: Self-hosted Keycloak (Option 2), bundled in docker-compose.**

Keycloak runs as part of the standard stack (`docker-compose up`) with a pre-configured
realm, self-registration enabled, and no required operator setup. Federation with external
providers (Google, Microsoft, institutional SSO) is supported as an optional operator
configuration step via Keycloak's admin panel — no app code changes needed.

Rationale:
- Others deploy their own instances → no central SaaS dependency
- Must work standalone → bundled Keycloak covers this
- EU data only → fully self-hosted, nothing leaves the operator's infrastructure
- Low operator burden → zero-config out of the box, optional federation when needed
- No user account management on our end → self-registration handles it

## Context

The app needs to identify users to enforce session isolation — i.e. user A cannot
see user B's documents or suggestions. Beyond that, we have no user management
requirements: no roles, no profiles, no admin panel.

The app is expected to run as part of a larger platform (e.g. a questionnaire tool
or educational infrastructure), which may already have its own auth system.

---

## Option 1: OIDC with an External Provider (Google, Microsoft, GitHub, …)

**How it works:**
Users click "Sign in with Google" (or Microsoft, etc.). The provider verifies their
identity and hands your app a token. No account creation needed — users log in with
something they already have.

**What we need:**

- Register the app with each provider (Google Cloud Console, Azure portal, etc.)
- Each deployment of the app needs its own registration and credentials
- One-time setup per deployment, ~15 minutes per provider

**Pros:**

- No user management on our end
- Users need no new account
- Well-understood, widely trusted

**Cons:**

- Every operator who deploys their own instance must register with each provider
- Dependency on external services (Google, Microsoft)
- Overkill if the host platform already handles auth

**Best fit:** A centrally hosted instance where we control deployment.

---

## Option 2: Self-Hosted Identity Provider (Keycloak)

**How it works:**
We run our own login service (Keycloak). It handles usernames, passwords, MFA, and
can optionally connect to Google/Microsoft on our behalf. Our app only talks to
Keycloak, not to external providers directly.

**What we need:**

- A server to run Keycloak on (Docker-based, manageable)
- Initial setup: create a realm, configure clients
- Optional: connect Keycloak to Google/Microsoft for social login

**Pros:**

- Full control — user data stays within our infrastructure
- GDPR-friendly (EU data locality)
- Register with Google/Microsoft once (in Keycloak), not once per deployment
- Can support institutional SSO (university LDAP, Shibboleth, etc.)

**Cons:**

- We own and operate the infrastructure
- Extra service to maintain and keep secure
- Still requires user accounts (either managed by us or federated)

**Best fit:** Projects with strong data sovereignty requirements, or where we want
to support institutional logins centrally.

---

## Option 3: Auth SaaS Middleman (Clerk, Supabase Auth, Firebase Auth)

**How it works:**
A managed service acts as a middleman. We register once with them; they handle
connections to Google, Microsoft, magic links, etc. Users get familiar login options,
we get a stable user ID.

**What we need:**

- Account with the chosen SaaS provider
- API key in our configuration
- Possibly a small monthly fee depending on user volume

**Pros:**

- Register with Google/Microsoft once, not once per deployment
- No infrastructure to run
- Pre-built login UI available
- Handles magic links, social login, MFA — all from one service

**Cons:**

- Dependency on a third-party SaaS (availability, pricing, data processing)
- GDPR considerations (data processed outside EU depending on provider)
- Every deployment still points to our account, or each operator needs their own

**Best fit:** Rapid prototyping, or projects comfortable with managed services.

---

## Option 4: Magic Links (Passwordless Email)

**How it works:**
The user enters their email address. The app sends them a one-time login link.
Clicking the link logs them in — no password, no external provider. Their email
address becomes their stable user ID.

**What we need:**

- An email sending service (e.g. Resend, SendGrid, Mailgun — free tiers available)
  or the deployer's own SMTP server (common in institutional environments)

**Pros:**

- No external provider registration per deployment
- No new account — just an email address the user already has
- Simple to implement and explain to users
- Works well in institutional settings (everyone has an institutional email)

**Cons:**

- Requires email infrastructure (but most institutions already have this)
- Slightly more friction than "Sign in with Google" for end users
- Login link can be forwarded (low risk for this use case)

**Best fit:** Projects embedded in institutional infrastructure where email is
already available and social login is not a priority.

---

## Option 5: Trust the Host Platform's Token (Embedded / LTI)

**How it works:**
The host platform (questionnaire tool, LMS, etc.) already knows who the user is.
When it launches our app, it passes a signed token containing the user ID. Our app
verifies the signature and trusts the identity — no separate login step at all.

This is how educational tools standardly integrate with platforms like Moodle,
Canvas, and Blackboard via the **LTI** (Learning Tools Interoperability) standard.

**What we need:**

- Agreement with the host platform on a token format and shared signing secret
  (or our public key for them to verify against)
- If LTI: implement the LTI 1.3 handshake (existing libraries available)
- If custom: define a simple JWT contract with the host platform team

**Pros:**

- Zero friction for users — they are already logged in to the host platform
- No auth infrastructure on our side at all
- Natural fit if this app is always launched from within another platform
- LTI is an established standard in education — many platforms support it already

**Cons:**

- Requires cooperation from the host platform
- Less suitable if the app is also used standalone (outside a host platform)
- LTI has some implementation complexity (though libraries help)

**Best fit:** App is always embedded in a known host platform (Moodle, Canvas,
a custom questionnaire tool, etc.).

---

## Comparison Summary

| Option | User needs new account? | We manage users? | Infra to run? | Per-deployment setup? | Standalone use? |
|--------|------------------------|-----------------|---------------|----------------------|-----------------|
| OIDC / External providers | No | No | No | Yes (register per deploy) | Yes |
| Self-hosted Keycloak | No (if federated) | Optional | Yes | No (register once) | Yes |
| Auth SaaS (Clerk etc.) | No | No | No | Depends on model | Yes |
| Magic links | No (email only) | No | Email service | No | Yes |
| Host platform token / LTI | No | No | No | Agreement with host | Only if embedded |

---

## Open Questions for the Team

1. **Deployment model:** Will there be one central instance (we operate it), or will
   others deploy their own instances? -> others will deploy their own

2. **Host platform:** Is there a known host platform this will always run inside?
   If yes, LTI or a token contract is likely the cleanest solution. -> no

3. **Standalone use:** Does the app need to work outside a host platform context?

4. **Data sovereignty:** Are there requirements around where user identity data is
   processed (e.g. EU-only)? -> EU only

5. **Operator burden:** How much setup complexity is acceptable for someone deploying
   their own instance?
