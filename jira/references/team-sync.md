# Refreshing Team Structure

`references/team-structure.json` holds Atlassian Team UUIDs + members used for team
assignment (`customfield_10001`). Atlassian teams get renamed, merged, and deleted, so these
UUIDs go stale — a stale UUID makes `jira_create_issue` / `jira_update_issue` fail with
**"Team with id '…' not found."** This procedure regenerates the file from the live API and
reconciles `config.json`.

The generator is `scripts/fetch-teams.py`. It uses the **Atlassian GraphQL gateway**
(`/gateway/api/graphql`), which works with a normal Jira Cloud API token over basic auth — no
admin access or OAuth. `siteId` (cloudId) and `orgId` are auto-discovered. It depends only on
the Python 3 standard library.

> Note: the older Teams REST API (`api.atlassian.com/public/teams/v1`) is OAuth-only and
> returns 401 with a basic-auth API token — that is why this uses the GraphQL gateway.

## Procedure

### 1. Ensure credentials
The script reads `JIRA_USERNAME` and `JIRA_API_TOKEN` from the environment (`JIRA_URL`
defaults to the `atlassian_url` you use, e.g. `https://evinced.atlassian.net`).

If they're not already exported, source the token from the configured `mcp-atlassian` server:

```bash
export JIRA_USERNAME=<your-atlassian-email>
export JIRA_API_TOKEN=$(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/.claude.json')))['mcpServers']['atlassian']['env']['JIRA_API_TOKEN'])")
```

The token needs only normal user access (the same token the jira tools use).

### 2. Run the generator
```bash
python3 jira/scripts/fetch-teams.py
```
It auto-discovers IDs, fetches every team + members, writes
`references/team-structure.json` (teams sorted by name, members by account_id), and prints a
**team count** plus an **Added / Removed** diff vs. the previous file.

### 3. Verify
- `python3 -m json.tool jira/references/team-structure.json` parses without error.
- Team count looks sane (dozens, not zero).
- Review the Added/Removed diff — removals are the teams whose UUIDs were stale.
- Confirm no removed team is still referenced as a dead UUID in `config.json` (step 4).

### 4. Reconcile `config.json`
The refresh can remove or rename teams that `config.json` still references. Check both:
- **`title_tag_to_team`** — every mapped team name must exist in the refreshed
  `team-structure.json`. For any tag pointing at a removed/renamed team, propose a remap to
  the team that absorbed it.
- **`default_team`** — its `name` + `uuid` must still match a live team; update if not.

**Always confirm remaps with the user (AskUserQuestion) before editing `config.json`** —
which team absorbed a merged squad is a judgment call, not derivable from the data alone.

Known org fact: **MFA work is handled by the Mobile Engine Team** — map `[MFA]` →
`Mobile Engine Team` (the former standalone MFA team was removed).

### 5. Report
Summarize: team count, Added/Removed teams, and any `config.json` remaps applied. If this was
triggered by a "Team not found" error, retry the original create/update now.

## When to run
- On demand: "refresh teams", "update team structure", "team-structure.json is stale".
- Reactively: any Jira mutation fails with "Team … not found" — run this, then retry.
- Periodically: the file's `last_updated` is months old and team assignment matters.
