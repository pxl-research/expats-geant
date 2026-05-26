#!/usr/bin/env python3
"""
End-to-end spot-check for LLM-driven survey reordering (move_question / move_section).

Unlike the unit suite (which mocks the LLM and feeds it canned tool calls), this
script hits a *running* Shape API with natural-language reorder requests and asserts
the live model actually changes the draft's list order.

Key property: ordering is list position only — there is no `order` field — so the
*only* way the order can change is via the move_question / move_section tools. A
correct order change therefore proves the model chose the right tool; a stray
update_question can no longer reorder anything.

Each scenario re-seeds a known survey via PUT (deterministic starting order), sends
one phrased instruction via POST /chat/{sid}, then GETs the draft and checks order.

Requires an LLM key configured on the server. If the chat turn returns 500 (no key),
checks are reported as WARN rather than FAIL.

Usage:
    # With the stack running (docker compose up shape-api, or python run_chat_api.py):
    python tests/scripts/e2e_reorder_spot_check.py [--base-url http://localhost:8003]

Defaults to http://localhost:8003.
"""

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_BASE_URL = "http://localhost:8003"
CHAT_TIMEOUT = 120  # LLM turns can be slow

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
    print(f"\n{SECTION}{'=' * 60}{RESET}")
    print(f"{SECTION}{title}{RESET}")
    print(f"{SECTION}{'=' * 60}{RESET}")


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
# Seed survey: two sections, known question order
# ---------------------------------------------------------------------------

SEED_SURVEY = {
    "id": "spotcheck_reorder",
    "title": "Reorder Spot-check Survey",
    "description": "",
    "sections": [
        {
            "id": "sec_intro",
            "title": "Introduction",
            "description": "",
            "metadata": {},
            "questions": [
                {"id": "q_name", "text": "What is your name?", "type": "open_ended"},
                {"id": "q_age", "text": "What is your age?", "type": "open_ended"},
            ],
        },
        {
            "id": "sec_feedback",
            "title": "Feedback",
            "description": "",
            "metadata": {},
            "questions": [
                {"id": "q_rating", "text": "How would you rate our service?", "type": "open_ended"},
                {"id": "q_comments", "text": "Any additional comments?", "type": "open_ended"},
            ],
        },
    ],
    "metadata": {},
}


def seed(client: httpx.Client, headers: dict, sid: str) -> bool:
    r = client.put(f"/chat/{sid}/survey", json={"survey": SEED_SURVEY}, headers=headers)
    return r.status_code == 200


def get_layout(client: httpx.Client, headers: dict, sid: str) -> dict[str, list[str]]:
    """Return {section_id: [question_id, ...]} in current list order."""
    r = client.get(f"/chat/{sid}/survey", headers=headers)
    survey = r.json().get("survey") or {}
    return {s["id"]: [q["id"] for q in s["questions"]] for s in survey.get("sections", [])}


def section_order(client: httpx.Client, headers: dict, sid: str) -> list[str]:
    r = client.get(f"/chat/{sid}/survey", headers=headers)
    survey = r.json().get("survey") or {}
    return [s["id"] for s in survey.get("sections", [])]


def ask(client: httpx.Client, headers: dict, sid: str, message: str) -> httpx.Response:
    return client.post(
        f"/chat/{sid}", json={"message": message}, headers=headers, timeout=CHAT_TIMEOUT
    )


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def check_server(client: httpx.Client) -> bool:
    section("Section 1 — Pre-flight: server health")
    try:
        r = client.get("/health", timeout=5)
        return check("GET /health → 200", r.status_code == 200, str(r.json()))
    except httpx.ConnectError:
        check("GET /health → 200", False, "Connection refused — is the server running?")
        return False


def llm_available(client: httpx.Client, headers: dict, sid: str) -> bool:
    """Probe with a trivial turn; a 500 means no LLM key is configured."""
    r = ask(client, headers, sid, "Briefly, what does this survey cover?")
    if r.status_code == 500:
        warn("LLM probe", "500 from POST /chat/{sid} — no LLM key on the server; skipping")
        return False
    check("LLM probe → 200", r.status_code == 200, r.text[:120])
    return r.status_code == 200


