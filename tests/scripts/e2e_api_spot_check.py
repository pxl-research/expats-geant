#!/usr/bin/env python3
"""
End-to-end spot-check for the M-Autofill API.

Covers:
  6.1  Happy-path flow  — upload docs, suggest answers, audit report, cleanup
  6.2  Performance      — response times and file-size handling
  6.3  Security         — missing/invalid/expired tokens, session isolation

Usage:
    # Start the API first:
    #   python run_api.py
    #
    # Then in another terminal:
    #   python scripts/e2e_api_spot_check.py [--base-url http://localhost:8001]

Defaults to http://localhost:8001.
"""

import argparse
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8001"

DATA_DIR = Path(__file__).parent.parent / "test_data" / "internship" / "data"
DATA_FILES = [
    DATA_DIR / "BachelorProject_gids_TIN.pdf",
    DATA_DIR / "Briefing voor aanvang stage 1.pptx",
    DATA_DIR / "Eerste Briefing Stage Semester1.pptx",
]

# A representative sample from the FAQ list
QUESTIONS = [
    "Hoeveel dagen per week mag ik remote werken tijdens mijn stage?",
    "Wanneer start en stopt mijn stage?",
    "Mag ik mijn eindwerk ook in het Engels schrijven?",
    "Hoe lang moet mijn presentatie tijdens het juryexamen duren?",
    "Voor hoeveel telt elk onderdeel van het Bachelor Project mee in het eindtotaal?",
    "Hoeveel woorden moet ik minimum opnemen in de definitieve versie van mijn eindwerk?",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
SECTION = "\033[1;34m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []  # (label, passed, detail)


def check(label: str, condition: bool, detail: str = "") -> bool:
    tag = PASS if condition else FAIL
    line = f"  [{tag}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)
    results.append((label, condition, detail))
    return condition


def section(title: str) -> None:
    print(f"\n{SECTION}{'='*60}{RESET}")
    print(f"{SECTION}{title}{RESET}")
    print(f"{SECTION}{'='*60}{RESET}")


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test stages
# ---------------------------------------------------------------------------


def check_server(client: httpx.Client) -> bool:
    section("Pre-flight: server health")
    try:
        r = client.get("/health", timeout=5)
        return check("GET /health → 200", r.status_code == 200, str(r.json()))
    except httpx.ConnectError:
        check("GET /health → 200", False, "Connection refused — is the server running?")
        print("\n  Start the server with:  python run_api.py\n")
        return False


def get_dev_token(client: httpx.Client, user_id: str = "test_user") -> str | None:
    r = client.post("/dev/token", json={"user_id": user_id, "org": "pxl", "roles": ["respondent"]})
    if check(f"POST /dev/token ({user_id}) → 200", r.status_code == 200, ""):
        token = r.json().get("token", "")
        check("Token non-empty", bool(token))
        return token
    check("Token non-empty", False, r.text)
    return None


def test_security(client: httpx.Client) -> None:
    section("6.3  Security checks")

    # No Authorization header
    r = client.get("/session/stats")
    check("No token → 401", r.status_code == 401)

    r = client.post("/upload", files={"file": ("test.txt", b"hello", "text/plain")})
    check("Upload without token → 401", r.status_code == 401)

    # Malformed token
    r = client.get("/session/stats", headers={"Authorization": "Bearer not.a.real.token"})
    check("Malformed token → 401", r.status_code == 401)

    # Wrong scheme
    r = client.get("/session/stats", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    check("Basic auth scheme → 401", r.status_code == 401)


def test_session_isolation(client: httpx.Client, token_a: str, token_b: str) -> None:
    section("6.3  Session isolation")

    # User B should see their own (empty) session, not User A's data
    r = client.get("/session/stats", headers=auth_headers(token_b))
    if check("User B GET /session/stats → 200", r.status_code == 200):
        doc_count = r.json().get("document_count", -1)
        check(
            "User B sees 0 documents (not User A's)",
            doc_count == 0,
            f"document_count={doc_count}",
        )

    # User B's suggest call should return "no documents" response, not User A's answers
    r = client.post(
        "/suggest",
        json={"question": "Wanneer start en stopt mijn stage?"},
        headers=auth_headers(token_b),
    )
    if check("User B POST /suggest → 200", r.status_code == 200):
        answer = r.json().get("answer", "")
        no_docs = "couldn't find" in answer.lower() or "no relevant" in answer.lower()
        check(
            "User B gets 'no documents' answer (not User A's data)",
            no_docs,
            f'answer starts with: "{answer[:80]}"',
        )


def test_happy_path(client: httpx.Client, token: str) -> None:
    section("6.1  Happy path — upload → suggest → audit → cleanup")
    headers = auth_headers(token)

    # --- Upload documents ---
    print("\n  Uploading documents...")
    uploaded = []
    for file_path in DATA_FILES:
        if not file_path.exists():
            check(f"Upload {file_path.name}", False, "File not found")
            continue
        suffix = file_path.suffix.lower()
        mime = {
            ".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(suffix, "application/octet-stream")

        with open(file_path, "rb") as f:
            t0 = time.perf_counter()
            r = client.post(
                "/upload",
                files={"file": (file_path.name, f, mime)},
                headers=headers,
                timeout=60,
            )
            elapsed = time.perf_counter() - t0

        ok = r.status_code == 200
        check(
            f"Upload {file_path.name}",
            ok,
            f"{elapsed:.1f}s  {file_path.stat().st_size // 1024} KB" if ok else r.text[:120],
        )
        if ok:
            uploaded.append(file_path.name)

    check(
        f"All {len(DATA_FILES)} files uploaded",
        len(uploaded) == len(DATA_FILES),
        f"uploaded: {uploaded}",
    )

    # --- Session stats after upload ---
    r = client.get("/session/stats", headers=headers)
    if check("GET /session/stats → 200", r.status_code == 200):
        stats = r.json()
        check(
            "document_count matches uploads",
            stats.get("document_count", 0) == len(uploaded),
            f"document_count={stats.get('document_count')}",
        )

    # --- Answer suggestions ---
    print("\n  Requesting suggestions...")
    timings = []
    for question in QUESTIONS:
        t0 = time.perf_counter()
        r = client.post("/suggest", json={"question": question}, headers=headers, timeout=60)
        elapsed = time.perf_counter() - t0
        timings.append(elapsed)

        if check(f'Suggest "{question[:55]}..." → 200', r.status_code == 200, f"{elapsed:.1f}s"):
            body = r.json()
            has_answer = bool(body.get("answer", "").strip())
            has_citations = len(body.get("citations", [])) > 0
            check("  Has non-empty answer", has_answer, body.get("answer", "")[:80])
            check("  Has citations", has_citations, f"{len(body.get('citations', []))} citation(s)")

    # --- Performance summary ---
    section("6.2  Performance summary")
    for q, t in zip(QUESTIONS, timings, strict=False):
        status = PASS if t < 10 else WARN
        print(f"  [{status}] {t:.2f}s  {q[:65]}")
    avg = sum(timings) / len(timings) if timings else 0
    check("Average suggestion time < 10s", avg < 10, f"avg={avg:.2f}s")
    check("All suggestions < 15s", all(t < 15 for t in timings), f"max={max(timings):.2f}s")

    # --- Audit report ---
    section("6.1  Audit report")
    r = client.get("/audit-report", headers=headers, timeout=30)
    if check("GET /audit-report (json) → 200", r.status_code == 200):
        report = r.json()
        summary = report.get("summary", {})
        check(
            "Audit: documents_uploaded matches",
            summary.get("documents_uploaded", 0) == len(uploaded),
            str(summary),
        )
        check(
            "Audit: suggestions_generated matches",
            summary.get("suggestions_generated", 0) == len(QUESTIONS),
            str(summary),
        )

    r = client.get("/audit-report?format=plaintext", headers=headers, timeout=30)
    check("GET /audit-report (plaintext) → 200", r.status_code == 200)
    if r.status_code == 200:
        check("Plaintext report non-empty", len(r.text) > 100, f"{len(r.text)} chars")

    # --- Privacy endpoint ---
    r = client.get("/privacy")
    check("GET /privacy → 200", r.status_code == 200)
    check("Privacy statement non-empty", len(r.text) > 100)

    # --- GDPR: delete audit report ---
    r = client.delete("/audit-report", headers=headers)
    check("DELETE /audit-report → 200", r.status_code == 200)

    # Confirm it's gone
    r = client.get("/audit-report", headers=headers)
    check("GET /audit-report after deletion → 404", r.status_code == 404)

    # --- Session cleanup ---
    r = client.delete("/session", headers=headers)
    if check("DELETE /session → 200", r.status_code == 200):
        check("Session deleted=true", r.json().get("deleted") is True)

    # After session delete the middleware auto-creates a fresh session on the next
    # authenticated request (by design), so we expect 200 with document_count=0.
    r = client.get("/session/stats", headers=headers)
    if check("GET /session/stats after delete → 200 (new session)", r.status_code == 200):
        check("New session has 0 documents", r.json().get("document_count") == 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="M-Autofill API end-to-end spot check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    args = parser.parse_args()

    print(f"\nM-Autofill API spot check  →  {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if not check_server(client):
            sys.exit(1)

        # Security: no state needed, run first
        test_security(client)

        # Get two independent tokens for isolation test
        section("Setup: obtain dev tokens")
        token_a = get_dev_token(client, user_id="user_a")
        token_b = get_dev_token(client, user_id="user_b")

        if not token_a or not token_b:
            print(f"\n  [{FAIL}] Could not obtain dev tokens — aborting\n")
            sys.exit(1)

        # Happy path runs on user_a's session (uploads docs, asks questions, etc.)
        test_happy_path(client, token_a)

        # Isolation: user_b's fresh session should not see user_a's documents
        test_session_isolation(client, token_a, token_b)

        # Clean up user_b's session
        client.delete("/session", headers=auth_headers(token_b))

    # --- Final summary ---
    section("Summary")
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print(f"\n  {passed}/{total} checks passed", end="")
    if failed:
        print(f"  ({failed} failed)")
        print("\n  Failed checks:")
        for label, ok, detail in results:
            if not ok:
                print(f"    [{FAIL}] {label}  {detail}")
    else:
        print("  — all good!")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
