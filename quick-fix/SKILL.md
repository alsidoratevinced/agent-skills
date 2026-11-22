---
name: quick-fix
description: Use ONLY when explicitly invoked as `/quick-fix`, or when the request itself contains some form of the words "quick fix" or "quick task" — "quickfix", "quick-fix", "a quick fix for ...", including via integration mentions such as "@cursor quick fix ...", "@claude quick fix ...". Never infer it from a change merely looking small or lacking a Jira ticket. Creates a Jira ticket for a small change under a parent the request names, the project docs designate, or the best match found from the task and recent history — then branch, implement, verify, commit and open the PR following the project's own conventions.
---

# Quick Fix

Small, ticket-less changes still often need a Jira key: branch names, PR titles and CI
checks commonly require one. This skill creates that key as a child of a parent issue,
then carries the change through branch, implementation, verification, commit and PR.

Nothing project-specific is baked in. Every convention — Jira project, parent, branch
format, verification commands, PR rules — is **discovered** from the project's own
documentation and history (Step 1).

## When to Use

This skill is **explicitly triggered only**. Exactly two things start it:

1. It is invoked by command — `/quick-fix`
2. The request contains some form of the words **"quick fix"** or **"quick task"** —
   `quick fix`, `quickfix`, `quick-fix`, "a quick fix for …", "can you quick fix …",
   "quick task in PROJ-5555 …", including via integration mentions such as
   `@cursor quick fix ...`, `@claude quick fix ...`

**Never infer the trigger.** A change being one line, trivial, a config touch-up, or
simply lacking a ticket key is _not_ a trigger. Neither are "small fix", "just tweak", or
"minor cleanup" on their own. Without the command or the phrase, do the work the way you
normally would and leave ticketing alone.

A Jira key in the request is **not** a reason to skip the skill — it names the parent to
create under (Step 3), it is not the ticket to work on.

**Even when triggered, stop and ask instead when:**

- The work spans multiple files/commits or touches shared state, data formats, public
  interfaces, or migrations → it deserves its own ticket; ask the user
- The user only asked a question or asked you to investigate → answer first, no ticket

## Workflow

### Step 1 — Discover project conventions

Read the project's own docs before assuming anything. Check whichever exist — this skill
is agent-agnostic, so look at all of them, not just the one for your own tool:

- Agent/contributor docs: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CONTRIBUTING.md`,
  `README.md`, `.cursor/rules/`, `.github/copilot-instructions.md`, `docs/`
- PR rules: `.github/pull_request_template.md` and the workflows in `.github/workflows/`
  (look for title/branch checks)
- Git facts: default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`), and
  the shape of recent branch names and commit messages (`git log`, `git branch -r`)

Collect, as far as the sources state or imply them:

| Need                      | Where it usually lives                                        |
| ------------------------- | ------------------------------------------------------------- |
| Jira project key          | Docs, recent branch names/PR titles, the named parent key     |
| Default quick-fix parent  | A docs mention — see below                                    |
| Base branch               | Docs, else the repo's default branch                          |
| Branch name format        | Docs or CI check, else the pattern of recent branches         |
| Commit message convention | Docs, else recent `git log` (e.g. whether keys are included)  |
| Verification commands     | Docs (lint, format, test commands that apply to what changed) |
| PR title/body rules       | PR template, CI title check, docs                             |

