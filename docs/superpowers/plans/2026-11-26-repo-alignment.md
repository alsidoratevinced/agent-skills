# Repo Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `repo-alignment` skill that compares process/agentic setup across a list of repos, proposes ports and improvements, and drives each approved (feature, repo) pair through `/quick-fix`; teach `quick-fix` to work in a caller-supplied worktree with a caller-approved scope.

**Architecture:** Instruction-only skills (Markdown `SKILL.md`, agent-agnostic, no scripts), same style as `quick-fix/SKILL.md`. Config is a gitignored `config.json` copied from a shipped `config.template.json`, as in `kanban-master`. Registered in `.claude-plugin/marketplace.json` and `README.md`.

**Tech Stack:** Markdown skills (agentskills.io format: YAML frontmatter `name`, `description`), JSON config, `git`, `gh`.

**Spec:** `docs/superpowers/specs/2026-11-26-repo-alignment-design.md`

## Global Constraints

- Skill name and directory: `repo-alignment`.
- Agent-agnostic: no Claude-only tool names as requirements; subagent fan-out is optional ("if your agent supports subagents").
- Config file: `repo-alignment/config.json`, shape exactly `{"repos": [ ... ]}` — no other keys.
- Entry forms: local path · `org/repo` · `https://…` · `git@host:org/repo.git`. Short name = last path segment without `.git`.
- Scope in: agent rules, local skills/commands/agents/hooks, review process, stack-agnostic process health, other process/agentic QoL. Scope out: test coverage, linters, formatters, type-checkers, test runners.
- One `/quick-fix` per approved (feature, repo) pair. quick-fix resolves the Jira parent with its own rules.
- Never modify the user's working tree of a reused clone — reads from `origin/<default>`, changes in a new `git worktree`.
- Nothing is changed in any repo or in Jira without explicit row approval.
- Commit messages: no `Claude-Session:` trailer, no session links (user's global rule).

## Review Focus

1. **Reused clone is dirty or on a feature branch** — scan must still reflect `origin/<default>`, and the user's branch/uncommitted changes stay untouched. (Task 2, Step 3 content; Task 3 dry run check.)
2. **Two entries share a short name** (`evinced/web-sdk` and `~/forks/web-sdk`) — cherry-picking by `web-sdk` must ask, not pick one. (Task 2, Step 1 content.)
3. **Same feature, different form** (rules in `AGENTS.md` in one repo, `CLAUDE.md` in another; review via a GitHub Action vs. a bot app) — mark as equivalent, not a gap. (Task 2, Step 4 content.)
4. **Default branch unresolvable** (`origin/HEAD` not set, common in fresh clones of old repos) — fall back to `git remote show origin` / `gh repo view --json defaultBranchRef`; never assume `main`. (Task 2, Step 3 content.)
5. **Ported content leaks source-repo specifics** (paths, commands, Jira project keys, team names) — porting notes must name what to adapt. (Task 2, Step 4 content; Task 3 dry run check.)

---

### Task 1: quick-fix — caller-supplied working directory and approved scope

**Files:**
- Modify: `quick-fix/SKILL.md` (the "Even when triggered, stop and ask instead when" list; Step 5; Quick Reference; Common Mistakes)

**Interfaces:**
- Produces: a documented calling contract other skills use when invoking quick-fix:
  - **working directory** — a path to a prepared `git worktree` (already on a new branch or detached at `origin/<base>`). When given, quick-fix does all git work there and does not `checkout` in any other tree.
  - **approved scope** — a one-paragraph description of the change the user already approved. When given, the "spans multiple files/commits → ask" guard does not fire for work inside that scope; anything beyond it still stops and asks.

- [ ] **Step 1: Add a "Called by another skill" section** right after "When to Use", stating the two inputs above, that the trigger rule is satisfied when a skill invokes quick-fix on the user's approval, and that every other step (conventions, parent, ticket, verify, PR) is unchanged.

- [ ] **Step 2: Amend the guard list** — the "multiple files/commits" bullet gets: "unless the caller supplied an approved scope and the work stays inside it".

- [ ] **Step 3: Amend Step 5** — when a working directory was supplied: `cd` there, `git fetch origin`, create the branch with `git switch -c <KEY>-short-summary origin/<base-branch>` inside it; skip the "stash unrelated changes" advice (the worktree is clean by construction). Otherwise unchanged.

- [ ] **Step 4: Amend Step 8** — non-GitHub remote (no GitHub tooling applies): push the branch and give the user the host's MR/PR link instead of opening it.

- [ ] **Step 5: Add rows** — Quick Reference: `Caller-supplied worktree | all git work there; never checkout elsewhere`. Common Mistakes: `Checking out a branch in the user's own clone when a worktree was supplied | Work only in the supplied worktree`.

- [ ] **Step 6: Verify**

Run: `grep -n "working directory\|approved scope\|worktree" quick-fix/SKILL.md`
Expected: hits in the new section, the guard list, Step 5, Quick Reference and Common Mistakes. Read the whole file once: the default (no caller) flow must read exactly as before.

- [ ] **Step 7: Commit**

```bash
git add quick-fix/SKILL.md
git commit -m "quick-fix: accept caller-supplied worktree and approved scope"
```

---

### Task 2: repo-alignment skill, config template, registration

**Files:**
- Create: `repo-alignment/SKILL.md`
- Create: `repo-alignment/config.template.json`
- Modify: `.claude-plugin/marketplace.json` (add plugin entry)
- Modify: `README.md` (install line, symlink example, `### repo-alignment` section)
- Check: `.gitignore` already has `**/config.json` — no change expected

**Interfaces:**
- Consumes: Task 1's calling contract — invokes `/quick-fix` with **working directory** and **approved scope**.
- Produces: `/repo-alignment [names | paths | urls] [plus X] [without X]`.

- [ ] **Step 1: Write `config.template.json`**

```json
{
  "repos": [
    "~/path/to/local/checkout",
    "your-org/repo-name",
    "git@github.com:your-org/other-repo.git"
  ]
}
```

- [ ] **Step 2: Write `SKILL.md` frontmatter and intro**

- `name: repo-alignment`
- `description`: compares agent rules, local skills/commands/hooks, review pipelines and stack-agnostic process checks across several repos; proposes what to port between them and what to add; drives each approved item through `/quick-fix`. Use for `/repo-alignment` or requests to compare/align repos' agent setup or dev process. Not for single-repo work, test coverage, or stack-specific tooling.
- `argument-hint: "[repo names | paths | urls] [plus X] [without X]"`
- Intro: why (some repos have good features others lack), and that nothing changes without row approval.

- [ ] **Step 3: Write the workflow sections** (one `###` per step, in this order)

1. **Resolve the repo set** — read `repo-alignment/config.json` (template if missing); apply the spec's resolution table verbatim (nothing → all; names → cherry-pick; values not in list → override; "plus X"; "without X"). Short-name collision or unknown name → ask. No config and no repos → ask and offer to write `config.json`.
2. **Locate each repo** — local path as is; `org/repo` and URLs: normalize to `host/org/repo`, search the spec's roots a few levels deep (list the roots verbatim), match any remote, prefer main checkout over worktree then most recently fetched; else `git clone --depth 1` / `gh repo clone` into a temp dir. Resolve the default branch: `origin/HEAD`, else `git remote show origin`, else `gh repo view --json defaultBranchRef`; never assume `main`. `git fetch`. Show the resolved list (name · path · local / found clone / will clone · default branch) and wait for go.
3. **Inventory** — read from `origin/<default>` (`git ls-tree -r --name-only`, `git show origin/<default>:<path>`), never the working tree. Areas with starting hints (agent rules; skills/commands/agents/hooks/settings for Claude, Cursor, Copilot, Gemini, Codex; review process; stack-agnostic process health; other QoL), stated as **non-exhaustive** — record anything process/agentic that stands out. Explicitly skip the out-of-scope list. Optional per-repo subagent fan-out; each returns: feature name, files, one-line what it does.
4. **Compare** — normalize equivalent features under one row (Review Focus 3). Output:
   - Matrix: rows = features, columns = repos, cells `✓` / `~` (partial) / `–`.
   - **Ports**: per gap — `#`, feature, target repo, source repo, what to adapt (paths, commands, project keys, team names — Review Focus 5).
   - **New improvements** (no repo has it): at most 5, labelled as such, each with target repos.
   - Offer to save the report as markdown only if asked.
5. **Approve** — user approves by row number per (feature, target repo); "all ports for X", "skip 3" etc. are fine. Restate the approved list before acting. Unapproved rows are never acted on.
6. **Drive** — group approved rows by repo. Per row: create a worktree (`git worktree add <tmp> origin/<base>` for found/local clones; the temp clone itself is fine for fresh clones), then invoke `/quick-fix` with working directory = that worktree and approved scope = the row's text + adaptation notes. One quick-fix per row. After each: record Jira key + PR link (or MR link for non-GitHub). Clean up worktrees after the PR is pushed (`git worktree remove`).
7. **Summary** — table: row · repo · Jira key · PR/MR link · status (opened / skipped / failed with reason).

- [ ] **Step 4: Write Quick Reference and Common Mistakes tables** — at least: blind copy of source-repo specifics; reading the working tree instead of `origin/<default>`; checking out in the user's clone; assuming `main`; treating `AGENTS.md`-vs-`CLAUDE.md` as a gap; acting on unapproved rows; bundling several rows in one quick-fix; flagging linters/tests/coverage.

- [ ] **Step 5: Register**

- `marketplace.json` plugins: `{"name": "repo-alignment", "source": "./", "strict": false, "description": "Compare agent rules, skills, review pipelines and process checks across repos; port what works and drive approved changes through quick-fix.", "skills": ["./repo-alignment"]}`; metadata description gains "and repo alignment".
- README: `/plugin install repo-alignment --marketplace alsidoratevinced/agent-skills`, a symlink line, and a `### repo-alignment` section (2–3 sentences) noting it uses `quick-fix` and needs `config.json` from the template.

- [ ] **Step 6: Verify**

Run: `python3 -m json.tool .claude-plugin/marketplace.json >/dev/null && python3 -m json.tool repo-alignment/config.template.json >/dev/null && echo ok`
Expected: `ok`

Run: `head -5 repo-alignment/SKILL.md && git check-ignore repo-alignment/config.json`
Expected: frontmatter with `name: repo-alignment`; `repo-alignment/config.json` printed (ignored).

Run: `grep -c "origin/<default>\|worktree\|never assume\|equivalent\|adapt" repo-alignment/SKILL.md`
Expected: ≥ 5 (each Review Focus item has its instruction).

- [ ] **Step 7: Commit**

```bash
git add repo-alignment/ .claude-plugin/marketplace.json README.md
git commit -m "Add repo-alignment skill"
```

---

### Task 3: Dry run (scan only, no approval)

**Files:** none changed (scratch `config.json` is gitignored and deleted afterwards)

- [ ] **Step 1: Set up a two-repo run** — write `repo-alignment/config.json` with this repo's path and one other local repo the user names (ask if none obvious), plus one `org/repo` entry that already has a local clone, to exercise clone discovery.

- [ ] **Step 2: Run the skill in a fresh subagent** with the prompt "/repo-alignment — stop after the Compare step, do not approve anything", and the skill text as its instructions.

- [ ] **Step 3: Check the output against**
- resolved list shows the found clone (not "will clone") and a default branch per repo;
- `git -C <reused clone> status` and current branch are unchanged after the run;
- matrix has no linter/test/coverage rows;
- every port row has a non-empty "what to adapt";
- nothing was created in Jira, no branches pushed.

Fix `repo-alignment/SKILL.md` for any miss and re-run once.

- [ ] **Step 4: Clean up** — `rm repo-alignment/config.json`; if a fix was made, commit it: `git commit -am "repo-alignment: fixes from dry run"`.
