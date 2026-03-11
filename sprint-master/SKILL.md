---
name: sprint-master
description: >
  Sprint lifecycle management for Team Leads. Three flows: (1) Prepare —
  create sprint, support bucket, capacity calc. (2) Plan — validate
  estimates/assignees, team breakdown, suggest goals. (3) KPI — post-sprint
  velocity report with planned vs. unplanned breakdown and completion rates.
argument-hint: "[sprint name] - e.g. 'Mobile Engine 26S06'"
---

# Sprint Planner Skill

## Overview

Three flows for sprint lifecycle management:

1. **Prepare** — create a new sprint, calculate capacity, set up support bucket
2. **Plan** — validate sprint readiness (estimates, assignees), team breakdown, suggest goals
3. **KPI** — post-sprint velocity report with planned vs. unplanned analysis

## Prepare Sprint

When the user asks to **prepare** or **create** a sprint, follow this flow:

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

---

## Plan Sprint

When the user asks to **plan a sprint**, follow this flow:

### Phase 1: Identify Sprint

If the sprint name is not provided, find the next upcoming sprint:
1. Find the board: `jira_get_agile_boards(board_name="Mobile Engine")`
2. Check future sprints: `jira_get_sprints_from_board(board_id, state="future")`
3. Check active sprint: `jira_get_sprints_from_board(board_id, state="active")`
4. Default to the future sprint, or active sprint if no future sprint exists

### Phase 2: Fetch All Sprint Tickets

Use `jira_get_sprint_issues(sprint_id, limit=50)` to get all issues.
If there are more than 50, paginate with `start_at` until all are retrieved.

For each issue, collect: key, summary, status, assignee, original estimate,
issue type, and parent/epic.

### Phase 3: Health Check

Flag issues with **missing required fields**. Only list tickets that have problems.

#### Missing Estimates
List tickets without an `originalEstimate` in `timetracking` (skip Cancelled tickets):

```
### Missing Estimates
| Issue | Summary | Assignee | Link |
|-------|---------|----------|------|
| {key} | {summary} | {assignee or "Unassigned"} | [link] |
```

#### Missing Assignees
List tickets without an assignee (with full detail — these need action):

```
### Missing Assignees
| Issue | Summary | Estimate | Link |
|-------|---------|----------|------|
| {key} | {summary} | {estimate or "—"} | [link] |
```

If everything is clean, output: **All tickets have estimates and assignees.**

### Phase 4: Breakdown by Team Member

Show a **stats-only** summary table — no individual ticket lists.
Group by assignee, show ticket count and total estimate per person.
Sort by total estimate descending. Convert estimates to days (1w = 5d, 1d = 8h).

```
### Team Breakdown
| Person | Tickets | Estimated | Notes |
|--------|---------|-----------|-------|
| {name} | {count} | {total}d  | {e.g. "+1 missing estimate", "2 blocked"} |
| ...    | ...     | ...       |       |
```

Include an "Unassigned" row if there are unassigned tickets.

### Phase 5: Suggest Sprint Goals

Analyze all ticket summaries, epics, and groupings to suggest **3–5 sprint goals**.

Guidelines for goals:
- Each goal should represent a meaningful **theme or deliverable**, not individual tickets
- Group related tickets into a single goal (e.g., multiple OCR tickets → "OCR feature kickoff")
- Exclude the support bucket from goals — it's overhead, not a goal
- Prefer action-oriented phrasing: "Ship X", "Complete Y", "Start Z"
- Order by estimated effort (largest first)
- **Titles only** — no descriptions or ticket key lists

```
### Suggested Sprint Goals
1. {Goal 1}
2. {Goal 2}
3. {Goal 3}
```

### Phase 6: Output

Combine all sections into a single summary:

```
## Sprint Plan: {sprint_name}

{Health Check section}

{Team Breakdown section}

{Suggested Sprint Goals section}

### Sprint Info
- Sprint: {sprint_name} (ID: {id}, state: {state})
- Total tickets: {count}
- Total estimated: {sum of all estimates}
```

---

## Sprint KPI

When the user asks for sprint **KPI**, **velocity**, **report**, or **metrics**,
follow the detailed flow in [`references/kpi-flow.md`](references/kpi-flow.md).

---

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
