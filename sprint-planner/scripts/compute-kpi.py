#!/usr/bin/env python3
"""
Compute sprint KPI metrics using the Jira GreenHopper Sprint Report API.

Usage:
    python compute-kpi.py \
        --board-name "Mobile Engine" \
        --sprint-name "Mobile Engine 26S05" \
        --team-size 5 \
        --vacation-days 2 \
        --sick-days 0 \
        --support-pct 20

Requires environment variables:
    JIRA_EMAIL      — Atlassian account email
    JIRA_API_TOKEN  — API token from https://id.atlassian.com/manage-profile/security/api-tokens

Output: Markdown-formatted KPI report to stdout.
"""

import argparse
import base64
import json
import math
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKING_DAYS_PER_SPRINT = 9  # 10 weekdays minus 1 for ceremonies
HOURS_PER_DAY = 8
SECONDS_PER_HOUR = 3600
BASE_URL = "https://evinced.atlassian.net"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def get_auth_header() -> str:
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        print("Error: JIRA_EMAIL and JIRA_API_TOKEN environment variables are required.", file=sys.stderr)
        print("Generate a token at https://id.atlassian.com/manage-profile/security/api-tokens", file=sys.stderr)
        sys.exit(1)
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return f"Basic {credentials}"


def jira_get(path: str, params: dict | None = None) -> dict:
    """Make an authenticated GET request to the Jira API."""
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("Authorization", get_auth_header())
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"Error: Authentication failed (HTTP {e.code}). Check JIRA_EMAIL and JIRA_API_TOKEN.", file=sys.stderr)
            sys.exit(1)
        body = e.read().decode() if e.fp else ""
        print(f"Error: HTTP {e.code} from {path}: {body[:500]}", file=sys.stderr)
        sys.exit(1)


def resolve_board_id(board_name: str) -> int:
    """Find board ID by name using the Jira Agile REST API."""
    data = jira_get("/rest/agile/1.0/board", {"name": board_name})
    values = data.get("values", [])
    if not values:
        print(f"Error: Board '{board_name}' not found.", file=sys.stderr)
        sys.exit(1)
    return values[0]["id"]


def resolve_sprint(board_id: int, sprint_name: str) -> dict:
    """Find a sprint by name on the given board. Returns {id, name, state, start, end}."""
    for state in ("closed", "active"):
        start_at = 0
        while True:
            data = jira_get(f"/rest/agile/1.0/board/{board_id}/sprint", {
                "state": state, "startAt": start_at, "maxResults": 50,
            })
            for s in data.get("values", []):
                if s["name"] == sprint_name:
                    return {
                        "id": s["id"],
                        "name": s["name"],
                        "state": s["state"],
                        "start": s.get("startDate", ""),
                        "end": s.get("endDate", ""),
                    }
            if data.get("isLast", True):
                break
            start_at += 50

    # Not found — show recent sprints to help the user
    recent = jira_get(f"/rest/agile/1.0/board/{board_id}/sprint", {
        "state": "closed", "startAt": 0, "maxResults": 5,
    })
    names = [s["name"] for s in recent.get("values", [])]
    print(f"Error: Sprint '{sprint_name}' not found on board {board_id}.", file=sys.stderr)
    if names:
        print(f"Recent sprints: {', '.join(names)}", file=sys.stderr)
    sys.exit(1)


def fetch_sprint_report(board_id: int, sprint_id: int) -> dict:
    """Fetch the GreenHopper sprint report (frozen snapshot)."""
    return jira_get("/rest/greenhopper/1.0/rapid/charts/sprintreport", {
        "rapidViewId": board_id, "sprintId": sprint_id,
    })


# ---------------------------------------------------------------------------
# Issue parsing
# ---------------------------------------------------------------------------

def parse_issue(raw: dict) -> dict:
    """Extract fields from a GreenHopper issue object."""
    estimate = 0
    stat = raw.get("currentEstimateStatistic") or {}
    field_val = stat.get("statFieldValue") or {}
    val = field_val.get("value")
    if val is not None and isinstance(val, (int, float)):
        estimate = val

    return {
        "key": raw["key"],
        "summary": raw.get("summary", ""),
        "status_name": raw.get("statusName", ""),
        "estimate_seconds": estimate,
    }


