#!/usr/bin/env python3
"""
End-to-end spot-check for the Shape conversational session API.

Covers:
  1.  Pre-flight         — health check
  2.  Session Lifecycle  — create, list, get, unauthorized access, reset, delete
  3.  Style Profile      — get defaults, update, verify persistence
  4.  Document Upload    — upload .txt file (requires LLM for topic summary)
  5.  Chat Turn          — send message, get survey, auth enforcement

Sections 4 and 5 require an LLM key. If LLM is unavailable (500 responses),
those checks are reported as WARN rather than FAIL.

Usage:
    # Start the API first:
    #   python run_chat_api.py
    #
    # Then in another terminal:
    #   python tests/scripts/e2e_chat_conversational_spot_check.py [--base-url http://localhost:8802]

Defaults to http://localhost:8802.
"""

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8802"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
SECTION = "\033[1;34m"
RESET = "\033[0m"

results: list[tuple[str, str, str]] = []  # (label, status, detail)


def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    line = f"  [{tag}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((label, "pass" if condition else "fail", detail))
    return condition


def warn(label: str, detail: str = "") -> None:
    line = f"  [{WARN}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((label, "warn", detail))


def section(title: str) -> None:
    print(f"\n{SECTION}{'='*60}{RESET}")
    print(f"{SECTION}{title}{RESET}")
    print(f"{SECTION}{'='*60}{RESET}")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_dev_token(client: httpx.Client, user_id: str) -> str | None:
    r = client.post(
        "/auth/token", json={"user_id": user_id, "api_secret": os.getenv("API_SECRET", "")}
    )
    if r.status_code == 200:
        return r.json().get("token")
    return None


# ---------------------------------------------------------------------------
# Test stages
# ---------------------------------------------------------------------------


def check_server(client: httpx.Client) -> bool:
    section("Section 1 — Pre-flight: server health")
    try:
        r = client.get("/health", timeout=5)
        ok = check("GET /health → 200", r.status_code == 200, str(r.json()))
        if ok:
            status = r.json().get("status", "")
            check("Status is healthy", status == "healthy", f"status={status!r}")
        return ok
    except httpx.ConnectError:
        check("GET /health → 200", False, "Connection refused — is the server running?")
        print("\n  Start the server with:  python run_chat_api.py\n")
        return False


def test_session_lifecycle(client: httpx.Client, token: str, token2: str) -> str | None:
    """Returns a fresh session_id for use by subsequent tests, or None on failure."""
    section("Section 2 — Session Lifecycle (no LLM)")
    headers = auth_headers(token)
    headers2 = auth_headers(token2)

    # Create session
    r = client.post("/chat/sessions", json={}, headers=headers)
    if not check("POST /chat/sessions → 201", r.status_code == 201, r.text[:120]):
        return None
    sid = r.json().get("session_id")
    check("session_id present", bool(sid), str(sid))

    # List sessions
    r = client.get("/chat/sessions", headers=headers)
    if check("GET /chat/sessions → 200", r.status_code == 200):
        ids = [s["session_id"] for s in r.json().get("sessions", [])]
        check("Created session in list", sid in ids, f"ids={ids}")

    # Get session metadata
    r = client.get(f"/chat/{sid}", headers=headers)
    if check("GET /chat/{sid} → 200", r.status_code == 200):
        data = r.json()
        check("session_id matches", data.get("session_id") == sid)
        check("user_id present", bool(data.get("user_id")))

    # Unauthorized access (different user)
    r = client.get(f"/chat/{sid}", headers=headers2)
    check("GET /chat/{sid} (wrong user) → 403", r.status_code == 403)

    # Reset session
    r = client.post(f"/chat/{sid}/reset", headers=headers)
    if check("POST /chat/{sid}/reset → 200", r.status_code == 200):
        check("reset == true", r.json().get("reset") is True)

    # Create a second session, then delete it
    r = client.post("/chat/sessions", json={}, headers=headers)
    if not check("POST /chat/sessions (2nd) → 201", r.status_code == 201, r.text[:120]):
        return sid
    sid_del = r.json()["session_id"]

    r = client.delete(f"/chat/{sid_del}", headers=headers)
    if check("DELETE /chat/{sid} → 200", r.status_code == 200):
        check("deleted == true", r.json().get("deleted") is True)

    r = client.get(f"/chat/{sid_del}", headers=headers)
    check("GET deleted session → 404 or 403", r.status_code in (404, 403))

    return sid


