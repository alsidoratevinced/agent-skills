---
name: kanban-master
description: >
  Kanban board health and weekly reporting for Team Leads. Two flows:
  (1) Doctor — who on the team has too few (or no) tasks ready to pick up.
  (2) Done — what the team finished this week, one bullet per epic with who did it.
  Use for "kanban doctor", "kanban done", "who needs tasks", "what did we do this week".
argument-hint: "doctor | done [last week]"
---

# Kanban Master

Read-only reporting for a Kanban board — no sprints, no estimates, no buckets. Nothing is
created or changed in Jira.

## Configuration

Read `kanban-master/config.json` (copy `config.template.json` if missing):

| Key             | Meaning                                                              |
| --------------- | -------------------------------------------------------------------- |
| `atlassian_url` | Used for clickable links                                             |
| `board_id`      | The Kanban board to report on                                        |
| `team_name`     | Team in `jira/references/team-structure.json` — defines "the people" |
| `min_todo`      | A person with fewer ready tasks than this is flagged (default `2`)   |
| `todo_statuses` | Statuses that mean "ready to pick up" (default `Ready for work`, `Reopened`) |

Use the Atlassian Jira tools available in this setup (`jira_get_board_issues`,
`jira_search`); no tokens or scripts are needed. Always pass only the `fields` you need —
the `parent` field makes responses large — and paginate (`start_at`) until everything is read.

**People** = the members of `team_name` in `jira/references/team-structure.json`. Match
Jira assignees to members by display name (case-insensitive).

---

## Doctor

Answers: *who is about to run out of work?*

### Step 1 — Fetch ready tasks

```
jira_get_board_issues(board_id, limit=50, fields="summary,status,assignee",
  jql='status in ("Ready for work", "Reopened")')   # from config.todo_statuses
```

### Step 2 — Fetch in-progress tasks (context only)

```
jira_get_board_issues(board_id, limit=50, fields="summary,status,assignee",
  jql='statusCategory = "In Progress"')
```

In progress never changes who gets flagged — it only explains the row (someone with no
ready tasks but nothing in progress is idle, which is worse than someone busy).

### Step 3 — Count per person

For every team member, count ready tasks and in-progress tasks. Members with zero of both
still get a row. Ready tasks with no assignee are counted separately.

### Step 4 — Report

Flag each person: **None** (0 ready), **Short** (fewer than `min_todo`), or OK. Sort
None first, then Short, then OK; ties by fewest ready.

```
## Kanban Doctor: {team_name}

| Person | Ready | In progress | Status |
|--------|-------|-------------|--------|
| {name} | 0     | 0           | 🔴 None — idle |
| {name} | 0     | 2           | 🔴 None |
| {name} | 1     | 1           | 🟡 Short |
| {name} | 4     | 1           | OK |

**Unassigned ready tasks:** {n} — {key} {summary} ([link]), ...
```

Close with one line of takeaway, e.g. "2 people have no ready work; 3 unassigned tasks could
cover them." Keep the unassigned list to titles and links. Do not suggest reassigning —
that is the lead's call.

Notes:
- Assignees outside the team who hold ready tasks on the board are ignored, not flagged.
- If a status in `todo_statuses` returns nothing at all, mention it — the status may have
  been renamed.

---

## Done

Answers: *what did the team ship this week?*

### Step 1 — Work out the week

The week runs **Sunday through Friday, inclusive**.

- Today is Monday–Saturday → this week's Sunday through that week's Friday
- Today is **Sunday** → nothing has happened yet, so report the week that just ended
- The user says "last week" or gives dates → use those

State the range you used (e.g. `Sun 15 Nov – Fri 20 Nov`). Compute the dates with `date`,
don't guess them.

### Step 2 — Fetch finished tasks

Done means status category Done — this covers both `Done` and `Merged`.

```
jira_get_board_issues(board_id, limit=50, fields="summary,assignee,parent,resolutiondate",
  jql='statusCategory = Done AND resolved >= "{sunday}" AND resolved < "{saturday}"')
```

`resolved < saturday` is what makes Friday inclusive. Paginate until `total` is covered.

### Step 3 — Group by epic

- Use the issue's `parent` when its type is `Epic`
- If the parent is a Story/Task (the issue is a Sub-task), look up that parent's own epic
- No epic → group under **No epic**

### Step 4 — Report

One bullet per epic, highest-level wording: a single short phrase for what moved, then the
people who did it. No ticket lists, no keys, no per-ticket detail unless asked.

```
## Kanban Done: {team_name} — {Sun d Mon} – {Fri d Mon}

- **{Epic name}** — {one phrase summarizing what was finished} — {Person, Person}
- **{Epic name}** — {phrase} — {Person}
- **No epic** — {phrase} — {Person}

{n} tasks finished across {m} epics.
```

Rules:
- Summarize from the ticket titles; do not invent outcomes the titles don't support
- List people by first name + last name, alphabetically, each once per epic
- Order epics by number of finished tasks, largest first; **No epic** last
- If nothing was finished, say so plainly instead of an empty list

---

## Common Mistakes

| Mistake                                                        | Fix                                                                   |
| -------------------------------------------------------------- | --------------------------------------------------------------------- |
| Counting `Open` as ready                                       | Ready means `todo_statuses` only — `Open` is backlog                  |
| Hiding people with no tasks                                    | Every team member gets a row, even with zero of everything            |
| Flagging people on in-progress counts                          | Flag on ready only; in-progress is context                            |
| Using `resolved <= friday`                                     | Resolution has a time — use `< saturday` so Friday is included        |
| Reporting an empty week on Sunday                              | On Sunday report the week that just ended                             |
| Treating only `Done` as done                                   | Use `statusCategory = Done` — `Merged` is done too                    |
| Fetching `parent` for the doctor flow                          | Not needed there; it bloats the response                              |
| Listing every ticket in Done                                   | One bullet per epic, high level                                       |
