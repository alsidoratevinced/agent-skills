---
name: jira
description: >
  Manage Jira issues with full workflow support. Use for ALL Jira interactions
  including searching, creating, updating, or querying issues. MUST be used
  whenever a request mentions a person by name, team, or role — this skill
  contains team-structure.json needed to resolve names, teams, and account IDs.
  Also handles team assignment, custom fields, time tracking, epic linking,
  and classification.
argument-hint: "[action] [details] - e.g. 'create bug for login crash' or 'MOB-123 set priority High'"
---

# Jira Workflow Skill

## Configuration

!`cat jira/config.json 2>/dev/null || echo '{"error": "config.json not found. Copy config.template.json to config.json and fill in your values."}'`

If you see an error above, guide the user to set up their config:
1. Copy `config.template.json` to `config.json`
2. Fill in: `atlassian_url`, `project_key`, `username`, `default_team`
3. Adjust `custom_fields` if their Jira instance uses different field IDs

## Core Rules

These rules are CRITICAL and must ALWAYS be followed:

1. **Always confirm before creating or updating issues**
   - Display a full summary of all fields (see `references/workflow-rules.md` for template)
   - Wait for explicit user approval before proceeding
   - NEVER create or update tickets without confirmation

2. **Always print clickable links after any mutation**
   - Format: `[{issue_key}](https://{atlassian_url}/browse/{issue_key})`
   - Include in every creation/update response

3. **Auto-fix minor spelling mistakes silently**
   - Do NOT ask for confirmation on obvious typos
   - Correct common mistakes in summaries and descriptions

4. **Do NOT add comments or labels unless explicitly requested**
   - Only add what the user specifically asks for

5. **Do NOT generate extra summaries or descriptions**
   - Use exact text from the user or source document
   - No embellishment or interpretation

6. **Classification field is REQUIRED on all issues**
   - Always include the classification field (from `custom_fields.classification` in config)
   - Options are listed in `classification_options` in config
   - If the user doesn't specify, infer from context or ask

## People & Team Resolution

When ANY Jira request mentions a person by first name, partial name, or team:
1. ALWAYS read `references/team-structure.json` first
2. Match the person by name + team context
3. Use the resolved full name in JQL queries

This is critical for ambiguous names (e.g., "Anton from iOS team" vs "Anton" from Engine team).

## Issue Creation

### Flow:
1. Parse user request for: summary, type, assignee, team, epic, estimate, description, classification
2. Apply defaults from config for anything not specified
3. Look up team assignment (see Team Assignment below)
4. Display confirmation with ALL fields
5. On approval, call `jira_create_issue` with:
   - `project_key` from config
   - `summary`, `issue_type`, `description` from user input
   - `assignee` (exact name from team-structure.json)
   - `additional_fields` with team UUID, epic link, classification, time estimate

### Field formats:

Read `references/custom-fields.md` for complete field format specifications.

**Quick reference for `additional_fields`:**
```
{
  "{team_field_id}": "team-uuid-from-team-structure-json",
  "{epic_field_id}": "EPIC-KEY",
  "{classification_field_id}": {"value": "Classification Name"},
  "timetracking": {"originalEstimate": "2d"}
}
```

Replace `{team_field_id}`, `{epic_field_id}`, `{classification_field_id}` with the actual IDs from config `custom_fields`.

## Team Assignment

### Priority order:
1. **Assignee specified** -> Look up assignee in `references/team-structure.json` -> use their team's UUID
2. **Title has tags** -> Match tag against `title_tag_to_team` in config -> look up team name in team-structure.json -> use UUID
3. **Neither** -> Use `default_team.uuid` from config

### How to look up:
1. Read `references/team-structure.json`
2. Find the team by name
3. Use the `id` field (UUID) for the team custom field
4. NEVER hardcode team UUIDs — always look them up from the file

### When assigning a person:
1. Search for the person's name in team-structure.json across all teams
2. Use their `account_id` is not needed for `assignee` field (use display name)
3. But DO use their team's UUID for the team field

## Issue Updates

1. ALWAYS fetch current state first: `jira_get_issue(issue_key="...")`
2. Show what will change (old -> new)
3. Wait for confirmation
4. Call `jira_update_issue` with only the changed fields
5. Print clickable link after update

For field formats when updating, see `references/custom-fields.md`.

## Search and Queries

Translate natural language to JQL. Use config `project_key` as default project.

**Common patterns:**
- "my open bugs" -> `project = {project_key} AND issuetype = Bug AND assignee = "{username}" AND status != Done`
- "tasks in sprint" -> `project = {project_key} AND sprint in openSprints()`
- "high priority issues" -> `project = {project_key} AND priority = High AND status != Done`
- "issues in epic X" -> `parent = X OR "Epic Link" = X`
- "tickets on Anton from iOS" -> look up team-structure.json -> find Anton Yereshchenko in Mobile iOS Team -> `assignee = "Anton Yereshchenko" ORDER BY updated DESC`
- "iOS team open bugs" -> look up Mobile iOS Team members -> `assignee in (...) AND issuetype = Bug AND status != Done`

Format results as a markdown table with clickable links.

## Transitions

1. Call `jira_get_transitions(issue_key="...")` to get available transitions
2. Match user's intent to a transition name
3. Confirm with user
4. Call `jira_transition_issue` with the transition ID (not name)
5. Some transitions require fields (e.g., resolution) — include them if needed

## Issue Linking

- **Duplicate/Relates/Blocks**: `jira_create_issue_link(link_type="...", inward_issue_key="...", outward_issue_key="...")`
- **Epic link**: `jira_link_to_epic(issue_key="...", epic_key="...")`
- **Remove link**: Get link ID from `jira_get_issue`, then `jira_remove_issue_link(link_id="...")`

Always verify links by checking both issues afterward.

## Time Logging

- **Log work**: `jira_add_worklog(issue_key="...", time_spent="4h")`
- **Set estimate**: `jira_update_issue(issue_key="...", fields={"timetracking": {"originalEstimate": "2d"}})`

## Batch Operations

See `references/workflow-rules.md` for detailed batch rules.

**Summary:**
1. Parse all tasks from user input
2. Look up ALL team UUIDs before starting
3. Display full breakdown and get confirmation
4. Create 1-3 at a time, show progress after each
5. Confirm at checkpoints (every 5 issues or between groups)
6. Provide final summary with clickable links (see template in workflow-rules.md)

## Error Recovery

See `references/workflow-rules.md` for detailed error recovery procedures.

**Quick guide:**
- Creation failed -> Show error, suggest fix, don't retry without user input
- Missing team -> Infer from assignee/tags/epic, fall back to default
- Missing estimate -> Mark as TBD, list in summary
- Link failed -> Verify both issues exist, check link type name, retry once

## Reference Files

- `references/workflow-rules.md` — Detailed rules, confirmation templates, batch rules, error recovery
- `references/custom-fields.md` — Custom field IDs, formats, and how to discover them
- `references/team-structure.json` — Team UUIDs and members (read when team assignment needed)
- `examples/usage-examples.md` — Example interactions showing expected behavior
