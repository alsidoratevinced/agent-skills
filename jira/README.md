# Jira Skill for Claude Code

A Claude Code skill for managing Jira issues with team assignment, custom fields, batch operations, and more.

## Quick Start

1. **Symlink into your Claude Code skills:**
   ```bash
   ln -s /path/to/jira ~/.claude/skills/jira
   ```

2. **Create your config:**
   ```bash
   cp config.template.json config.json
   ```

3. **Edit `config.json`** with your values:
   - `atlassian_url` — your Jira instance URL (e.g., `https://yourcompany.atlassian.net`)
   - `project_key` — your default project (e.g., `MOB`)
   - `username` — your Jira display name
   - `default_team` — your primary team name and UUID from `references/team-structure.json`
   - `custom_fields` — adjust if your instance uses different field IDs (use `/jira` then ask "search for team field" to discover them)

4. **Populate team structure** (choose one):
   - **Manual:** Create `references/team-structure.json` based on your org's teams
   - **Automated:** Run the fetch script (see below)

5. **Ensure mcp-atlassian is configured** in your Claude Code MCP settings.

## Fetching Team Structure Automatically

The `scripts/fetch-teams.py` script pulls team data from the Atlassian Public Teams API.

### Prerequisites

- Python 3 with `requests` library (`pip install requests`)
- An [Atlassian API token](https://id.atlassian.com/manage-profile/security/api-tokens)
- Your organization ID and site ID (see below)

### Finding Your Organization ID

1. Go to [admin.atlassian.com](https://admin.atlassian.com)
2. The URL will contain your org ID: `https://admin.atlassian.com/o/{ORG_ID}/overview`
3. Alternatively: **Settings > API keys** — the org ID is displayed there

### Finding Your Site ID

1. Open your browser and go to: `https://YOUR-DOMAIN.atlassian.net/_edge/tenant_info`
2. The JSON response contains a `cloudId` field — that's your site ID
3. Example: `{"cloudId": "abc123de-f456-7890-ghij-klmnopqrstuv", ...}`

**Important:** Without `--site-id`, site-scoped teams will NOT be returned (you may get an empty list).

### Running the Script

```bash
ATLASSIAN_API_TOKEN=your_token python scripts/fetch-teams.py \
  --email you@company.com \
  --org-id YOUR_ORG_ID \
  --site-id YOUR_SITE_ID \
  --atlassian-url https://your-domain.atlassian.net
```

This writes `references/team-structure.json` with all teams and their members.

## File Overview

| File | Purpose | Git tracked? |
|------|---------|:---:|
| `SKILL.md` | Main skill definition | Yes |
| `config.template.json` | Config template for new users | Yes |
| `config.json` | Your personal config | No |
| `references/workflow-rules.md` | Detailed workflow rules and templates | Yes |
| `references/custom-fields.md` | Custom field formats and discovery | Yes |
| `references/team-structure.json` | Team UUIDs and members | No |
| `scripts/fetch-teams.py` | Team structure fetcher | Yes |
| `examples/usage-examples.md` | Example interactions | Yes |

## Usage

Once installed, use `/jira` or just describe what you need:

- "Create a bug for login crash on iOS"
- "Update MOB-123 priority to High"
- "Find my open tasks"
- "Move MOB-456 to In Progress"
- "Log 4 hours on MOB-789"
