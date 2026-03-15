# Agent Skills

[Agent Skills](https://agentskills.io/specification) for Jira workflow automation and sprint planning. Works with any agent that supports the open standard — Claude Code, Cursor, GitHub Copilot, Windsurf, Gemini CLI, Kiro, and [others](https://agentskills.io).

## Installation

Install using the [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add evinced/agent-skills
```

Or manually — clone the repo and place skill directories where your agent expects them. For example, in Claude Code:

```bash
git clone <repo-url>
ln -s /path/to/agent-skills/jira ~/.claude/skills/jira
ln -s /path/to/agent-skills/sprint-master ~/.claude/skills/sprint-master
```

## Skills

### jira
Manage Jira issues with full workflow support — search, create, update, transition, link, and batch operations. Includes team structure, custom field mappings, and classification.

### sprint-master
Sprint lifecycle management for Team Leads — prepare sprints (create sprint, support bucket, capacity calc), plan sprints (validate estimates/assignees, team breakdown, suggest goals), and generate post-sprint KPI reports (velocity, planned vs. unplanned, completion rates).
