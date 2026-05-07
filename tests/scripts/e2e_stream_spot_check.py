#!/usr/bin/env python3
"""
End-to-end spot-check for the POST /suggest/stream SSE endpoint.

Covers:
  S.1  Happy path  — upload docs, stream batch suggestions, verify all items arrive
  S.2  SSE format  — event/data structure, done sentinel, valid JSON payloads
  S.3  Answer report persistence  — report written after stream completes
  S.4  Performance — time-to-first-suggestion vs. total time
  S.5  Security    — unauthenticated request rejected

Usage:
    python tests/scripts/e2e_stream_spot_check.py [--base-url http://localhost:8001]

Defaults to http://localhost:8001.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://localhost:8001"

DATA_DIR = Path(__file__).parent.parent.parent / "test_data" / "internship" / "data"
DATA_FILES = [
    DATA_DIR / "BachelorProject_gids_TIN.pdf",
    DATA_DIR / "Briefing voor aanvang stage 1.pptx",
]

# Six items spread across two sections to exercise sibling-context logic
BATCH_PAYLOAD = {
    "assessment_id": "stream-e2e-test",
    "sections": [
        {
            "id": "sec1",
            "title": "Stage",
            "items": [
                {
                    "id": "q1",
                    "type": "open_ended",
                    "prompt": "Wanneer start en stopt mijn stage?",
                    "choices": [],
                },
                {
                    "id": "q2",
                    "type": "open_ended",
                    "prompt": "Hoeveel dagen per week mag ik remote werken tijdens mijn stage?",
                    "choices": [],
                },
                {
                    "id": "q3",
                    "type": "open_ended",
                    "prompt": "Mag ik mijn eindwerk ook in het Engels schrijven?",
                    "choices": [],
                },
            ],
        },
        {
            "id": "sec2",
            "title": "Bachelor Project",
            "items": [
                {
                    "id": "q4",
                    "type": "open_ended",
                    "prompt": "Hoe lang moet mijn presentatie tijdens het juryexamen duren?",
                    "choices": [],
                },
                {
                    "id": "q5",
                    "type": "open_ended",
                    "prompt": "Voor hoeveel telt elk onderdeel van het Bachelor Project mee?",
                    "choices": [],
                },
                {
                    "id": "q6",
                    "type": "open_ended",
                    "prompt": "Wanneer gaat het juryexamen door?",
                    "choices": [],
                },
            ],
        },
    ],
}

EXPECTED_ITEM_IDS: set[str] = {"q1", "q2", "q3", "q4", "q5", "q6"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
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


# ---------------------------------------------------------------------------
# SSE parser
# ---------------------------------------------------------------------------


def consume_sse_stream(
    client: httpx.Client,
    url: str,
    payload: dict,
    headers: dict,
    timeout: float = 120.0,
) -> tuple[list[dict], bool, float | None, float]:
    """Stream POST /suggest/stream and return parsed results.

    Returns:
        suggestions: list of parsed suggestion dicts
        got_done: whether event: done was received
        ttfs: time-to-first-suggestion (seconds), or None if none arrived
        total: total elapsed time (seconds)
    """
    suggestions: list[dict] = []
    got_done = False
    ttfs: float | None = None
    t0 = time.perf_counter()

    with client.stream("POST", url, json=payload, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        event_type: str | None = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                if event_type == "suggestion":
                    if ttfs is None:
                        ttfs = time.perf_counter() - t0
                    try:
                        suggestions.append(json.loads(data_str))
                    except json.JSONDecodeError:
                        suggestions.append({"_parse_error": data_str})
                    event_type = None
                elif event_type == "done":
                    got_done = True
                    break
                elif event_type == "error":
                    print(f"  [{WARN}] SSE error event: {data_str}")
                    break

    total = time.perf_counter() - t0
    return suggestions, got_done, ttfs, total


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
        return False


def get_dev_token(client: httpx.Client, user_id: str) -> str | None:
    r = client.post(
        "/auth/token", json={"user_id": user_id, "api_secret": os.getenv("API_SECRET", "")}
    )
    if check(f"POST /auth/token ({user_id}) → 200", r.status_code == 200):
        token = r.json().get("token", "")
        check("Token non-empty", bool(token))
        return token
    return None


def upload_documents(client: httpx.Client, headers: dict) -> list[str]:
    section("S.1  Setup — upload documents")
    uploaded = []
    for file_path in DATA_FILES:
        if not file_path.exists():
            check(f"Upload {file_path.name}", False, "File not found")
            continue
        suffix = file_path.suffix.lower()
        mime = {
            ".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }.get(suffix, "application/octet-stream")
        with open(file_path, "rb") as f:
            r = client.post(
                "/upload",
                files={"file": (file_path.name, f, mime)},
                headers=headers,
                timeout=60,
            )
        if check(f"Upload {file_path.name}", r.status_code == 200):
            uploaded.append(file_path.name)
    return uploaded


def test_security(client: httpx.Client) -> None:
    section("S.5  Security")
    r = client.post("/suggest/stream", json=BATCH_PAYLOAD)
    check("No token → 401", r.status_code == 401)

    r = client.post(
        "/suggest/stream",
        json=BATCH_PAYLOAD,
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    check("Malformed token → 401", r.status_code == 401)


def test_stream_happy_path(client: httpx.Client, headers: dict) -> None:
    section("S.1  Happy path — stream batch suggestions")

    n_items = len(EXPECTED_ITEM_IDS)
    print(f"\n  Streaming {n_items} items across {len(BATCH_PAYLOAD['sections'])} sections…")

    suggestions, got_done, ttfs, total = consume_sse_stream(
        client, "/suggest/stream", BATCH_PAYLOAD, headers
    )

    check(
        f"Received all {n_items} suggestion events",
        len(suggestions) == n_items,
        f"got {len(suggestions)}",
    )
    check("Stream terminated with event: done", got_done)
    check(
        "Total stream time < 120s",
        total < 120,
        f"{total:.1f}s",
    )


def test_sse_format(client: httpx.Client, headers: dict) -> None:
    section("S.2  SSE format validation")

    suggestions, got_done, _ttfs, _total = consume_sse_stream(
        client, "/suggest/stream", BATCH_PAYLOAD, headers
    )

    received_ids: set[str] = {str(s["item_id"]) for s in suggestions if "item_id" in s}
    check(
        "All expected item_ids present",
        received_ids == EXPECTED_ITEM_IDS,
        f"got {sorted(received_ids)}, expected {sorted(EXPECTED_ITEM_IDS)}",
    )

    parse_errors = [s for s in suggestions if "_parse_error" in s]
    check(
        "All suggestion data fields parse as valid JSON",
        len(parse_errors) == 0,
        f"{len(parse_errors)} parse error(s)" if parse_errors else "",
    )

    required_fields = {"item_id", "type", "suggestion", "citations"}
    malformed = [s for s in suggestions if not required_fields.issubset(s.keys())]
    check(
        "All suggestions have required fields (item_id, type, suggestion, citations)",
        len(malformed) == 0,
        f"{len(malformed)} malformed" if malformed else "",
    )

    non_empty = [s for s in suggestions if (s.get("suggestion") or "").strip()]
    check(
        "All suggestions have non-empty suggestion text",
        len(non_empty) == len(suggestions),
        f"{len(suggestions) - len(non_empty)} empty suggestion(s)",
    )

    check("Stream ends with event: done", got_done)


def test_answer_report_persistence(client: httpx.Client, headers: dict) -> None:
    section("S.3  Answer report persisted after stream")

    # Consume the stream to completion
    suggestions, got_done, _ttfs, _total = consume_sse_stream(
        client, "/suggest/stream", BATCH_PAYLOAD, headers
    )

    if not check("Stream completed (prerequisite)", got_done):
        return

    # The stream endpoint writes the answer report on done; fetch it
    r = client.get("/answer-report/download", headers=headers, timeout=10)
    if not check(
        "GET /answer-report/download → 200", r.status_code == 200, r.text[:80] if r.is_error else ""
    ):
        return

    report = r.json()
    check("Answer report is a list", isinstance(report, list))
    if isinstance(report, list):
        check(
            f"Report contains {len(EXPECTED_ITEM_IDS)} entries",
            len(report) >= len(EXPECTED_ITEM_IDS),
            f"got {len(report)}",
        )
        reported_ids = {entry.get("question_id") for entry in report}
        check(
            "All streamed item_ids appear in report",
            EXPECTED_ITEM_IDS.issubset(reported_ids),
            f"missing: {EXPECTED_ITEM_IDS - reported_ids}"
            if not EXPECTED_ITEM_IDS.issubset(reported_ids)
            else "",
        )
        entry = report[0]
        for field in ("question_id", "question", "answer", "generated_at"):
            check(f"Report entry has '{field}'", field in entry)


def test_performance(client: httpx.Client, headers: dict) -> None:
    section("S.4  Performance — time-to-first-suggestion")

    suggestions, got_done, ttfs, total = consume_sse_stream(
        client, "/suggest/stream", BATCH_PAYLOAD, headers
    )

    n = len(EXPECTED_ITEM_IDS)
    if ttfs is not None:
        naive_avg = total / n if n else 0
        check(
            "First suggestion arrives before naive-batch average",
            ttfs < naive_avg,
            f"ttfs={ttfs:.1f}s  naive_avg={naive_avg:.1f}s  total={total:.1f}s",
        )
        check(
            "Time-to-first-suggestion < 30s",
            ttfs < 30,
            f"ttfs={ttfs:.1f}s",
        )
    else:
        check("Time-to-first-suggestion measured", False, "no suggestions received")

    check(
        f"All {n} suggestions received",
        len(suggestions) == n,
        f"got {len(suggestions)}",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Cue /suggest/stream e2e spot check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    print(f"\nCue stream spot check  →  {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if not check_server(client):
            sys.exit(1)

        test_security(client)

        section("Setup: obtain dev token")
        token = get_dev_token(client, "stream_e2e_user")
        if not token:
            print(f"\n  [{FAIL}] Could not obtain dev token — aborting\n")
            sys.exit(1)
        headers = auth_headers(token)

        upload_documents(client, headers)

        # Each test section streams independently; answer report accumulates
        test_stream_happy_path(client, headers)
        test_sse_format(client, headers)
        test_answer_report_persistence(client, headers)
        test_performance(client, headers)

        # Cleanup
        client.delete("/session", headers=headers)

    section("Summary")
    total_checks = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total_checks - passed
    print(f"\n  {passed}/{total_checks} checks passed", end="")
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
