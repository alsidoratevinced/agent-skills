#!/usr/bin/env python3
"""
Compute sprint KPI metrics using the Jira GreenHopper Sprint Report API.

Usage:
    python compute-kpi.py --sprint-name "Mobile Engine 26S05"
    python compute-kpi.py --sprint-name "Mobile Engine 26S05" --vacation-days 2
    python compute-kpi.py --sprint-name "Mobile Engine 26S05" --config path/to/config.json

All team-specific settings (Atlassian URL, board name, credentials, defaults)
are read from config.json. See config.template.json for the expected format.

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
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HOURS_PER_DAY = 8
SECONDS_PER_HOUR = 3600


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(config_path: str | None) -> dict:
    """Load config.json from the given path or auto-discover it."""
    if config_path:
        path = Path(config_path)
    else:
        # Auto-discover: look relative to this script's location
        script_dir = Path(__file__).resolve().parent
        path = script_dir.parent / "config.json"

    if not path.exists():
        print(f"Error: Config file not found at {path}", file=sys.stderr)
        print("Copy config.template.json to config.json and fill in your values.", file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def make_auth_header(config: dict) -> str:
    """Build Basic Auth header from config credentials."""
    email = config.get("jira_email") or os.environ.get("JIRA_EMAIL", "")
    token = config.get("jira_api_token") or os.environ.get("JIRA_API_TOKEN", "")
    if not email or not token:
        print("Error: Jira credentials not found.", file=sys.stderr)
        print("Set jira_email/jira_api_token in config.json, or export JIRA_EMAIL/JIRA_API_TOKEN.", file=sys.stderr)
        sys.exit(1)
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return f"Basic {credentials}"


def jira_get(base_url: str, auth_header: str, path: str, params: dict | None = None) -> dict:
    """Make an authenticated GET request to the Jira API."""
    url = f"{base_url}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"Error: Authentication failed (HTTP {e.code}). Check credentials in config.json.", file=sys.stderr)
            sys.exit(1)
        body = e.read().decode() if e.fp else ""
        print(f"Error: HTTP {e.code} from {path}: {body[:500]}", file=sys.stderr)
        sys.exit(1)


def resolve_board_id(base_url: str, auth: str, board_name: str) -> int:
    """Find board ID by name using the Jira Agile REST API."""
    data = jira_get(base_url, auth, "/rest/agile/1.0/board", {"name": board_name})
    values = data.get("values", [])
    if not values:
        print(f"Error: Board '{board_name}' not found.", file=sys.stderr)
        sys.exit(1)
    return values[0]["id"]


def resolve_sprint(base_url: str, auth: str, board_id: int, sprint_name: str) -> dict:
    """Find a sprint by name on the given board."""
    for state in ("closed", "active"):
        start_at = 0
        while True:
            data = jira_get(base_url, auth, f"/rest/agile/1.0/board/{board_id}/sprint", {
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
    recent = jira_get(base_url, auth, f"/rest/agile/1.0/board/{board_id}/sprint", {
        "state": "closed", "startAt": 0, "maxResults": 5,
    })
    names = [s["name"] for s in recent.get("values", [])]
    print(f"Error: Sprint '{sprint_name}' not found on board {board_id}.", file=sys.stderr)
    if names:
        print(f"Recent sprints: {', '.join(names)}", file=sys.stderr)
    sys.exit(1)


def fetch_sprint_report(base_url: str, auth: str, board_id: int, sprint_id: int) -> dict:
    """Fetch the GreenHopper sprint report (frozen snapshot)."""
    return jira_get(base_url, auth, "/rest/greenhopper/1.0/rapid/charts/sprintreport", {
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


def parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime string from Jira."""
    s = s.replace("Z", "+00:00")
    # Ensure timezone offset has colon (e.g., +0000 → +00:00)
    if re.match(r'.*[+-]\d{4}$', s):
        s = s[:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)


def fetch_sprint_changes(base_url: str, auth: str, issue_key: str) -> list[dict]:
    """Fetch Sprint field changelog entries for an issue."""
    entries = []
    start_at = 0
    while True:
        data = jira_get(base_url, auth, f"/rest/api/2/issue/{issue_key}/changelog", {
            "startAt": start_at, "maxResults": 100,
        })
        for history in data.get("values", []):
            for item in history.get("items", []):
                if item.get("field") == "Sprint":
                    entries.append({
                        "created": history["created"],
                        "from_string": item.get("fromString", ""),
                        "to_string": item.get("toString", ""),
                    })
        if data.get("isLast", True) or start_at + 100 >= data.get("total", 0):
            break
        start_at += 100
    return entries


