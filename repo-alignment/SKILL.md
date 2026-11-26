---
name: repo-alignment
description: Use when invoked as `/repo-alignment`, or when asked to compare or align several repos' agent setup or development process — agent rules (AGENTS.md, CLAUDE.md, Cursor/Copilot rules), local skills, commands and hooks, review pipelines, and stack-agnostic process checks. Finds what one repo does well that others lack, proposes ports, fixes and a few new improvements, and drives each approved item through `/quick-fix`. Not for single-repo work, test coverage, or stack-specific tooling (linters, formatters, type-checkers, test runners).
argument-hint: "[repo names | paths | urls] [plus X] [without X]"
---

# Repo Alignment

Some repos grow good process and agentic-workflow features — a sharp `AGENTS.md`, a local
skill, an AI review step in CI, a PR title check — that sibling repos never get. This skill
inventories a set of repos, shows what each has, proposes what to port where (plus broken
features to fix and a few gaps no repo covers yet), and drives each approved item through
`/quick-fix`.

**Nothing changes — in any repo, in GitHub settings, or in Jira — until the user approves
a row.** (Refreshing remote-tracking refs with `git fetch` / `git remote set-head` is not a
change: the user's branches, working tree and uncommitted work are never touched.)

## Scope

| In                                                                | Out                                     |
| ----------------------------------------------------------------- | --------------------------------------- |
| Agent rules and instructions                                      | Test coverage                           |
| Local skills, commands, subagents, hooks, agent settings          | Linters, formatters, type-checkers      |
| Review process: PR templates, title/branch checks, AI review, CODEOWNERS, rulesets | Test runners, build tooling |
| Stack-agnostic process health: Jira-key enforcement, stale PRs, release/changelog flow, having a dependency bot | Which stack tools a hook or bot runs (pre-commit linters, per-ecosystem settings) |
| Any other process / agentic quality-of-life feature               | Anything tied to one language or framework |

## Configuration

Read `config.json` next to this file (copy `config.template.json` if missing). It holds
one thing — the repo list:

```json
{ "repos": ["~/code/web-sdk", "evinced/site-scanner", "git@github.com:evinced/ios-sdk.git"] }
```

An entry is a **local path**, GitHub shorthand **`org/repo`**, or any **remote URL**
(`https://…`, `ssh://…`, `git@host:org/repo.git`).

A repo's **short name** is its repo name — the last segment of its `origin` URL without
`.git` (`web-sdk`, `site-scanner`, `ios-sdk`). For a local path, the directory name also
matches (useful when it is a worktree named something else).

## Workflow

### Step 1 — Resolve the repo set

Start from the config list and apply what the request says:

| Request says                              | Set used                        |
| ----------------------------------------- | ------------------------------- |
| nothing about repos                       | the whole list                  |
| short names from the list (`web-sdk`)     | cherry-pick: just those         |
| paths / `org/repo` / URLs not in the list | override: exactly those         |
| "plus X"                                  | list (or picked subset) + X     |
| "without X"                               | list (or picked subset) − X     |

Short names and own values may be mixed; the set is their union.

- **Unknown short name** → say so and ask. Never guess a path.
- **Two entries share a short name** (`evinced/web-sdk` and `~/forks/web-sdk`) and the
  request uses it → ask which one (or both). Don't pick silently.
- **No config and no repos in the request** → ask for them, and offer to write
  `config.json` with the answer.

### Step 2 — Locate each repo (no network yet)

**Local path** → use it as is; it must be a git repo (if not, say so and drop it). Its
`<remote>` is `origin` if present, else `upstream`, else none.

**`org/repo` or URL** → look for an existing clone before planning a clone:

1. **Normalize** a remote to `host/org/repo`: drop the scheme (`https://`, `ssh://`),
   user (`git@`) and port; turn scp-style `host:org/repo` into `host/org/repo`; drop
   `.git` and trailing `/`; lowercase. `org/repo` means `github.com/org/repo`. If the host
   is an SSH alias (e.g. `github.com-work`), resolve it with
   `ssh -G <alias> | awk '/^hostname /{print $2}'`.
2. **Search** for git repos (a directory with a `.git` dir or file) whose directory is at
   most **3 levels below** each root (`<root>/a/b/c` is the deepest; the root itself is
   not a candidate) — never crawl the whole home directory. Roots, whichever exist:
   - the parent directories of the config's local-path entries
   - the parent of the current repo's **main checkout**
     (`dirname $(git rev-parse --path-format=absolute --git-common-dir)`, then its parent) —
     the current directory may be a worktree
   - `~/code`, `~/src`, `~/projects`, `~/dev`, `~/git`, `~/workspace`, `~/workspaces`,
     `~/Evinced`
3. **Match** a candidate if any of its remotes normalizes to the target. Remember which
   remote matched — usually `origin`; in a fork clone it may be `upstream`. Below,
   `<remote>` means that remote.
4. **Found** → use it. If several match, prefer a main checkout (`.git` is a directory)
   over a worktree (`.git` is a file); worktrees share refs, so this only matters for
   where new worktrees are made from. Say which you chose.
5. **Not found** → mark **will clone**.

Show the resolved list — short name (the repo name), location, how it was found — one
line per repo, and **wait for go**:

```
web-sdk       ~/code/web-sdk                  local path
site-scanner  ~/Evinced/site-scanner          found clone (remote: origin)
ios-sdk       git@github.com:evinced/ios-sdk  will clone
```

After go:

- **Clone** each "will clone" repo into a fresh temp directory with a blobless clone —
  full history (quick-fix reads it), lazy file contents:
  `gh repo clone <org/repo> <tmp> -- --filter=blob:none` for the shorthand,
  `git clone --filter=blob:none <url> <tmp>` for a URL.
- **Fetch** each repo: `git fetch <remote>`. This only updates remote-tracking refs and
  tags; the user's branches, working tree and uncommitted changes stay untouched. If the
  fetch fails (offline, no access), say so — the repo would be scanned from stale refs —
  and ask whether to continue with it or drop it.
- **Resolve the default branch** — never assume `main`:
  `git remote set-head <remote> --auto` (refreshes a stale `<remote>/HEAD`), then
  `git symbolic-ref --short refs/remotes/<remote>/HEAD` and strip the `<remote>/` prefix;
  else `gh repo view <org/repo> --json defaultBranchRef` (GitHub only); else **ask the
  user**. Then show the default branch per repo (`<remote>/<default>`) in one line each,
  so a wrong ref is caught before the scan.
- **Local path with no remote** → it can only be a **source**: inventory its current
  `HEAD` and never make it a target.
- **Local path or found clone with unmerged work** → if its current branch has commits not
  on `<remote>/<default>` (`git log <remote>/<default>..HEAD`) or uncommitted changes that
  look process/agentic, say so in one line — the scan ignores them.

### Step 3 — Inventory

**Read files from `<remote>/<default>`, never the working tree.** A reused clone may be on
a feature branch or have uncommitted changes; the scan must describe the repo as merged:

```bash
git -C <repo> ls-tree -r --name-only <remote>/<default>
git -C <repo> show <remote>/<default>:<path>
```

For GitHub repos, review settings live on GitHub, not in files. Read them **read-only**
when `gh` is available: `gh api repos/<org>/<repo>/rulesets`,
`gh api repos/<org>/<repo>/rules/branches/<default>` (active rules, readable without
admin). Classic branch protection (`…/branches/<default>/protection`) returns 404 both
when absent and when you lack admin — report it as "unknown", not "none". If `gh` is
unavailable, say the settings weren't checked.

To tell whether a review bot or app is actually active, look at who reviewed or commented
on the last ~5 merged PRs (`gh pr list --state merged -L 5`, then their reviews).

For each repo, record every process or agentic feature you find. These are **starting
hints, not a checklist** — the point is to notice homegrown features no list would name:

- **Agent rules** — `AGENTS.md`, `CLAUDE.md` (any level), `GEMINI.md`, `.cursor/rules/`,
  `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules`, `.codex/`. Note
  what they cover (setup, conventions, verification commands, PR rules, Jira parent, temp
  files, do-not-edit files).
- **Local skills, commands, agents, hooks** — `.claude/skills/`, `.claude/commands/`,
  `.claude/agents/`, `.claude/settings.json` (hooks, permissions, enabled plugins),
  `.mcp.json`, `.cursor/` commands, equivalents for other agents.
- **Review process** — `.github/pull_request_template.md`, PR title/branch checks in
  `.github/workflows/`, AI code review (CI step, app config, ruleset), `CODEOWNERS`,
  rulesets and required checks, review policy docs, reviewer assignment.
- **Process health** — Jira-key enforcement, stale-PR/issue handling, release and
  changelog automation, dependency update bot, `CONTRIBUTING.md`.
- **Other QoL** — anything else process- or agent-related that makes working in the repo
  easier.

Also note what is **broken or stale**: a `CODEOWNERS` in a path GitHub doesn't read, a
policy doc contradicting the actual settings, rules referencing removed paths, a bot config
nobody runs.

Skip everything in the Out column of the scope table.

If your agent supports subagents, you may inventory repos in parallel, one per repo; each
returns, per feature: a name, the files or settings, one line on what it does, and any
breakage. Otherwise inventory them one after another.

### Step 4 — Compare and propose

**Define features by what they do, and by where they'd land.**

- **Equivalent forms are one feature.** Rules in `AGENTS.md` in one repo and `CLAUDE.md`
  in another; AI review via a GitHub Action and via a review app. A different-but-equivalent
  form counts as present.
- **Anything landing in the same file of a target is one row.** If a target needs several
  agent-rules additions (verification commands, PR conventions, temp-file rule), that is
  one row, "Agent rules: add X, Y, Z" — not one row each, which would yield conflicting
  PRs on the same file. The user can still approve a subset of the listed items.

Present:

**1. Matrix** — rows = features, columns = repos:
`✓` present · `~` partial · `–` missing · `n/a` doesn't apply to that repo (e.g. a
release flow for a repo that doesn't ship; a consumer-rollout skill elsewhere).

**2. Ports** — one row per (feature, target repo) where the target is `–` or `~`, ranked
by value. Show **high** and **medium** value rows in the table; list **low** ones in one
line under it, by number, so they can still be approved.

| # | Feature | Target | Source | Value | Kind | What to adapt |
| - | ------- | ------ | ------ | ----- | ---- | ------------- |

- **Source:** if several repos have it, pick the most complete and maintained one, and
  name the alternatives in "what to adapt".
- **Value:** `high` — prevents real mistakes or unblocks agents daily (rules, verification
  gate, review gates); `medium` — consistency and convenience; `low` — rarely exercised in
  the target (e.g. few PRs) or high setup cost for little gain.
- **Kind:** `PR` (files in the repo — goes through quick-fix), `settings` (GitHub
  rulesets, app installs, secrets — needs an admin; this skill doesn't change settings), or
  `PR + settings` (a file plus a setting, e.g. a title-check workflow that must also become
  a required check: the file goes through quick-fix, the setting goes to the summary).
- **What to adapt** is never empty. Name what in the source is specific to the source and
  must change in the target: paths, commands, Jira project keys or parents, team names
  and handles, branch names and base branch, CI job names, Slack channels, org-only apps
  that a personal or other-org repo can't install. Porting means adapting, never copying
  blind.

**3. Fixes** — broken or stale existing features from Step 3, same columns (Source = `—`).
If a fix and a port would touch the same file of a target, merge them into the Fixes row.

**4. New** — at most 5 things no repo has yet, labelled NEW, same columns (Source = `NEW`,
one row per target repo), with one line on why.

Number all rows in one sequence — Ports (table, then low), Fixes, New — so they are
approved the same way. Save this report as a markdown file only if the user asks.

### Step 5 — Approve

The user approves by row number — "1, 3, 5", "all ports for web-sdk", "everything except
4", "row 2 but only the PR-conventions part". Each approved row is one (feature, target
repo) pair. Restate the approved list before acting. **Never act on a row that wasn't
approved**, and never widen a row's scope.

### Step 6 — Drive each approved row

**`settings` rows, and the settings part of `PR + settings` rows,** are not changed by
this skill. Collect them for the summary with exact
steps (where in GitHub, what value, who needs to do it).

**`PR` rows (and the file part of `PR + settings`)** — group by target repo, so each repo's context is loaded once. For each row:

1. **Prepare a worktree** off the fresh base:
   `git -C <repo> worktree add --detach <tmp-dir> <remote>/<default>`.
   This works the same for a local path, a found clone, or a clone made in Step 2.
2. **Invoke `/quick-fix`** with:
   - **working directory** = that worktree
   - **remote and base branch** = the target's `<remote>` and `<default>`
   - **source** = the source repo's path @ `<remote>/<default>` and the files the feature
     lives in (none for NEW rows)
   - **approved scope** = the row's feature, source → target, the approved items, and its
     "what to adapt" notes

   quick-fix resolves the Jira parent, creates the ticket, branches, implements, verifies
   and opens the PR by the target repo's own conventions.
3. **Record** the Jira key and the PR link (or, for a non-GitHub remote, the merge-request
   link quick-fix hands back).
4. **Clean up** the worktree after each row, whether or not quick-fix finished:
   `git -C <repo> worktree remove <tmp-dir>` once the branch is pushed; if quick-fix
   stopped with uncommitted work, tell the user the worktree path and ask before
   `worktree remove --force`. The branch quick-fix created stays in the target clone's
   local branches — list it in the summary.

**One quick-fix per row.** Never bundle several rows into one ticket or PR. If a row turns
out bigger than approved, quick-fix stops — relay that to the user and move to the next
row.

### Step 7 — Summary

| # | Repo | Feature | Jira | PR / MR | Status |
| - | ---- | ------- | ---- | ------- | ------ |

Status is `opened`, `manual` (settings rows, with the steps), `skipped` (with reason), or
`failed` (with the error). Include each local branch quick-fix created per repo.

**Temp clones** made in Step 2 are removed when the run ends — after the summary, or
right after Step 4 even if nothing is approved.

## Quick Reference

| Item              | Rule                                                                 |
| ----------------- | -------------------------------------------------------------------- |
| Repo list         | `config.json` → `repos`; request can cherry-pick, override, plus, without |
| Short name        | repo name from `origin`; directory name also matches for local paths |
| Remote entry      | reuse an existing clone if found, else blobless clone to temp after go |
| Default branch    | `remote set-head --auto` → `symbolic-ref` (strip prefix) → `gh repo view`; never assume `main` |
| What to read      | `<remote>/<default>` via `git ls-tree` / `git show`; GitHub settings via read-only `gh api` |
| Rows              | equivalent forms = one feature; same target file = one row            |
| Sections          | Ports (ranked, low ones listed briefly) · Fixes · New (≤ 5)           |
| Every row         | Value, Kind (`PR` / `settings` / `PR + settings`), "what to adapt"   |
| Approval          | per row; nothing happens without it                                  |
| Execution         | `PR` rows: one `/quick-fix` each, in its own worktree · `settings` rows: steps in summary |

## Common Mistakes

| Mistake                                                        | Fix                                                                  |
| -------------------------------------------------------------- | -------------------------------------------------------------------- |
| Copying a file from the source repo as is                      | Adapt paths, commands, Jira keys, team handles, channels to the target |
| Reading the working tree of a reused clone                     | Read `<remote>/<default>`; the user may be mid-branch                |
| Checking out a branch in the user's own clone                  | Make a worktree; pass it to quick-fix                                |
| Assuming the default branch is `main`, or using `origin/origin/main` | Resolve it per repo; strip the remote prefix                   |
| Shallow (`--depth 1`) clone                                    | Blobless clone — quick-fix needs history                             |
| Flagging `AGENTS.md` vs `CLAUDE.md` as a gap                   | Compare what features do, not file names                             |
| Several rows editing the same target file                      | Merge them into one row with listed items                            |
| Porting something that makes no sense for the target           | Mark `n/a`                                                            |
| Treating the hint list as the full checklist                   | Record anything process/agentic that stands out                     |
| Ignoring broken features                                       | List them under Fixes                                                |
| Sending a GitHub-settings change through quick-fix             | Kind `settings`: steps in the summary                                |
| Reporting linters, test runners or coverage                    | Out of scope                                                         |
| Acting on rows the user didn't approve                         | Only approved rows, restated first                                   |
| Bundling several rows into one quick-fix                       | One row → one ticket → one PR                                        |
| Guessing which repo an ambiguous short name means              | Ask                                                                  |
| Crawling the whole home directory for clones                   | Only the listed roots, ≤ 3 levels deep                               |
