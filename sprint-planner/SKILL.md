---
name: sprint-planner
description: >
  Prepare and organize a new sprint for the Team Lead. Gathers inputs,
  ensures sprint exists, creates support bucket, calculates capacity,
  and outputs a full summary with links.
argument-hint: "[sprint name] - e.g. 'Mobile Engine 26S06'"
---

# Sprint Planner Skill

## Overview

Single interactive flow to prepare a new sprint. The skill collects all inputs
upfront, executes all steps, and outputs a summary with links and computed numbers.

## How to Invoke

When the user asks to prepare/plan a sprint, follow this flow:

### Phase 1: Collect Inputs

Ask the user for ALL of the following in a single prompt:

1. **Sprint name** (if not already provided)
   - Format: `{Team Name} {YY}S{Sprint Number}`
   - Example: `Mobile Engine 26S06`
2. **Team size** — number of engineers available (default: 5)
3. **Vacation days** — total person-days of PTO in the sprint (default: 0)

### Phase 2: Execute

Once inputs are collected, execute all steps **without further prompts**.

#### Step 1: Ensure Sprint Exists

1. Find the board using `jira_get_agile_boards(board_name="{Team Name}")`
2. Check future sprints: `jira_get_sprints_from_board(board_id, state="future")`
3. Check active sprint: `jira_get_sprints_from_board(board_id, state="active")`
4. If sprint exists → note its ID and proceed
5. If not → create it using `jira_create_sprint`:
   - `board_id`: from step 1
   - `name`: full sprint name
   - Start/end dates: starts when active sprint ends, duration = 2 weeks

#### Step 2: Calculate Capacity

**Constants:**
- Sprint working days = 9 (10 weekdays minus 1 day for ceremonies)
- Support bucket % = 20%

**Formulas:**
```
gross_capacity   = team_size × 9
support_bucket   = 20% × gross_capacity
available        = gross_capacity - vacation_days - support_bucket
```

Convert support_bucket to Jira time format (e.g. 9d → `1w 4d`, where 1w = 5d).

#### Step 3: Create Support Bucket Story

**IMPORTANT:** Use the `/jira` skill to create the issue. Do NOT call the raw
`jira_create_issue` MCP tool directly — it requires exact field formats that
differ from what the docs suggest. The `/jira` skill handles field formatting,
classification, and team assignment correctly.

Invoke `/jira` with a request like:
> Create a Story in project MOB with summary "[Support Bucket] Engine {YY}S{NN}",
> assigned to Sasha Sidorenko, epic link MOB-9056, team Mobile Engine Team,
> sprint {sprint_name} (ID {sprint_id}), time estimate {support_bucket in Jira format},
> and classification "Support & Maintenance".

The `/jira` skill will show a confirmation — approve it to create the issue.

**Expected fields:**

| Field | Value |
|-------|-------|
| Type | Story |
| Summary | `[Support Bucket] Engine {YY}S{NN}` |
| Epic Link | `customfield_10014: "MOB-9056"` |
| Assignee | Sasha Sidorenko |
| Team | `customfield_10001` with Mobile Engine Team UUID from `jira/references/team-structure.json` |
| Sprint | target sprint via `customfield_10020` |
| Estimate | support_bucket value in Jira time format |
| Classification | Support & Maintenance |

Reference ticket: [MOB-16131](https://evinced.atlassian.net/browse/MOB-16131)

### Phase 3: Output Summary

After all steps complete, present a single summary:

```
## Sprint Ready: {sprint_name}

### Capacity
| Metric               | Value  |
|----------------------|--------|
| Team size            | {n}    |
| Gross capacity       | {x}d   |
| Vacation days        | {v}d   |
| Support bucket (20%) | {s}d   |
| **Available**        | **{a}d** |

### Created Issues
| Issue | Summary | Estimate | Link |
|-------|---------|----------|------|
| {key} | [Support Bucket] Engine {YY}S{NN} | {s}d | [link] |

### Sprint Info
- Sprint: {sprint_name} (ID: {id}, state: {state})
- Active sprint: {active_name} (ends {end_date})
```

## Reference

### Sprint Naming Convention
Format: `{Team Name} {YY}S{Sprint Number}`
- **YY**: short year (26 for 2026)
- **S**: literal
- **Sprint Number**: two-digit, two-week sprint number

### Jira Configuration
- Board: "Mobile Engine" (scrum)
- Team: "Mobile Engine Team" from `jira/references/team-structure.json`
- Epic for support buckets: MOB-9056 (`[Engine][Sprint Support Buckets]`)
- Project: MOB