**Default-parent hint.** Docs MAY name where quick fixes go — look for phrases such as
"quick fix parent", "quick-fix parent", "default parent", "support bucket", "quick task
epic", or any similar statement tying small changes to a specific issue, epic, or a
JQL/naming pattern for the current sprint's bucket. Treat it as the project's standing
answer for Step 3. A hint may be a fixed key (`PROJ-9056`) or a rule ("the current
sprint's `[Support Bucket]` story under epic PROJ-9056") — resolve rules live.

If a convention is missing and matters (no Jira project can be determined, or no way to
tell how to verify), ask rather than guess.

### Step 2 — Understand the task

Restate what will change, in one or two sentences, and confirm the scope is genuinely
small. If it isn't, say so and ask whether the work deserves a ticket of its own instead.

Read the relevant source before assuming field names, flags, or formats.

### Step 3 — Determine the parent

The new ticket is always a child of something. Use whatever Jira tooling is available in
this setup (MCP server, CLI, REST API) — the queries and field names matter, not the tool.

Resolve the parent with the first rule that applies:

**1. The request names a key** — as in "quick task in PROJ-5555, do X". Use it. Read its
issue type first, never assume it:

| Parent's type                | Create              | Notes                                                   |
| ---------------------------- | ------------------- | ------------------------------------------------------- |
| `Epic`                       | `Task` in the epic  | Sprint and Team are **not** inherited — set what's required |
| `Story`, `Task`, `Bug`, etc. | `Sub-task` under it | Sprint and Team **are** inherited — set neither         |
| `Sub-task`                   | nothing             | Sub-tasks cannot have children — see below              |

If the named key is itself a Sub-task, use that key directly for the branch and PR, say so,
and create no new issue. If the key does not exist or is in another project, stop and ask
rather than guessing a parent.

**2. The docs name a default parent** (Step 1) — resolve it to a concrete, **open** issue
(e.g. for a per-sprint bucket, the one in the active sprint; fall back to the newest if
none is active, preferring a bucket whose sprint state is `active`). State which parent
you picked and why before creating anything.

**3. Neither — infer the best parent.** Gather candidates from the task and recent history:

- **The task itself** — keywords, files, and areas it touches
- **Your recent Jira work** — issues assigned to or recently updated by the current user,
  especially open Stories/Tasks/Epics in the current sprint
- **The repo's recent history** — keys in recent commits, branch names, and PRs touching
  the same files or area (`git log -- <paths>`, `git branch -r`)
- **Open buckets/epics** — any support-bucket or maintenance-style parent the project uses

Score candidates by how directly they relate to the task (same area/files beats same
project) and by recency/openness. Then:

- **One clear leader** — clearly the closest match, open, and not tied → use it **without
  asking**. State which parent you picked and why, so the user can redirect.
- **No clear leader** (a tie, weak matches, or nothing open) → show the top 2–3 candidates
  with one line of reasoning each and ask which to use. Do not pick arbitrarily.

### Step 4 — Create the ticket

**Never use the parent's key as the ticket.** A parent — bucket, epic, or story — is a
container. Every quick fix gets its own key, and that key is what goes in the branch name
and PR title.

No exceptions:

- Not for one-line changes
- Not because the parent key is already at hand
- Not because a previous commit on the repo did it that way
- Not to "save a ticket"

The one exception is the Sub-task parent from Step 3, which cannot have children.

**Sub-task under a Story/Task/Bug (including a support bucket):**

```
project:     <project key>
issue type:  Sub-task
parent:      <parent key>
summary:     <short imperative summary>
description: <what and why, plus files/areas touched>
assignee:    <current Jira user>
```

That single create is the whole step — no follow-up field updates are needed.

- Do **not** set Sprint or Team on a Sub-task — it inherits both from the parent, and Jira
  commonly rejects a Team update with _"is a subtask, and inherits the team assignment
  from its parent"_
- Summary prefix: follow the convention visible in sibling Sub-tasks or the docs; absent
  one, keep it plain

**Task under an Epic:**

```
project:     <project key>
issue type:  Task
parent:      <epic key>
summary:     <short imperative summary, with any prefix the project uses on top-level issues>
description: <what and why, plus files/areas touched>
assignee:    <current Jira user>
fields:      Sprint = <active sprint id>
```

- Sprint and Team are not inherited from an epic. Set Sprint on create. Set Team too if
  the project uses it — copy the value from the epic or from recent sibling Tasks, and if
  the create rejects it, apply it in a follow-up update (accepted here because the issue
  is not a Sub-task)
- Look up field ids (Sprint, Team) through the tooling or from sibling issues; they differ
  per Jira instance. Sprint ids change when a sprint is renamed — re-fetch, don't reuse a
  remembered one

Either way, resolve the current user through the available tooling rather than hardcoding
an assignee. Report the new key and its browse URL to the user.

### Step 5 — Create the branch from the latest base branch

**Always branch from the freshly fetched base branch — never from the current branch.**

Whatever branch is checked out may be stale, already merged, or unrelated work. Fetch
first so the branch point is today's base, not a cached ref.

```bash
git fetch origin
git checkout -b <KEY>-short-summary origin/<base-branch>
```

- `<KEY>` is the key created in Step 4 — never the parent's key
- `<base-branch>` and the name format come from Step 1; absent a documented format, use
  `<KEY>-short-kebab-summary`
- Use `origin/<base-branch>` explicitly rather than checking out and pulling the local
  branch — it cannot pick up local drift
- Check the tree is clean first (`git status --short`); stash unrelated changes rather
  than carrying them onto the new branch

### Step 6 — Implement

Make the change. Keep it to the scope agreed in Step 2 — a quick fix that grows into a
refactor is no longer a quick fix; stop and ask.

### Step 7 — Verify before committing

Run the checks the project docs prescribe that apply to what changed (lint, format,
type-check, tests for the affected area). If the docs name none, look for the project's
standard entry points (`Makefile`, `package.json` scripts, CI workflow steps) and run
the narrowest relevant ones. If still nothing is discoverable, say so rather than
claiming it was verified.

Do not proceed to the PR while any check fails. Report actual output.

### Step 8 — Commit and open the PR

Follow the commit convention from Step 1 (e.g. whether the key belongs in the message or
only in the branch and PR title). Push, then open the PR with the available GitHub
tooling (CLI, MCP server, API), using the project's PR template if there is one:

- Title must satisfy any CI title check found in Step 1 (commonly `[KEY] <description>`)
- Replace any placeholder ticket link in the template with the key from Step 4
- Remove template sections that don't apply to a quick fix (e.g. PRD/design links)
- Fill in the summary of work; fill reviewer notes only if there is something non-obvious
- Check off the relevant checklist items

Report the PR URL and the Jira key together.

## Quick Reference

| Item                   | Value                                                              |
| ---------------------- | ------------------------------------------------------------------ |
| Parent, in order       | key in request → default parent in project docs → inferred best fit |
| Inferred parent        | clear leader: use it, say why · no leader: ask with top 2–3 options |
| Epic parent → create   | `Task`, Sprint (+ Team if used) set explicitly                     |
| Story/Task/Bug → create | `Sub-task`, Sprint + Team inherited — set neither                  |
| Sub-task parent        | use that key as-is; create nothing                                 |
| Branch                 | `<new key>-short-summary` from fresh `origin/<base>`, never the parent's key |
| PR title               | per CI check/docs, with the new key                                |

## Common Mistakes

| Mistake                                                  | Fix                                                                                 |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Running this skill because a change looked small         | Trigger is `/quick-fix` or the words "quick fix"/"quick task" only                  |
| Hardcoding project, board, or team values from memory    | Discover them from project docs, the named parent, and sibling issues               |
| Reading only your own tool's doc file                    | Check `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, etc.                |
| Using the parent's key as the ticket for the branch/PR   | Create a child; bucket, epic and story are containers, never the work item          |
| Ignoring a key named in the request                      | A named key is the parent — resolve its type first                                  |
| Ignoring a documented default parent                     | Step 3 rule 2 — use it before inferring                                             |
| Asking the user when there is one clear best parent      | Pick it, state why; ask only when there is no clear leader                          |
| Picking a parent arbitrarily when candidates are tied    | Ask, offering the top 2–3 with reasoning                                            |
| Assuming the named key's issue type                      | Read it; `Epic` → `Task`, `Story`/`Task`/`Bug` → `Sub-task`                         |
| Creating a `Sub-task` under an `Epic`                    | Epics take a `Task`; only Stories/Tasks/Bugs take Sub-tasks                         |
| Picking a closed bucket or sprint                        | Filter to open/active first                                                         |
| Setting Sprint or Team on a Sub-task                     | Both are inherited; Jira may reject a Team update outright                          |
| Omitting Sprint or Team on a `Task` under an epic        | Neither is inherited from an epic — set what the project uses                       |
| Leaving a placeholder ticket link in the PR description  | Replace with the real key from Step 4                                               |
| Branching off the current branch instead of the base     | `git fetch origin` then branch from `origin/<base-branch>`                          |
| Branching off a stale or already-merged branch           | Fetch first; the branch point must be today's base                                  |
| Opening the PR before checks pass                        | Step 7 is a gate, not a suggestion                                                  |
| Claiming verification when no checks were discoverable   | Say none were found                                                                 |
| Scope creep into a refactor                              | Stop, tell the user, ask for a real ticket                                          |
