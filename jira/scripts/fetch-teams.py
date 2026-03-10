#!/usr/bin/env python3
"""
Fetch Atlassian team structure and write to team-structure.json.

Usage:
    ATLASSIAN_API_TOKEN=your_token python fetch-teams.py \\
        --email you@company.com \\
        --org-id YOUR_ORG_ID \\
        [--site-id YOUR_SITE_ID] \\
        [--atlassian-url https://your-domain.atlassian.net] \\
        [--output ../references/team-structure.json]

Finding required IDs:
    org_id:  Go to https://admin.atlassian.com -> the URL contains /o/{ORG_ID}/
             Or: Settings > API keys
    site_id: Go to https://YOUR-DOMAIN.atlassian.net/_edge/tenant_info
             The "cloudId" field is your site ID.
             IMPORTANT: Without site_id, site-scoped teams will NOT be returned.

API token:
    Generate at: https://id.atlassian.com/manage-profile/security/api-tokens
    Pass via ATLASSIAN_API_TOKEN environment variable (never hardcode).
"""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)

TEAMS_API_BASE = "https://api.atlassian.com/public/teams/v1/org"
DEFAULT_OUTPUT = str(Path(__file__).parent.parent / "references" / "team-structure.json")


def fetch_teams(org_id, site_id, auth):
    """Fetch all teams with cursor-based pagination."""
    teams = []
    cursor = None

    while True:
        url = f"{TEAMS_API_BASE}/{org_id}/teams"
        params = {"size": 300}
        if site_id:
            params["siteId"] = site_id
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(url, params=params, auth=auth)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        resp.raise_for_status()

        data = resp.json()
        for team in data.get("entities", []):
            teams.append({
                "name": team.get("displayName", ""),
                "id": team.get("teamId", ""),
                "description": team.get("description", ""),
            })

        cursor = data.get("cursor")
        if not cursor or not data.get("entities"):
            break

    return teams


def fetch_members(org_id, team_id, auth):
    """Fetch all members for a team with relay-style pagination."""
    members = []
    cursor = None

    while True:
        url = f"{TEAMS_API_BASE}/{org_id}/teams/{team_id}/members"
        body = {"first": 50}
        if cursor:
            body["after"] = cursor

        resp = requests.post(url, json=body, auth=auth)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"  Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        resp.raise_for_status()

        data = resp.json()
        for edge in data.get("edges", []):
            node = edge.get("node", {})
            members.append({
                "account_id": node.get("accountId", ""),
                "name": ""  # Resolved separately if atlassian_url provided
            })

        page_info = data.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            cursor = page_info.get("endCursor")
        else:
            break

    return members


def resolve_user(atlassian_url, account_id, auth):
    """Resolve accountId to display name via Jira REST API."""
    url = f"{atlassian_url}/rest/api/3/user"
    params = {"accountId": account_id}

    try:
        resp = requests.get(url, params=params, auth=auth)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            resp = requests.get(url, params=params, auth=auth)
        resp.raise_for_status()
        return resp.json().get("displayName", "")
    except requests.RequestException:
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Atlassian team structure and write to team-structure.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--email", required=True, help="Atlassian account email")
    parser.add_argument("--org-id", required=True, help="Atlassian organization ID")
    parser.add_argument(
        "--site-id",
        default=None,
        help="Atlassian site ID (cloudId). Required for site-scoped teams.",
    )
    parser.add_argument(
        "--atlassian-url",
        default=None,
        help="Jira base URL for resolving user names (e.g., https://evinced.atlassian.net)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    api_token = os.environ.get("ATLASSIAN_API_TOKEN")
    if not api_token:
        print("Error: Set ATLASSIAN_API_TOKEN environment variable")
        print("Generate token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        sys.exit(1)

    auth = (args.email, api_token)

    print(f"Fetching teams for org {args.org_id}...")
    if args.site_id:
        print(f"  Site ID: {args.site_id}")
    else:
        print("  WARNING: No --site-id provided. Site-scoped teams will NOT be returned.")

    teams = fetch_teams(args.org_id, args.site_id, auth)
    print(f"Found {len(teams)} teams")

    for i, team in enumerate(teams):
        print(f"  Fetching members for {team['name']} ({i + 1}/{len(teams)})...")
        team["members"] = fetch_members(args.org_id, team["id"], auth)

        if args.atlassian_url:
            for member in team["members"]:
                name = resolve_user(args.atlassian_url, member["account_id"], auth)
                member["name"] = name
                if name:
                    print(f"    {name}")

        # Small delay to avoid rate limiting
        time.sleep(0.2)

    # Convert list to dict keyed by team name for easier lookup
    teams_dict = {}
    for team in teams:
        teams_dict[team["name"]] = {
            "id": team["id"],
            "description": team.get("description", ""),
            "members": team["members"],
        }

    output = {
        "last_updated": str(date.today()),
        "teams": teams_dict,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(teams)} teams to {output_path}")
    print("Done!")


if __name__ == "__main__":
    main()
