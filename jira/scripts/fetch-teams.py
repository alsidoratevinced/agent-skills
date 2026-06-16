#!/usr/bin/env python3
"""
Fetch Atlassian team structure and write to references/team-structure.json.

Uses the Atlassian GraphQL gateway (/gateway/api/graphql), which works with a
normal Jira Cloud API token over basic auth -- no admin access or OAuth scope
needed. siteId (cloudId) and orgId are auto-discovered, so no manual IDs.

Usage:
    JIRA_USERNAME=you@company.com JIRA_API_TOKEN=xxxx \\
        python3 fetch-teams.py [--jira-url https://your-domain.atlassian.net] \\
        [--output ../references/team-structure.json]

Environment variables:
    JIRA_URL        Base URL (default: https://evinced.atlassian.net).
                    May also be set via --jira-url.
    JIRA_USERNAME   Atlassian account email (basic-auth user).
    JIRA_API_TOKEN  API token from
                    https://id.atlassian.com/manage-profile/security/api-tokens

Tip: source the token already configured for the mcp-atlassian server:
    export JIRA_USERNAME=you@company.com
    export JIRA_API_TOKEN=$(python3 -c "import json,os; \\
        print(json.load(open(os.path.expanduser('~/.claude.json')))\\
        ['mcpServers']['atlassian']['env']['JIRA_API_TOKEN'])")
"""

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

DEFAULT_JIRA_URL = "https://evinced.atlassian.net"
DEFAULT_OUTPUT = str(Path(__file__).parent.parent / "references" / "team-structure.json")
TEAM_ARI_PREFIX = "ari:cloud:identity::team/"


def _post_graphql(gql_url, auth_header, operation_name, query, variables):
    """POST a named GraphQL operation and return the `data` object.

    Raises RuntimeError on transport errors or GraphQL `errors`.
    """
    body = json.dumps(
        {"operationName": operation_name, "query": query, "variables": variables}
    ).encode("utf-8")
    req = urllib.request.Request(gql_url, data=body, method="POST")
    req.add_header("Authorization", auth_header)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"GraphQL HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"GraphQL request failed: {e.reason}") from None
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(payload['errors'])[:500]}")
    return payload.get("data") or {}


def _get_json(url, auth_header):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", auth_header)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code} for {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request to {url} failed: {e.reason}") from None


def discover_site_id(jira_url, auth_header):
    """cloudId == siteId, exposed unauthenticated at /_edge/tenant_info."""
    data = _get_json(f"{jira_url}/_edge/tenant_info", auth_header)
    site_id = data.get("cloudId")
    if not site_id:
        raise RuntimeError("Could not resolve cloudId from /_edge/tenant_info")
    return site_id


def discover_org_id(gql_url, auth_header, site_id):
    query = (
        "query OrgId($c: [ID!]!) { tenantContexts(cloudIds: $c) { orgId } }"
    )
    data = _post_graphql(gql_url, auth_header, "OrgId", query, {"c": [site_id]})
    contexts = (data.get("tenantContexts") or [])
    org_id = contexts[0].get("orgId") if contexts else None
    if not org_id:
        raise RuntimeError("Could not resolve orgId from tenantContexts")
    return org_id


def fetch_teams(gql_url, auth_header, site_id, org_ari):
    """Return list of {id (bare uuid), name, description} for every team."""
    query = (
        "query TeamList($s: String!, $o: ID!, $after: String) {"
        " team { teamSearchV2(siteId: $s, organizationId: $o,"
        " filter: { query: \"\" }, first: 100, after: $after) {"
        " nodes { team { id displayName description } }"
        " pageInfo { hasNextPage endCursor } } } }"
    )
    teams = []
    after = None
    while True:
        data = _post_graphql(
            gql_url, auth_header, "TeamList",
            query, {"s": site_id, "o": org_ari, "after": after},
        )
        search = (data.get("team") or {}).get("teamSearchV2") or {}
        for node in search.get("nodes") or []:
            team = node.get("team") or {}
            raw_id = team.get("id", "")
            teams.append({
                "id": raw_id.replace(TEAM_ARI_PREFIX, ""),
                "name": team.get("displayName", ""),
                "description": team.get("description") or "",
            })
        page = search.get("pageInfo") or {}
        if page.get("hasNextPage"):
            after = page.get("endCursor")
        else:
            break
    return teams