def test_reorder_within_section(client: httpx.Client, headers: dict, sid: str) -> None:
    section("Section 2 — Reorder questions within a section")
    if not seed(client, headers, sid):
        check("seed survey", False, "PUT failed")
        return
    before = get_layout(client, headers, sid).get("sec_intro")
    check("seeded order", before == ["q_name", "q_age"], str(before))

    r = ask(
        client,
        headers,
        sid,
        "In the 'Introduction' section, move the age question so it comes first, "
        "before the name question.",
    )
    if not check("POST /chat/{sid} → 200", r.status_code == 200, r.text[:120]):
        return
    check("survey_updated == true", r.json().get("survey_updated") is True)

    after = get_layout(client, headers, sid).get("sec_intro")
    check(
        "age now before name in Introduction",
        after == ["q_age", "q_name"],
        f"got {after} (a correct change here can only come from move_question)",
    )


def test_reorder_sections(client: httpx.Client, headers: dict, sid: str) -> None:
    section("Section 3 — Reorder sections")
    if not seed(client, headers, sid):
        check("seed survey", False, "PUT failed")
        return
    before = section_order(client, headers, sid)
    check("seeded section order", before == ["sec_intro", "sec_feedback"], str(before))

    r = ask(
        client,
        headers,
        sid,
        "Move the 'Feedback' section so it appears first, before the 'Introduction' section.",
    )
    if not check("POST /chat/{sid} → 200", r.status_code == 200, r.text[:120]):
        return
    check("survey_updated == true", r.json().get("survey_updated") is True)

    after = section_order(client, headers, sid)
    check(
        "Feedback now before Introduction",
        after == ["sec_feedback", "sec_intro"],
        f"got {after} (a correct change here can only come from move_section)",
    )


def test_cross_section_move(client: httpx.Client, headers: dict, sid: str) -> None:
    section("Section 4 — Move a question across sections")
    if not seed(client, headers, sid):
        check("seed survey", False, "PUT failed")
        return

    r = ask(
        client,
        headers,
        sid,
        "Move the 'Any additional comments?' question out of Feedback and into the "
        "'Introduction' section.",
    )
    if not check("POST /chat/{sid} → 200", r.status_code == 200, r.text[:120]):
        return
    check("survey_updated == true", r.json().get("survey_updated") is True)

    layout = get_layout(client, headers, sid)
    intro = layout.get("sec_intro", [])
    feedback = layout.get("sec_feedback", [])
    check(
        "comments question now in Introduction",
        "q_comments" in intro,
        f"intro={intro}",
    )
    check(
        "comments question removed from Feedback",
        "q_comments" not in feedback,
        f"feedback={feedback}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-driven reorder end-to-end spot check")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    args = parser.parse_args()

    print(f"\nShape reorder spot check  →  {args.base_url}\n")

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if not check_server(client):
            print("\n  Start the stack (docker compose up shape-api) and retry.\n")
            sys.exit(1)

        section("Setup: token + session")
        token = get_dev_token(client, "e2e_reorder_user")
        if not token:
            check(
                "Dev token obtained", False, "Could not get dev token (check API_SECRET) — aborting"
            )
            sys.exit(1)
        check("Dev token obtained", True)
        headers = auth_headers(token)

        r = client.post("/chat/sessions", json={}, headers=headers)
        if not check("POST /chat/sessions → 201", r.status_code == 201, r.text[:120]):
            sys.exit(1)
        sid = r.json()["session_id"]

        if not llm_available(client, headers, sid):
            section("Reorder scenarios (require LLM)")
            warn("Skipping reorder scenarios — LLM unavailable")
        else:
            test_reorder_within_section(client, headers, sid)
            test_reorder_sections(client, headers, sid)
            test_cross_section_move(client, headers, sid)

        client.delete(f"/chat/{sid}", headers=headers)

    section("Summary")
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "pass")
    warned = sum(1 for _, s, _ in results if s == "warn")
    failed = sum(1 for _, s, _ in results if s == "fail")

    print(f"\n  {passed}/{total} checks passed", end="")
    if warned:
        print(f"  ({warned} warned)", end="")
    if failed:
        print(f"  ({failed} failed)")
        print("\n  Failed checks (an order-change miss may mean the model chose the wrong tool):")
        for label, status, detail in results:
            if status == "fail":
                print(f"    [{FAIL}] {label}  {detail}")
    else:
        print("  — all good!")

    print()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
