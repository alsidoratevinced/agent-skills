# Repo Alignment Skill — Design

## Intent

Some of our repos have good process / agentic-workflow features that others don't have yet.
A skill that takes a list of repos, compares how each is set up for agents and dev process,
proposes what to port from repo to repo (and a few gaps no repo covers), and — for the items
the user approves — drives each one through `/quick-fix` (Jira ticket → branch → change →
verify → PR).

## Goals

- Inventory each repo across these areas:
  - **Agent rules** — `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules/`,
    `.github/copilot-instructions.md`; completeness and consistency
  - **Local skills / commands / agents / hooks** — `.claude/skills`, `.claude/commands`,
    `.claude/agents`, `.claude/settings.json` hooks & permissions, equivalents for other agents
  - **Review process** — PR templates, PR title/branch checks, AI review in CI, CODEOWNERS,
    review rules
  - **Process health** — stack-agnostic workflow checks: Jira-key enforcement, stale-PR
    handling, release/changelog flow, etc.
  - **Other QoL** — anything process/agentic that stands out, even if not on a checklist
- Present a **feature × repo matrix**; for each gap, name the **source repo** and what
  "porting" means (adapt, not blind copy).
- Separately list a small number of **improvements no repo has yet**, labelled as such.
- User approves row by row (feature × target repo).
- Each approved (feature, repo) pair → its own `/quick-fix` run (option A).

## Non-goals

- Test coverage.
- Stack-specific tooling: linters, formatters, type-checkers, test runners.
- Owning Jira parent resolution, branching, PR conventions — `quick-fix` already does this.

## Anti-goals

- Blind file copy that ignores the target repo's conventions (e.g. pasting a `CLAUDE.md`
  section that references the source repo's paths/commands).
- Acting on anything not explicitly approved.
- A fixed checklist that misses homegrown features — the point is discovering them.

## Approaches considered

1. **Single prose skill, like `quick-fix`** — agent reads repos, builds matrix, approves,
   invokes `/quick-fix`. Agent-agnostic; can notice unlisted homegrown features. Output
   may vary run to run. **← Chosen.**
2. Skill + deterministic inventory script — reproducible, but only finds what the script
   already knows about; works against the "find the nice homegrown thing" goal.
3. Subagent per repo + synthesis — fast for many repos, but Claude-only; breaks the
   repo's agent-agnostic promise.

Chosen: 1, with optional per-repo fan-out to subagents when the agent supports them,
sequential otherwise.

## Decided

- Execution granularity: **one quick-fix per (feature, repo)** — option A.
- Parent resolution per quick-fix: quick-fix's own rules (no alignment-level Epic).
- **Repo list lives in a config file**, `kanban-master`-style: `repo-alignment/config.json`
  (gitignored), copied from a shipped `config.template.json`. The user must be able to
  override, cherry-pick, or supply their own values per run.

### Repo list config

Just a list — nothing else:

```json
{
  "repos": [
    "~/Evinced/web-sdk",
    "~/Evinced/mobile-ios-sdk",
    "evinced/site-scanner"
  ]
}
```

Each entry is anything `git clone` understands, or a local path:

- local path — used as is
- `org/repo` — GitHub shorthand
- `https://…` or `git@host:org/repo.git` — any remote URL

A repo's name for cherry-picking is the last path segment without `.git`
(`web-sdk`, `mobile-ios-sdk`, `site-scanner`).

### Remote entries: reuse an existing clone first

For `org/repo` and URL entries, look for a clone already on disk before cloning:

1. Normalize the remote (drop protocol, user, `.git`, case) → `host/org/repo`.
2. Search for git repos whose `origin` (or any remote) normalizes to the same value:
   parents of the local-path entries in the config, the current working directory's
   parent, and common roots (`~/code`, `~/src`, `~/projects`, `~/dev`, `~/git`,
   `~/workspace(s)`, `~/Evinced`), a few levels deep — never a whole-home crawl.
3. Found one → use it (if several, prefer a main checkout over a worktree, then the most
   recently fetched; say which). `git fetch` before reading so the scan sees the current
   default branch, not stale local state.
4. Found none → `git clone --depth 1` (`gh repo clone` for the `org/repo` form) into a
   temp dir.

The resolved list shown before scanning says, per repo, which it is: local path,
**found clone at `<path>`**, or **will clone**.

**Don't disturb the user's checkout.** Reading happens on the fetched default branch
(`git show` / `git ls-tree` on `origin/<default>`, or a temp worktree). When a quick-fix
needs to change a reused clone, it works in a new `git worktree` off `origin/<base>`, not
in the user's working tree — their current branch and uncommitted changes stay untouched.

**Non-GitHub remotes:** scan works the same; quick-fix pushes the branch and hands the
user the link to open the MR/PR themselves.

Resolving the set for a run, from the request:

| Request says                              | Set used                         |
| ----------------------------------------- | -------------------------------- |
| nothing about repos                       | the whole list                   |
| names from the list (`web-sdk`)           | cherry-pick: just those          |
| paths / `org/repo` values not in the list | override: exactly those          |
| "plus X"                                  | list (or picked subset) + X      |
| "without X"                               | list (or picked subset) − X      |

- Before scanning, show the resolved list in one line and wait for go — cheap guard
  against a wrong set.
- No config and no repos in the request → ask for them (and offer to write `config.json`).
- Unknown short name → say so and ask; never guess a path.
- Scope: processes and agentic flow; stack-based health checks out.

## Calls made by Claude (correct if wrong)

- **Name:** `repo-alignment`.
- **Clone discovery:** search roots and depth as listed under "Remote entries"; reused
  clones are changed only through a new worktree.
- **Approval = scope approval:** an approved row counts as the agreed scope for quick-fix,
  so its "multi-file → ask for a real ticket" guard doesn't re-block a port that needs,
  e.g., a workflow file plus its config. Anything beyond the approved row still stops.
- **Stateless:** no saved state between runs; works the same for a one-off or repeated use.
  The matrix is shown in the conversation (optionally saved as markdown if the user asks).
- **Trigger:** explicit — `/repo-alignment` or a request to compare/align repos' agent
  setup or dev process. Not inferred from single-repo work.
- **Packaging:** `repo-alignment/SKILL.md`, `repo-alignment/config.template.json`, README
  entry, `marketplace.json` plugin entry.

## Left to the builder

- Exact wording of the inventory checklist (as hints, explicitly non-exhaustive).
- Matrix layout and how adaptation notes are phrased.
- Order of quick-fix runs (suggest: grouped by repo, so each repo's context is loaded once).
