# Custom Field Reference

Custom field IDs and formats used in Jira issue operations. Field IDs are configured in `config.json` under `custom_fields`.

## Field Mapping

| Field Name | Config Key | Default ID | Format |
|------------|-----------|------------|--------|
| Team | `custom_fields.team` | `customfield_10001` | Team UUID string |
| Epic Link | `custom_fields.epic_link` | `customfield_10014` | Issue key string |
| Classification | `custom_fields.classification` | `customfield_10938` | `{"value": "Name"}` |
| Time Tracking | (built-in) | `timetracking` | `{"originalEstimate": "Xd"}` |

## Team Field

**Config key:** `custom_fields.team`

The team field stores a team UUID. Always look up the UUID from `references/team-structure.json`.

**Setting during creation:**
```json
"additional_fields": {
  "customfield_10001": "206cd4c7-6cdb-4a6e-aadd-e11958ee265a"
}
```

**Updating existing issue:**
```json
"fields": {
  "customfield_10001": "206cd4c7-6cdb-4a6e-aadd-e11958ee265a"
}
```

NEVER use team names for this field. ALWAYS use the UUID from team-structure.json.

## Epic Link Field

**Config key:** `custom_fields.epic_link`

Links an issue to an epic. Value is the epic's issue key as a plain string.

**Setting during creation:**
```json
"additional_fields": {
  "customfield_10014": "MOB-14735"
}
```

Alternative: Use `jira_link_to_epic` MCP tool after creation.

## Classification Field (REQUIRED)

**Config key:** `custom_fields.classification`

This is a dropdown/select field. It is REQUIRED on all issues.

**Options** (configured in `config.json` under `classification_options`):

| Name | ID | When to Use |
|------|----|-------------|
| Product Roadmap | 11183 | New features, enhancements, user-facing improvements |
| Support & Maintenance | 11184 | Bug fixes, hotfixes, customer support, patches |
| Technical Debt & Engineering Health | 11185 | Refactoring, performance, tech debt, infrastructure |

**Format:**
```json
"additional_fields": {
  "customfield_10938": {"value": "Product Roadmap"}
}
```

If unsure which classification to use, ask the user.

## Time Tracking

**Field:** `timetracking` (built-in Jira field)

**Supported units:**
- `d` - days (e.g., "2d")
- `h` - hours (e.g., "4h")
- `m` - minutes (e.g., "30m")
- Combined: "1d 4h"

**Setting during creation:**
```json
"additional_fields": {
  "timetracking": {"originalEstimate": "2d"}
}
```

**Updating existing issue:**
```json
"fields": {
  "timetracking": {"originalEstimate": "2d"}
}
```

## Discovering Custom Field IDs (for new users)

If your Jira instance uses different custom field IDs:

1. Use the `jira_search_fields` MCP tool with a keyword:
   - `jira_search_fields(keyword="team")` - find the team field
   - `jira_search_fields(keyword="epic")` - find the epic link field
   - `jira_search_fields(keyword="classification")` - find the classification field

2. Update `config.json` with your instance's field IDs:
   ```json
   "custom_fields": {
     "team": "customfield_XXXXX",
     "epic_link": "customfield_XXXXX",
     "classification": "customfield_XXXXX"
   }
   ```

3. Classification options and IDs also vary by instance. Check your Jira project settings for available values and update `classification_options` in config.json.