def fetch_members(gql_url, auth_header, site_id, team_uuid):
    """Return list of {name, account_id} for one team."""
    query = (
        "query TeamMembers($id: ID!, $s: String!, $after: String) {"
        " team { teamV2(id: $id, siteId: $s) {"
        " members(first: 50, after: $after) {"
        " nodes { member { accountId name } }"
        " pageInfo { hasNextPage endCursor } } } } }"
    )
    team_ari = TEAM_ARI_PREFIX + team_uuid
    members = []
    after = None
    while True:
        data = _post_graphql(
            gql_url, auth_header, "TeamMembers",
            query, {"id": team_ari, "s": site_id, "after": after},
        )
        conn = ((data.get("team") or {}).get("teamV2") or {}).get("members") or {}
        for node in conn.get("nodes") or []:
            member = node.get("member") or {}
            members.append({
                "name": member.get("name", ""),
                "account_id": member.get("accountId", ""),
            })
        page = conn.get("pageInfo") or {}
        if page.get("hasNextPage"):
            after = page.get("endCursor")
        else:
            break
    return members


def load_previous_team_names(output_path):
    try:
        with open(output_path) as f:
            return set((json.load(f).get("teams") or {}).keys())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--jira-url",
        default=os.environ.get("JIRA_URL", DEFAULT_JIRA_URL),
        help=f"Jira base URL (default: {DEFAULT_JIRA_URL} or $JIRA_URL)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    jira_url = args.jira_url.rstrip("/")
    username = os.environ.get("JIRA_USERNAME")
    token = os.environ.get("JIRA_API_TOKEN")
    if not username or not token:
        print("Error: set JIRA_USERNAME and JIRA_API_TOKEN environment variables.")
        print("Token: https://id.atlassian.com/manage-profile/security/api-tokens")
        sys.exit(1)

    auth_header = "Basic " + base64.b64encode(
        f"{username}:{token}".encode("utf-8")
    ).decode("ascii")
    gql_url = f"{jira_url}/gateway/api/graphql"

    print(f"Discovering site/org for {jira_url}...")
    site_id = discover_site_id(jira_url, auth_header)
    org_id = discover_org_id(gql_url, auth_header, site_id)
    org_ari = f"ari:cloud:platform::org/{org_id}"
    print(f"  siteId={site_id}  orgId={org_id}")

    print("Fetching teams...")
    teams = fetch_teams(gql_url, auth_header, site_id, org_ari)
    print(f"Found {len(teams)} teams")

    teams_dict = {}
    for i, team in enumerate(sorted(teams, key=lambda t: t["name"].lower())):
        members = fetch_members(gql_url, auth_header, site_id, team["id"])
        members.sort(key=lambda m: m["account_id"])
        print(f"  ({i + 1}/{len(teams)}) {team['name']}: {len(members)} members")
        teams_dict[team["name"]] = {
            "id": team["id"],
            "description": team["description"],
            "members": members,
        }

    output_path = Path(args.output)
    previous_names = load_previous_team_names(output_path)

    result = {"last_updated": str(date.today()), "teams": teams_dict}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {len(teams_dict)} teams to {output_path}")
    if previous_names is not None:
        current = set(teams_dict.keys())
        added = sorted(current - previous_names)
        removed = sorted(previous_names - current)
        if added:
            print(f"  Added:   {', '.join(added)}")
        if removed:
            print(f"  Removed: {', '.join(removed)}")
        if not added and not removed:
            print("  No team additions or removals vs. previous file.")
    print("Done!")


if __name__ == "__main__":
    main()
