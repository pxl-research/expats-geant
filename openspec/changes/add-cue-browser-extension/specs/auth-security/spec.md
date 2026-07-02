## ADDED Requirements

### Requirement: Extension-Origin CORS Allow-List

The system SHALL accept a configurable allow-list of browser-extension origins
for CORS preflight and credentialed requests. The allow-list SHALL be sourced
from an environment variable (e.g. `EXTENSION_ALLOWED_ORIGINS`) as a
comma-separated list of complete origins such as
`chrome-extension://<extension-id>` and `moz-extension://<extension-uuid>`. The
default value SHALL be empty — operators opt in per deployment.

The CORS configuration SHALL NOT allow wildcard extension schemes (no
`chrome-extension://*` style entries). The system SHALL log a warning at
startup if `EXTENSION_ALLOWED_ORIGINS` contains a wildcard or malformed entry
and SHALL exclude that entry from the active allow-list.

Allowed extension origins SHALL be permitted to send credentialed requests
(Authorization headers carrying a JWT) and SHALL receive the same CORS headers
as allowed `cue_ui/` and `shape_ui/` origins.

#### Scenario: Origin in allow-list accepted

- **WHEN** the operator sets `EXTENSION_ALLOWED_ORIGINS` to a specific
  `chrome-extension://...` origin
- **AND** a preflight `OPTIONS` request arrives from that origin
- **THEN** the response includes `Access-Control-Allow-Origin` echoing the
  origin
- **AND** `Access-Control-Allow-Credentials: true`

#### Scenario: Origin not in allow-list rejected

- **WHEN** a request arrives from an extension origin not present in
  `EXTENSION_ALLOWED_ORIGINS`
- **THEN** the response omits CORS allow headers
- **AND** the browser blocks the request client-side

#### Scenario: Empty allow-list is the default

- **WHEN** `EXTENSION_ALLOWED_ORIGINS` is unset or empty
- **THEN** no extension origin is permitted
- **AND** `cue_ui/` and `shape_ui/` CORS behaviour is unaffected

#### Scenario: Wildcard extension origin rejected at startup

- **WHEN** `EXTENSION_ALLOWED_ORIGINS` contains an entry like
  `chrome-extension://*`
- **THEN** the system logs a warning identifying the rejected entry
- **AND** the wildcard entry is not added to the active allow-list

#### Scenario: Credentialed extension request authorised

- **WHEN** an allowed extension origin sends an authenticated request with
  `Authorization: Bearer <jwt>` to a Cue endpoint
- **THEN** the JWT is validated through the existing token-validation flow
- **AND** the response includes the credentialed-CORS headers required for the
  browser to expose the response to the extension
