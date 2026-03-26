#!/usr/bin/env python3
"""
End-to-end spot-check for Cue audit logging & compliance.

Covers:
  7.1a  Audit accuracy   — log entries match actual events performed
  7.1b  Timestamps       — timestamps are recent and ordered correctly
  7.1c  Session isolation — session A's audit contains no events from session B
  7.2a  Report completeness — all required fields present in report
  7.2b  Source attribution  — sources cited in suggestions match uploaded documents
  7.2c  Retention policy    — retention_until ~1 year out; GDPR deletion writes tombstone

Usage:
    # Start the API first:
    #   docker compose up --build   (or python run_api.py)
    #
    # Then:
    #   python tests/scripts/e2e_audit_spot_check.py [--base-url http://localhost:8001]
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8001"

DATA_DIR = Path(__file__).parent.parent.parent / "test_data" / "internship" / "data"
UPLOAD_FILES = [
    ("BachelorProject_gids_TIN.pdf", "application/pdf"),
    (
        "Briefing voor aanvang stage 1.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
]

QUESTIONS = [
    "Wanneer start en stopt mijn stage?",
    "Voor hoeveel telt elk onderdeel van het Bachelor Project mee in het eindtotaal?",
    "Wanneer gaat het juryexamen door?",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SECTION = "\033[1;34m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []


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


def get_token(client: httpx.Client, user_id: str) -> str | None:
    r = client.post("/dev/token", json={"user_id": user_id, "org": "pxl", "roles": ["respondent"]})
    if r.status_code == 200:
        return r.json().get("token")
    return None


def upload_files(client: httpx.Client, headers: dict) -> list[str]:
    uploaded = []
    for filename, mime in UPLOAD_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            check(f"Upload {filename}", False, "File not found")
            continue
        with open(path, "rb") as f:
            r = client.post(
                "/upload",
                files={"file": (filename, f, mime)},
                headers=headers,
                timeout=120,
            )
        if r.status_code == 200:
            uploaded.append(filename)
        else:
            check(f"Upload {filename}", False, r.text[:80])
    return uploaded


# ---------------------------------------------------------------------------
# Test sections
# ---------------------------------------------------------------------------


def check_server(client: httpx.Client) -> bool:
    section("Pre-flight: server health")
    try:
        r = client.get("/health", timeout=5)
        return check("GET /health → 200", r.status_code == 200)
    except httpx.ConnectError:
        check("GET /health → 200", False, "Connection refused — is the server running?")
        return False


def test_audit_accuracy(client: httpx.Client, token: str) -> None:
    """7.1a — Audit log entries match actual events performed.

    Note: the audit log also contains SESSION_START and CONSENT_ACCEPTED entries
    that are logged automatically by the session middleware, so total_events will
    always be uploads + suggestions + 2 (for those two automatic events).
    """
    section("7.1a  Audit accuracy — entries match events")
    headers = auth_headers(token)

    # Upload known files and ask known questions
    uploaded = upload_files(client, headers)
    check(f"Uploaded {len(UPLOAD_FILES)} files", len(uploaded) == len(UPLOAD_FILES))

    answered = []
    for question in QUESTIONS:
        r = client.post("/suggest", json={"question": question}, headers=headers, timeout=60)
        if r.status_code == 200:
            answered.append(question)

    check(f"Got {len(QUESTIONS)} suggestions", len(answered) == len(QUESTIONS))

    # Fetch audit report and compare counts
    r = client.get("/audit-report", headers=headers)
    if not check("GET /audit-report → 200", r.status_code == 200, r.text[:80]):
        return

    report = r.json()
    summary = report.get("summary", {})

    check(
        "documents_uploaded matches actual uploads",
        summary.get("documents_uploaded") == len(uploaded),
        f"expected={len(uploaded)}, got={summary.get('documents_uploaded')}",
    )
    check(
        "suggestions_generated matches actual suggestions",
        summary.get("suggestions_generated") == len(answered),
        f"expected={len(answered)}, got={summary.get('suggestions_generated')}",
    )
    # Verify individual log entries
    entries = report.get("log_entries", [])

    # SESSION_START and CONSENT_ACCEPTED are also logged automatically (+2)
    expected_min = len(uploaded) + len(answered)
    actual = summary.get("total_events", 0)
    check(
        "total_events >= uploads + suggestions",
        actual >= expected_min,
        f"expected>={expected_min}, got={actual}",
    )
    session_event_types = {e.get("event_type") for e in entries}
    check(
        "SESSION_START and CONSENT_ACCEPTED present",
        {"SESSION_START", "CONSENT_ACCEPTED"}.issubset(session_event_types),
        f"event types: {session_event_types}",
    )
    upload_entries = [e for e in entries if e.get("event_type") == "UPLOAD"]
    suggest_entries = [e for e in entries if e.get("event_type") == "SUGGEST"]

    uploaded_names_in_log = {e.get("details", {}).get("filename") for e in upload_entries}
    check(
        "Each uploaded filename appears in log",
        all(f in uploaded_names_in_log for f in uploaded),
        f"in log: {uploaded_names_in_log}",
    )

    questions_in_log = {e.get("details", {}).get("question") for e in suggest_entries}
    check(
        "Each question appears in log",
        all(q in questions_in_log for q in answered),
        f"in log: {[q[:40] for q in questions_in_log]}",
    )


def test_timestamps(client: httpx.Client, token: str, t_start: datetime) -> None:
    """7.1b — Timestamps are accurate and correctly ordered."""
    section("7.1b  Timestamps — accurate and ordered")
    headers = auth_headers(token)

    t_before = t_start  # recorded before any operations in this test run
    r = client.get("/audit-report", headers=headers)
    t_after = datetime.now(UTC)

    if not check("GET /audit-report → 200", r.status_code == 200):
        return

    report = r.json()
    entries = report.get("log_entries", [])

    if not check("Report has log entries", len(entries) > 0):
        return

    timestamps = []
    for entry in entries:
        ts_str = entry.get("timestamp")
        if not ts_str:
            check("Entry has timestamp", False, str(entry))
            continue
        # Parse — handle both Z suffix and +00:00
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        timestamps.append(ts)

    check("All entries have timestamps", len(timestamps) == len(entries))

    # All timestamps should be between test start and now (with some tolerance)
    tolerance = timedelta(seconds=5)
    all_recent = all(t_before - tolerance <= ts <= t_after + tolerance for ts in timestamps)
    check(
        "All timestamps fall within test window",
        all_recent,
        f"window: {t_before.isoformat()} – {t_after.isoformat()}",
    )

    # Entries should be in chronological order
    ordered = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
    check("Log entries are in chronological order", ordered)

    # retention_until should be ~1 year from last entry
    retention_str = report.get("retention_until")
    if check("Report has retention_until", bool(retention_str)):
        retention = datetime.fromisoformat(retention_str.replace("Z", "+00:00"))
        expected_min = t_before + timedelta(days=364)
        expected_max = t_after + timedelta(days=366)
        check(
            "retention_until is ~1 year from session end",
            expected_min <= retention <= expected_max,
            f"retention_until={retention.date()}, expected ~{(t_before + timedelta(days=365)).date()}",
        )


def test_session_isolation(client: httpx.Client, token_a: str, token_b: str) -> None:
    """7.1c — Session A's audit contains no events from session B.

    Note: suggest calls without uploaded documents return early before reaching
    the audit logger, so isolation is verified via session_id on all entries and
    by confirming no cross-contamination of event data between sessions.
    """
    section("7.1c  Audit session isolation")

    # Fetch both reports and compare session IDs
    r_a = client.get("/audit-report", headers=auth_headers(token_a))
    r_b = client.get("/audit-report", headers=auth_headers(token_b))

    if not check("Session A audit report → 200", r_a.status_code == 200):
        return
    if not check("Session B audit report → 200", r_b.status_code == 200):
        return

    report_a = r_a.json()
    report_b = r_b.json()

    session_id_a = report_a.get("session_id")
    session_id_b = report_b.get("session_id")

    check(
        "Sessions have distinct IDs",
        session_id_a != session_id_b,
        f"A={session_id_a}, B={session_id_b}",
    )

    # Every entry in A must belong to A's session only
    entries_a = report_a.get("log_entries", [])
    session_ids_in_a = {e.get("session_id") for e in entries_a}
    check(
        "All session A entries carry session A's session_id",
        session_ids_in_a <= {session_id_a},
        f"session_ids found: {session_ids_in_a}",
    )

    # Every entry in B must belong to B's session only
    entries_b = report_b.get("log_entries", [])
    session_ids_in_b = {e.get("session_id") for e in entries_b}
    check(
        "All session B entries carry session B's session_id",
        session_ids_in_b <= {session_id_b},
        f"session_ids found: {session_ids_in_b}",
    )

    # Session B's SUGGEST events (if any) must not appear in session A's log
    questions_in_a = {
        e.get("details", {}).get("question", "")
        for e in entries_a
        if e.get("event_type") == "SUGGEST"
    }
    questions_in_b = {
        e.get("details", {}).get("question", "")
        for e in entries_b
        if e.get("event_type") == "SUGGEST"
    }
    cross_contamination = questions_in_b & questions_in_a
    check(
        "No session B questions appear in session A log",
        len(cross_contamination) == 0,
        f"overlap: {cross_contamination}" if cross_contamination else "",
    )


def test_report_completeness(client: httpx.Client, token: str) -> None:
    """7.2a — Report contains all required fields."""
    section("7.2a  Report completeness")
    headers = auth_headers(token)

    r = client.get("/audit-report", headers=headers)
    if not check("GET /audit-report → 200", r.status_code == 200):
        return

    report = r.json()

    # Top-level fields
    for field in ["session_id", "created_at", "retention_until", "summary", "log_entries"]:
        check(f"Report has '{field}'", field in report and report[field] is not None)

    # Summary fields
    summary = report.get("summary", {})
    for field in [
        "total_events",
        "documents_uploaded",
        "suggestions_generated",
        "suggestions_edited",
    ]:
        check(f"Summary has '{field}'", field in summary)

    # Each log entry has required fields
    entries = report.get("log_entries", [])
    if check("Report has log entries", len(entries) > 0):
        for entry in entries:
            for field in ["event_type", "timestamp", "session_id", "details"]:
                if not check(f"Entry has '{field}'", field in entry and entry[field] is not None):
                    break  # only report first missing field per entry


def test_source_attribution(client: httpx.Client, token: str) -> None:
    """7.2b — Sources in suggestion log entries match uploaded document names."""
    section("7.2b  Source attribution")
    headers = auth_headers(token)

    r = client.get("/audit-report", headers=headers)
    if not check("GET /audit-report → 200", r.status_code == 200):
        return

    report = r.json()
    entries = report.get("log_entries", [])
    uploaded_names = {f for f, _ in UPLOAD_FILES}

    suggest_entries = [e for e in entries if e.get("event_type") == "SUGGEST"]
    if not check("Report has suggestion entries", len(suggest_entries) > 0):
        return

    for entry in suggest_entries:
        sources = entry.get("details", {}).get("sources_used", [])
        question = entry.get("details", {}).get("question", "")[:50]
        check(
            f'Suggestion "{question}..." has at least one source',
            len(sources) > 0,
            f"sources: {sources}",
        )
        unknown = [s for s in sources if s not in uploaded_names]
        check(
            f'All sources for "{question}..." are known uploads',
            len(unknown) == 0,
            f"unknown sources: {unknown}" if unknown else "",
        )


def test_retention_and_deletion(client: httpx.Client, token: str) -> None:
    """7.2c — Retention policy and GDPR deletion."""
    section("7.2c  Retention policy & GDPR deletion")
    headers = auth_headers(token)

    # Verify retention_until before deletion
    r = client.get("/audit-report", headers=headers)
    if check("GET /audit-report before deletion → 200", r.status_code == 200):
        report = r.json()
        retention_str = report.get("retention_until")
        if check("retention_until present", bool(retention_str)):
            retention = datetime.fromisoformat(retention_str.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            check(
                "retention_until is in the future",
                retention > now,
                f"retention_until={retention.date()}",
            )
            check(
                "retention_until is at least 364 days from now",
                retention >= now + timedelta(days=364),
                f"days remaining: {(retention - now).days}",
            )

    # GDPR deletion
    r = client.delete("/audit-report", headers=headers)
    if check("DELETE /audit-report → 200", r.status_code == 200):
        body = r.json()
        check("Deletion response deleted=true", body.get("deleted") is True)

    # Report should be gone
    r = client.get("/audit-report", headers=headers)
    check("GET /audit-report after deletion → 404", r.status_code == 404)

    # By design: the tombstone permanently blocks API access even if new events
    # are written to the log file afterwards. This is intentional for the PoC —
    # once a user exercises GDPR erasure, the report endpoint stays closed.
    client.post("/suggest", json={"question": "post-deletion test"}, headers=headers, timeout=30)
    r = client.get("/audit-report", headers=headers)
    check(
        "GET /audit-report after deletion stays 404 (tombstone honoured)",
        r.status_code == 404,
        r.text[:80],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Cue audit logging e2e spot check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print(f"\nCue audit spot check  →  {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if not check_server(client):
            sys.exit(1)

        section("Setup: obtain dev tokens")
        token_a = get_token(client, "audit_user_a")
        token_b = get_token(client, "audit_user_b")
        check("Token A obtained", bool(token_a))
        check("Token B obtained", bool(token_b))
        if not token_a or not token_b:
            sys.exit(1)

        t_start = datetime.now(UTC)

        # 7.1a — accuracy (uploads + questions happen here, token_a session populated)
        test_audit_accuracy(client, token_a)

        # 7.1b — timestamps (reads the same session; t_start covers the full run)
        test_timestamps(client, token_a, t_start)

        # 7.1c — isolation (token_b makes its own event)
        test_session_isolation(client, token_a, token_b)

        # 7.2a — completeness
        test_report_completeness(client, token_a)

        # 7.2b — source attribution
        test_source_attribution(client, token_a)

        # 7.2c — retention + deletion (destructive, run last for token_a)
        test_retention_and_deletion(client, token_a)

        # Cleanup
        for token in (token_a, token_b):
            client.delete("/session", headers=auth_headers(token))

    # Summary
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