def test_style_profile(client: httpx.Client, token: str, sid: str) -> None:
    section("Section 3 — Style Profile (no LLM)")
    headers = auth_headers(token)

    # Get defaults
    r = client.get(f"/chat/{sid}/style", headers=headers)
    if check("GET /chat/{sid}/style → 200", r.status_code == 200):
        profile = r.json().get("style_profile", {})
        check("language default present", "language" in profile, str(profile))

    # Update language
    r = client.put(f"/chat/{sid}/style", json={"language": "nl"}, headers=headers)
    if check("PUT /chat/{sid}/style → 200", r.status_code == 200):
        updated = r.json().get("style_profile", {})
        check("language updated to 'nl'", updated.get("language") == "nl", str(updated))

    # Verify persistence
    r = client.get(f"/chat/{sid}/style", headers=headers)
    if check("GET /chat/{sid}/style (persisted) → 200", r.status_code == 200):
        persisted = r.json().get("style_profile", {})
        check("language still 'nl'", persisted.get("language") == "nl", str(persisted))


def test_document_upload(client: httpx.Client, token: str, sid: str) -> bool:
    """Returns True if LLM appears to be available (no 500 from upload)."""
    section("Section 4 — Document Upload (requires LLM for topic summary)")
    headers = auth_headers(token)

    content = b"This document covers employee satisfaction and workplace culture surveys."
    r = client.post(
        f"/chat/{sid}/upload",
        files={"file": ("survey_content.txt", content, "text/plain")},
        headers=headers,
        timeout=60,
    )

    if r.status_code == 500:
        warn(
            "POST /chat/{sid}/upload (LLM unavailable)",
            "500 returned — no LLM key configured; skipping LLM-dependent sections",
        )
        return False

    if check("POST /chat/{sid}/upload → 200", r.status_code == 200, r.text[:120]):
        data = r.json()
        check("filename present", bool(data.get("filename")), data.get("filename", ""))
        check(
            "topic_summary present",
            bool(data.get("topic_summary")),
            str(data.get("topic_summary", ""))[:80],
        )

    return r.status_code == 200


def test_chat_turn(client: httpx.Client, token: str, token2: str, sid: str) -> None:
    section("Section 5 — Chat Turn (requires LLM)")
    headers = auth_headers(token)
    headers2 = auth_headers(token2)

    # Send a simple chat message
    r = client.post(
        f"/chat/{sid}",
        json={"message": "Help me design a short employee survey."},
        headers=headers,
        timeout=60,
    )

    if r.status_code == 500:
        warn(
            "POST /chat/{sid} (LLM unavailable)",
            "500 returned — no LLM key configured",
        )
        return

    if check("POST /chat/{sid} → 200", r.status_code == 200, r.text[:120]):
        data = r.json()
        check("message non-empty", bool(data.get("message")), str(data.get("message", ""))[:80])
        check("survey_updated is boolean", isinstance(data.get("survey_updated"), bool))

    # GET current survey (may be null if LLM didn't propose one)
    r = client.get(f"/chat/{sid}/survey", headers=headers)
    if check("GET /chat/{sid}/survey → 200", r.status_code == 200):
        survey = r.json().get("survey")
        # survey may be null — that's expected
        check(
            "survey field present (may be null)",
            "survey" in r.json(),
            f"survey={'<present>' if survey else 'null'}",
        )

    # Auth enforcement: no token → 401
    r = client.post(f"/chat/{sid}", json={"message": "Hello"})
    check("POST /chat/{sid} without token → 401", r.status_code == 401)

    # Auth enforcement: wrong user → 403
    r = client.post(
        f"/chat/{sid}",
        json={"message": "Hello"},
        headers=headers2,
    )
    check("POST /chat/{sid} (wrong user) → 403", r.status_code == 403)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Shape conversational API end-to-end spot check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    args = parser.parse_args()

    print(f"\nShape conversational API spot check  →  {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if not check_server(client):
            sys.exit(1)

        section("Setup: obtain dev tokens")
        token = get_dev_token(client, "e2e_user_a")
        token2 = get_dev_token(client, "e2e_user_b")
        if not token or not token2:
            check("Dev tokens obtained", False, "Could not get dev tokens — aborting")
            sys.exit(1)
        check("Dev tokens obtained", True, "e2e_user_a + e2e_user_b")

        sid = test_session_lifecycle(client, token, token2)
        if not sid:
            print(f"\n  [{FAIL}] Session lifecycle failed — cannot continue\n")
            sys.exit(1)

        test_style_profile(client, token, sid)
        llm_ok = test_document_upload(client, token, sid)
        if llm_ok:
            test_chat_turn(client, token, token2, sid)
        else:
            section("Section 5 — Chat Turn (requires LLM)")
            warn("Skipping chat turn tests — LLM unavailable")

    # --- Final summary ---
    section("Summary")
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "pass")
    warned = sum(1 for _, s, _ in results if s == "warn")
    failed = sum(1 for _, s, _ in results if s == "fail")

    print(f"\n  {passed}/{total} checks passed", end="")
    if warned:
        print(f"  ({warned} warned, LLM not available)", end="")
    if failed:
        print(f"  ({failed} failed)")
        print("\n  Failed checks:")
        for label, status, detail in results:
            if status == "fail":
                print(f"    [{FAIL}] {label}  {detail}")
    else:
        print("  — all good!")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