def reclassify_punted(
    base_url: str,
    auth: str,
    punted: list[dict],
    sprint_name: str,
    complete_date_str: str,
) -> tuple[list[dict], list[dict]]:
    """
    Separate punted issues into carryovers and true punts.

    A carryover is a punted issue whose Sprint field was changed shortly
    before the sprint's completeDate — i.e., it was moved by the
    "Complete Sprint" action, not manually removed beforehand.

    Jira processes "Complete Sprint" by first moving each issue (changelog
    timestamps), then marking the sprint closed (completeDate). For sprints
    with many issues, this can take 10+ minutes, so we use a 30-minute
    window looking backwards from completeDate.
    """
    if not punted or not complete_date_str:
        return [], punted

    complete_dt = parse_iso_datetime(complete_date_str)
    window = timedelta(minutes=30)

    carryovers = []
    true_punts = []

    for issue in punted:
        changes = fetch_sprint_changes(base_url, auth, issue["key"])
        is_carryover = False

        for change in changes:
            from_sprints = change.get("from_string") or ""
            to_sprints = change.get("to_string") or ""

            if sprint_name in from_sprints and sprint_name not in to_sprints:
                change_dt = parse_iso_datetime(change["created"])
                if abs(change_dt - complete_dt) <= window:
                    is_carryover = True
                    break

        if is_carryover:
            carryovers.append(issue)
        else:
            true_punts.append(issue)

    return carryovers, true_punts


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
    base_url: str,
    sprint_name: str,
    sprint_id: int,
    sprint_state: str,
    sprint_start: str,
    sprint_end: str,
    team_size: int,
    vacation_days: int,
    sick_days: int,
    support_pct: int,
    working_days: int,
    support_bucket: dict | None,
    planned_stats: dict,
    unplanned_stats: dict,
    total_stats: dict,
) -> str:
    """Format the KPI report as markdown."""
    gross = team_size * working_days
    support_days = round(gross * support_pct / 100, 1)
    net = round(gross - vacation_days - support_days, 1)

    p_done_pct = pct(planned_stats["done_count"], planned_stats["count"])
    u_done_pct = pct(unplanned_stats["done_count"], unplanned_stats["count"])

    # Support bucket line
    if support_bucket:
        sb_est = seconds_to_days(support_bucket["estimate_seconds"])
        sb_line = (
            f"- {support_bucket['key']}: {support_bucket['summary']} — {sb_est}d "
            f"([link]({base_url}/browse/{support_bucket['key']}))"
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
    parser.add_argument("--sprint-name", required=True, help="Sprint name (e.g. 'Mobile Engine 26S05')")
    parser.add_argument("--config", help="Path to config.json (default: auto-discover)")
    parser.add_argument("--board-name", help="Override board name from config")
    parser.add_argument("--team-size", type=int, help="Override team size from config")
    parser.add_argument("--vacation-days", type=int, default=0, help="Total vacation person-days (default: 0)")
    parser.add_argument("--sick-days", type=int, default=0, help="Total sick person-days (default: 0)")
    parser.add_argument("--support-pct", type=int, help="Override support percentage from config")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    defaults = config.get("defaults", {})

    base_url = config["atlassian_url"]
    board_name = args.board_name or config["board_name"]
    team_size = args.team_size if args.team_size is not None else defaults.get("team_size", 5)
    support_pct = args.support_pct if args.support_pct is not None else defaults.get("support_pct", 20)
    working_days = defaults.get("working_days_per_sprint", 9)

    auth = make_auth_header(config)

    # Resolve board and sprint
    board_id = resolve_board_id(base_url, auth, board_name)
    sprint = resolve_sprint(base_url, auth, board_id, args.sprint_name)

    # Fetch GreenHopper sprint report
    report_data = fetch_sprint_report(base_url, auth, board_id, sprint["id"])
    contents = report_data["contents"]
    sprint_info = report_data["sprint"]

    # Parse all issue arrays
    completed = [parse_issue(i) for i in contents.get("completedIssues", [])]
    not_completed = [parse_issue(i) for i in contents.get("issuesNotCompletedInCurrentSprint", [])]
    punted = [parse_issue(i) for i in contents.get("puntedIssues", [])]

    # Reclassify punted issues: those moved during "Complete Sprint" are carryovers
    complete_date = sprint_info.get("isoCompleteDate") or sprint_info.get("completeDate", "")
    carryovers, true_punts = reclassify_punted(
        base_url, auth, punted, args.sprint_name, complete_date,
    )
    not_completed = not_completed + carryovers

    # Identify support bucket (scan all arrays including true punts)
    all_for_bucket_scan = completed + not_completed + true_punts
    support_bucket, _ = find_support_bucket(all_for_bucket_scan)
    sb_key = support_bucket["key"] if support_bucket else None

    # Build working set: completed + not_completed, excluding support bucket
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
        base_url=base_url,
        sprint_name=sprint_info.get("name", args.sprint_name),
        sprint_id=sprint["id"],
        sprint_state=sprint_info.get("state", sprint["state"]),
        sprint_start=sprint_info.get("isoStartDate", sprint["start"]),
        sprint_end=sprint_info.get("isoEndDate", sprint["end"]),
        team_size=team_size,
        vacation_days=args.vacation_days,
        sick_days=args.sick_days,
        support_pct=support_pct,
        working_days=working_days,
        support_bucket=support_bucket,
        planned_stats=planned_stats,
        unplanned_stats=unplanned_stats,
        total_stats=total_stats,
    )
    print(output)


if __name__ == "__main__":
    main()
