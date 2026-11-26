---
name: repo-alignment
description: Use when invoked as `/repo-alignment`, or when asked to compare or align several repos' agent setup or development process — agent rules (AGENTS.md, CLAUDE.md, Cursor/Copilot rules), local skills, commands and hooks, review pipelines, and stack-agnostic process checks. Finds what one repo does well that others lack, proposes ports and a few new improvements, and drives each approved item through `/quick-fix`. Not for single-repo work, test coverage, or stack-specific tooling (linters, formatters, type-checkers, test runners).
argument-hint: "[repo names | paths | urls] [plus X] [without X]"
---

# Repo Alignment

Some repos grow good process and agentic-workflow features — a sharp `AGENTS.md`, a local
skill, an AI review step in CI, a PR title check — that sibling repos never get. This skill
inventories a set of repos, shows what each has, proposes what to port where (and a few
gaps no repo covers yet), and drives each approved item through `/quick-fix`.

**Nothing changes — in any repo or in Jira — until the user approves a row.**

## Scope

| In                                                                | Out                                     |
| ----------------------------------------------------------------- | --------------------------------------- |
| Agent rules and instructions                                      | Test coverage                           |
| Local skills, commands, subagents, hooks, agent settings          | Linters, formatters, type-checkers      |
| Review process: PR templates, title/branch checks, AI review, CODEOWNERS | Test runners, build tooling       |
| Stack-agnostic process health: Jira-key enforcement, stale PRs, release/changelog flow | Anything tied to one language or framework |
| Any other process / agentic quality-of-life feature               |                                         |

## Configuration

Read `config.json` next to this file (copy `config.template.json` if missing). It holds
one thing — the repo list:

```json
{ "repos": ["~/code/web-sdk", "evinced/site-scanner", "git@github.com:evinced/ios-sdk.git"] }
```

An entry is a **local path**, GitHub shorthand **`org/repo`**, or any **remote URL**
(`https://…`, `git@host:org/repo.git`). A repo's **short name** is the last path segment
without `.git` (`web-sdk`, `site-scanner`, `ios-sdk`).

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

### Step 2 — Locate each repo

**Local path** → use it as is (it must be a git repo; if not, say so and drop it).

**`org/repo` or URL** → look for an existing clone before cloning:

1. Normalize the remote to `host/org/repo`: drop protocol, user (`git@`), `.git`, trailing
   slash; lowercase; `org/repo` means `github.com/org/repo`.
2. Search for git repos with any remote that normalizes to the same value, a few levels
   deep (≤ 3) — never crawl the whole home directory. Roots:
   - the parent directories of the config's local-path entries
   - the parent of the current working directory
   - `~/code`, `~/src`, `~/projects`, `~/dev`, `~/git`, `~/workspace`, `~/workspaces`,
     `~/Evinced` — whichever exist
3. **Found** → use it. If several match, prefer a main checkout over a worktree, then the
   most recently fetched; say which you chose.
4. **Not found** → `gh repo clone <org/repo> <tmp> -- --depth 1` for the shorthand, or
   `git clone --depth 1 <url> <tmp>` for a URL, into a fresh temp directory.

For every repo:

- `git fetch origin`
- Resolve the **default branch**: `git symbolic-ref --short refs/remotes/origin/HEAD`;
  else `git remote show origin` (the `HEAD branch:` line); else
  `gh repo view <org/repo> --json defaultBranchRef`. **Never assume `main`.**

Show the resolved list, one line per repo, and **wait for go**:

```
web-sdk       ~/code/web-sdk                  local path     default: main
site-scanner  ~/Evinced/site-scanner          found clone    default: develop
ios-sdk       git@github.com:evinced/ios-sdk  will clone     default: master
```

### Step 3 — Inventory

**Read from `origin/<default>`, never the working tree.** A reused clone may be on a
feature branch or have uncommitted changes; the scan must describe the repo as merged, and
the user's checkout must stay untouched:

```bash
git -C <repo> ls-tree -r --name-only origin/<default>
git -C <repo> show origin/<default>:<path>
```

For each repo, record every process or agentic feature you find. These are **starting
hints, not a checklist** — the point is to notice homegrown features no list would name:

- **Agent rules** — `AGENTS.md`, `CLAUDE.md` (any level), `GEMINI.md`, `.cursor/rules/`,
  `.cursorrules`, `.github/copilot-instructions.md`, `.windsurfrules`, `.codex/`. Note
  what they cover (setup, conventions, verification commands, PR rules, Jira parent) and
  what's missing or stale.
- **Local skills, commands, agents, hooks** — `.claude/skills/`, `.claude/commands/`,
  `.claude/agents/`, `.claude/settings.json` (hooks, permissions), `.mcp.json`,
  `.cursor/` commands, equivalents for other agents.
- **Review process** — `.github/pull_request_template.md`, PR title/branch checks in
  `.github/workflows/`, AI code review in CI, `CODEOWNERS`, required reviewers, review
  bots.