def is_support_bucket(summary: str) -> bool:
    """Check if an issue is the support bucket based on summary text."""
    s = re.sub(r"\s+", " ", summary.strip().lower())
    return "support" in s and any(w in s for w in ("bucket", "sprint", "time"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seconds_to_days(seconds: int | float) -> int:
    """Convert seconds to working days (8h/day), rounded to 0 decimal places.

    Uses math.floor(x + 0.5) to match JavaScript's Math.round / .toFixed(0)
    behavior (rounds 0.5 up), unlike Python's round() which uses banker's rounding.
    """
    if not seconds:
        return 0
    return math.floor(seconds / SECONDS_PER_HOUR / HOURS_PER_DAY + 0.5)


def pct(part: int, total: int) -> str:
    """Format percentage, handling division by zero."""
    if total == 0:
        return "0%"
    return f"{round(part / total * 100)}%"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def find_support_bucket(issues: list[dict]) -> tuple[dict | None, list[dict]]:
    """Find the support bucket and return it separately from the filtered list."""
    bucket = None
    for issue in issues:
        if is_support_bucket(issue["summary"]):
            bucket = issue
            break

    if bucket is None:
        return None, issues

    filtered = [i for i in issues if i["key"] != bucket["key"]]
    return bucket, filtered


def classify_issues(
    issues: list[dict],
    added_keys: set[str],
) -> tuple[list[dict], list[dict]]:
    """Split issues into planned and unplanned using issueKeysAddedDuringSprint."""
    planned = [i for i in issues if i["key"] not in added_keys]
    unplanned = [i for i in issues if i["key"] in added_keys]
    return planned, unplanned


def compute_stats(issues: list[dict], completed_keys: set[str]) -> dict:
    """Compute stats for a group of issues.

    An issue is "done" if its key is in completedIssues (GreenHopper's classification).
    Estimates are summed as raw seconds first, then converted to days — matching
    the Chrome extension's behavior (sum first, round once).
    """
    count = len(issues)
    est = seconds_to_days(sum(i["estimate_seconds"] for i in issues))
    done = [i for i in issues if i["key"] in completed_keys]
    done_count = len(done)
    done_est = seconds_to_days(sum(i["estimate_seconds"] for i in done))
    cancelled = [i for i in issues if i["status_name"] == "Cancelled"]
    cancel_count = len(cancelled)
    cancel_est = seconds_to_days(sum(i["estimate_seconds"] for i in cancelled))

    return {
        "count": count,
        "est": est,
        "done_count": done_count,
        "done_est": done_est,
        "cancel_count": cancel_count,
        "cancel_est": cancel_est,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def format_report(
    sprint_name: str,
    sprint_id: int,
    sprint_state: str,
    sprint_start: str,
    sprint_end: str,
    team_size: int,
    vacation_days: int,
    sick_days: int,
    support_pct: int,
    support_bucket: dict | None,
    planned_stats: dict,
    unplanned_stats: dict,
    total_stats: dict,
) -> str:
    """Format the KPI report as markdown."""
    gross = team_size * WORKING_DAYS_PER_SPRINT
    support_days = round(gross * support_pct / 100, 1)
    net = round(gross - vacation_days - support_days, 1)

    p_done_pct = pct(planned_stats["done_count"], planned_stats["count"])
    u_done_pct = pct(unplanned_stats["done_count"], unplanned_stats["count"])

    # Support bucket line
    if support_bucket:
        sb_est = seconds_to_days(support_bucket["estimate_seconds"])
        sb_line = (
            f"- {support_bucket['key']}: {support_bucket['summary']} — {sb_est}d "
            f"([link]({BASE_URL}/browse/{support_bucket['key']}))"
        )
    else:
        sb_line = "- No support bucket found"

    # Format dates (date only)
    start_short = sprint_start[:10]
    end_short = sprint_end[:10]

    return f"""## Sprint KPI: {sprint_name}

### Capacity
| Metric               | Value    |
|----------------------|----------|
| Team size            | {team_size}      |
| Gross days           | {gross}d     |
| Vacation days        | {vacation_days}d       |
| Sick days            | {sick_days}d       |
| Support days ({support_pct}%)  | {support_days}d   |
| **Net working days** | **{net}d**  |

### Sprint Stats
| Metric           | Planned          | Unplanned        | Total             |
|------------------|-----------------|-----------------|-------------------|
| Issues           | {planned_stats['count']}               | {unplanned_stats['count']}               | {total_stats['count']}                |
| Estimated days   | {planned_stats['est']}d            | {unplanned_stats['est']}d            | {total_stats['est']}d           |
| Done             | {planned_stats['done_count']} ({p_done_pct})      | {unplanned_stats['done_count']} ({u_done_pct})     | {total_stats['done_count']}/{planned_stats['count']}           |
| Completed days   | {planned_stats['done_est']}d            | {unplanned_stats['done_est']}d            | {total_stats['done_est']}d           |
| Cancelled        | {planned_stats['cancel_count']} ({planned_stats['cancel_est']}d)       | {unplanned_stats['cancel_count']} ({unplanned_stats['cancel_est']}d)        | {total_stats['cancel_count']} ({total_stats['cancel_est']}d)        |

### Support Bucket
{sb_line}

### Sprint Info
- Sprint: {sprint_name} (ID: {sprint_id}, state: {sprint_state})
- Dates: {start_short} → {end_short}"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compute sprint KPI metrics from Jira GreenHopper API")
    parser.add_argument("--board-name", required=True, help="Board name (e.g. 'Mobile Engine')")
    parser.add_argument("--sprint-name", required=True, help="Sprint name (e.g. 'Mobile Engine 26S05')")
    parser.add_argument("--team-size", type=int, default=5, help="Number of engineers (default: 5)")
    parser.add_argument("--vacation-days", type=int, default=0, help="Total vacation person-days (default: 0)")
    parser.add_argument("--sick-days", type=int, default=0, help="Total sick person-days (default: 0)")
    parser.add_argument("--support-pct", type=int, default=20, help="Support percentage (default: 20)")
    args = parser.parse_args()

    # Resolve board and sprint
    board_id = resolve_board_id(args.board_name)
    sprint = resolve_sprint(board_id, args.sprint_name)

    # Fetch GreenHopper sprint report
    report_data = fetch_sprint_report(board_id, sprint["id"])
    contents = report_data["contents"]
    sprint_info = report_data["sprint"]

    # Parse all issue arrays
    completed = [parse_issue(i) for i in contents.get("completedIssues", [])]
    not_completed = [parse_issue(i) for i in contents.get("issuesNotCompletedInCurrentSprint", [])]
    punted = [parse_issue(i) for i in contents.get("puntedIssues", [])]

    # Identify support bucket (scan all 3 arrays)
    all_for_bucket_scan = completed + not_completed + punted
    support_bucket, _ = find_support_bucket(all_for_bucket_scan)
    sb_key = support_bucket["key"] if support_bucket else None

    # Build working set: completed + not_completed, excluding support bucket and punted
    completed_filtered = [i for i in completed if i["key"] != sb_key]
    not_completed_filtered = [i for i in not_completed if i["key"] != sb_key]
    all_issues = completed_filtered + not_completed_filtered

    # Completed keys for "done" classification
    completed_keys = {i["key"] for i in completed_filtered}

    # Planned vs unplanned
    added_keys = set(contents.get("issueKeysAddedDuringSprint", {}).keys())
    planned, unplanned = classify_issues(all_issues, added_keys)

    # Compute stats — totals from full set to avoid rounding drift
    planned_stats = compute_stats(planned, completed_keys)
    unplanned_stats = compute_stats(unplanned, completed_keys)
    total_stats = compute_stats(all_issues, completed_keys)

    # Output
    output = format_report(
        sprint_name=sprint_info.get("name", args.sprint_name),
        sprint_id=sprint["id"],
        sprint_state=sprint_info.get("state", sprint["state"]),
        sprint_start=sprint_info.get("isoStartDate", sprint["start"]),
        sprint_end=sprint_info.get("isoEndDate", sprint["end"]),
        team_size=args.team_size,
        vacation_days=args.vacation_days,
        sick_days=args.sick_days,
        support_pct=args.support_pct,
        support_bucket=support_bucket,
        planned_stats=planned_stats,
        unplanned_stats=unplanned_stats,
        total_stats=total_stats,
    )
    print(output)


if __name__ == "__main__":
    main()
