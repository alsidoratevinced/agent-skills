# Agent Skills

[Agent Skills](https://agentskills.io/specification) for Jira workflow automation and Kanban reporting. Works with any agent that supports the open standard — Claude Code, Cursor, GitHub Copilot, Windsurf, Gemini CLI, Kiro, and [others](https://agentskills.io).

## Installation

Install using the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add evinced/agent-skills
```

Or, in Claude Code, install from the plugin marketplace:

```
/plugin marketplace add alsidoratevinced/agent-skills
/plugin install jira --marketplace alsidoratevinced/agent-skills
/plugin install kanban-master --marketplace alsidoratevinced/agent-skills
/plugin install quick-fix --marketplace alsidoratevinced/agent-skills
/plugin install repo-alignment --marketplace alsidoratevinced/agent-skills
```

Or manually — clone the repo and place skill directories where your agent expects them. For example, in Claude Code:

```bash
git clone <repo-url>
ln -s /path/to/agent-skills/jira ~/.claude/skills/jira
ln -s /path/to/agent-skills/kanban-master ~/.claude/skills/kanban-master
ln -s /path/to/agent-skills/repo-alignment ~/.claude/skills/repo-alignment
```

## Skills

### jira
Manage Jira issues with full workflow support — search, create, update, transition, link, and batch operations. Includes team structure, custom field mappings, and classification.

### quick-fix
Ticket-first workflow for small changes — triggered only by `/quick-fix` or the words "quick fix"/"quick task". Discovers project conventions from `AGENTS.md`/`CLAUDE.md`/`CONTRIBUTING.md`/PR templates, resolves the Jira parent (named key → documented default → best match from task and recent history), creates the ticket, then branches, implements, verifies, and opens the PR.

### kanban-master
Read-only Kanban reporting for Team Leads — **doctor** shows who on the team has no or too few ready tasks (plus unassigned ready work), and **done** summarizes what was finished Sunday–Friday, one bullet per epic with who did it. No sprints, estimates or support buckets; config is just the board and team.

### repo-alignment
Compares several repos' agent rules, local skills/commands/hooks, review pipelines and stack-agnostic process checks, then proposes what to port from one repo to another (adapted, not copied) plus a few new improvements. Each approved (feature, repo) item goes through `quick-fix` in its own worktree — one ticket, one PR. Repo list lives in `repo-alignment/config.json` (copy `config.template.json`); local paths, `org/repo` and git URLs are accepted, and existing clones are reused.
