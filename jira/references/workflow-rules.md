# Jira Workflow Rules

Detailed rules for creating, updating, and managing Jira issues. Referenced by SKILL.md.

## Pre-Creation Checklist

Before creating any issue, verify:
- Summary is clear and actionable
- Team UUID looked up from `team-structure.json` (NEVER hardcode)
- Assignee name matches exactly as listed in `team-structure.json`
- Classification field value selected (REQUIRED)
- Time estimate specified if available
- Epic link set if applicable

## Required Fields for Issue Creation

| Field | Source | Notes |
|-------|--------|-------|
| `project_key` | config.json `project_key` | Usually "MOB" |
| `summary` | User input | Auto-fix obvious typos |
| `issue_type` | User input or config default | Task, Bug, Story, Epic, Subtask |
| `description` | User input | Use exact text, no embellishment |

## Recommended Fields (set during creation)

| Field | Config Key | Format |
|-------|-----------|--------|
| `assignee` | Exact display name | Must match team-structure.json |
| Epic link | `custom_fields.epic_link` | Issue key string, e.g. "MOB-14735" |
| Team | `custom_fields.team` | Team UUID from team-structure.json |
| Classification | `custom_fields.classification` | `{"value": "Classification Name"}` |

## Optional Fields

| Field | Format | Example |
|-------|--------|---------|
| `priority` | Name string | "High", "Medium", "Low" |
| Time estimate | `{"originalEstimate": "Xd"}` | "2d", "4h", "30m", "1d 4h" |
| `labels` | Array of strings | `["frontend", "urgent"]` |
| `components` | Comma-separated string | "Frontend,API" |

## Confirmation Display Template

Before ANY create or update, display this to the user and wait for confirmation:

```
About to create:
- Project: {project_key}
- Type: {issue_type}
- Summary: {summary}
- Description: {description (truncated if long)}
- Priority: {priority or "Medium (default)"}
- Assignee: {assignee or "Unassigned"}
- Team: {team_name} ({team_uuid})
- Epic: {epic_key or "None"}
- Estimate: {estimate or "None"}
- Classification: {classification}

Proceed?
```

## Post-Creation Actions

After successfully creating an issue:
1. Verify the response contains the issue key
2. If time estimate was specified but not set during creation, update with `jira_update_issue`
3. If team field wasn't set during creation, update it separately
4. Print clickable link: `https://{atlassian_url}/browse/{issue_key}`

## Issue Update Rules

1. Always fetch current issue state with `jira_get_issue` BEFORE updating
2. Show the user what will change (old value -> new value)
3. Wait for confirmation before applying
4. After update, print the clickable link

## Transition Rules

1. Always call `jira_get_transitions` first to get available transitions
2. Use the transition ID (not name) when calling `jira_transition_issue`
3. Some transitions require fields (e.g., resolution). If so, include them.
4. Common flow: To Do -> In Progress -> In Review -> Done

## Issue Linking

### Available operations:
- `jira_create_issue_link` - Generic links (Duplicate, Relates, Blocks, Clones)
- `jira_link_to_epic` - Link issue to an epic
- `jira_remove_issue_link` - Remove a link (needs link ID from `jira_get_issue`)

### After linking:
- Verify by fetching both issues
- Report success with links to both issues

## Batch Operation Rules

1. Create issues 1-3 at a time (never all at once)
2. After each batch, show progress: "Created 3/15 issues..."
3. Ask for confirmation at logical checkpoints (every 5 issues, or between groups)
4. If any creation fails, stop and report before continuing
5. Provide running summary with clickable links

## Summary Template (for batch operations)

After completing batch operations:

```markdown
## Task Creation Complete

### Epic: [MOB-XXXXX](https://{url}/browse/MOB-XXXXX) - Epic Title

### Tasks Created:

**{Team Name} ({Assignee}):**
1. [MOB-XXXX](link) - Task summary - **Xd** - Team assigned
2. [MOB-YYYY](link) - Task summary - **Xd** - Team assigned

**Total:** X tasks created
**Estimated Work:** X days
**Tasks Needing Attention:**
- MOB-ZZZZ - Needs time estimate
- MOB-AAAA - Needs team assignment
```

## Error Recovery

### Missing Team Assignment
1. Determine team from assignee (look up in team-structure.json)
2. Or from title tags (use `title_tag_to_team` config mapping)
3. Or from epic context
4. Fall back to default team from config
5. Always look up UUID from team-structure.json

### Failed Issue Creation
1. Check the error message for specific field issues
2. Common causes: invalid assignee name, wrong field format, missing required field
3. Show the error to the user with a suggested fix
4. Do NOT retry automatically without user input

### Failed Issue Links
1. Verify both issues exist with `jira_get_issue`
2. Check link type name is exact (use `jira_get_link_types` to verify)
3. Retry once with corrected parameters
4. If still failing, report to user and suggest manual linking

### Missing Time Estimates
1. Check source document for estimates
2. If found, update with `jira_update_issue`
3. If not found, mark as "TBD" in summary
4. List all tasks still needing estimates