- **Process health** — Jira-key enforcement, stale-PR/issue handling, release and
  changelog automation, dependency update bots, branch hygiene.
- **Other QoL** — anything else process- or agent-related that makes working in the repo
  easier.

Skip everything in the Out column of the scope table.

If your agent supports subagents, you may inventory repos in parallel, one per repo; each
returns, per feature: a name, the files, and one line on what it does. Otherwise inventory
them one after another.

### Step 4 — Compare and propose

**Merge equivalent features into one row.** Rules in `AGENTS.md` in one repo and
`CLAUDE.md` in another are the same feature; an AI review via a GitHub Action and via a
review bot app are the same feature. Compare what a feature *does*, not its file name, and
mark a different-but-equivalent form as present, not as a gap.

Present three things:

**1. Matrix** — rows = features, columns = repos; `✓` present, `~` partial, `–` missing.

**2. Ports** — one row per (feature, target repo) gap:

| # | Feature | Target | Source | What to adapt |
| - | ------- | ------ | ------ | ------------- |

"What to adapt" is never empty. Name what in the source is specific to the source repo and
must change in the target: paths, commands, Jira project keys or parents, team names,
branch names, CI job names, tool versions. Porting means adapting, never copying blind.

**3. New improvements** — at most 5 things no repo has yet, labelled as new, each with the
repos it would apply to and one line on why. Numbered in the same sequence as ports so
they can be approved the same way.

Save this report as a markdown file only if the user asks.

### Step 5 — Approve

The user approves by row number — "1, 3, 5", "all ports for web-sdk", "everything except
4". Each approved row is one (feature, target repo) pair. Restate the approved list before
acting. **Never act on a row that wasn't approved**, and never widen a row's scope.

### Step 6 — Drive each approved row through `/quick-fix`

Group approved rows by target repo, so each repo's context is loaded once. For each row:

1. **Prepare a worktree** off the fresh base: `git -C <repo> worktree add <tmp-dir>
   origin/<default>` for a local or found clone. A clone this skill made in Step 2 is
   already disposable — use it directly (one row at a time, starting from
   `origin/<default>` each time).
2. **Invoke `/quick-fix`** with:
   - **working directory** = that worktree
   - **approved scope** = the row's feature, source → target, and its "what to adapt" notes
   quick-fix resolves the Jira parent, creates the ticket, branches, implements, verifies
   and opens the PR by the target repo's own conventions.
3. **Record** the Jira key and the PR link (or, for a non-GitHub remote, the merge-request
   link quick-fix hands back).
4. **Clean up** once the branch is pushed: `git -C <repo> worktree remove <tmp-dir>`.

**One quick-fix per row.** Never bundle several rows into one ticket or PR. If a row turns
out bigger than approved, quick-fix stops — relay that to the user and move to the next row.

### Step 7 — Summary

| # | Repo | Feature | Jira | PR / MR | Status |
| - | ---- | ------- | ---- | ------- | ------ |

Status is `opened`, `skipped` (with reason), or `failed` (with the error).

## Quick Reference

| Item              | Rule                                                                 |
| ----------------- | -------------------------------------------------------------------- |
| Repo list         | `config.json` → `repos`; request can cherry-pick, override, plus, without |
| Remote entry      | reuse an existing clone if found, else shallow clone to temp         |
| Default branch    | `origin/HEAD` → `git remote show origin` → `gh repo view`; never assume `main` |
| What to read      | `origin/<default>` via `git ls-tree` / `git show` — not the working tree |
| Equivalent forms  | one row, marked present                                              |
| Port row          | always has "what to adapt"                                           |
| Approval          | per (feature, repo) row; nothing happens without it                  |
| Execution         | one `/quick-fix` per row, in its own worktree, with the approved scope |

## Common Mistakes

| Mistake                                                        | Fix                                                                  |
| -------------------------------------------------------------- | -------------------------------------------------------------------- |
| Copying a file from the source repo as is                      | Adapt paths, commands, Jira keys, team names to the target           |
| Reading the working tree of a reused clone                     | Read `origin/<default>`; the user may be mid-branch                  |
| Checking out a branch in the user's own clone                  | Make a worktree; pass it to quick-fix                                |
| Assuming the default branch is `main`                          | Resolve it per repo                                                  |
| Flagging `AGENTS.md` vs `CLAUDE.md` as a gap                   | Compare what features do, not file names                             |
| Treating the hint list as the full checklist                   | Record anything process/agentic that stands out                     |
| Reporting linters, test runners or coverage                    | Out of scope                                                         |
| Acting on rows the user didn't approve                         | Only approved rows, restated first                                   |
| Bundling several rows into one quick-fix                       | One row → one ticket → one PR                                        |
| Guessing which repo an ambiguous short name means              | Ask                                                                  |
| Crawling the whole home directory for clones                   | Only the listed roots, ≤ 3 levels deep                               |
