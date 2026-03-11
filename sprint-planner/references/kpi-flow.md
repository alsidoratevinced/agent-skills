# Sprint KPI Flow

When the user asks for sprint **KPI**, **velocity**, **report**, or **metrics**, follow this flow.

## Prerequisites

The script requires `JIRA_EMAIL` and `JIRA_API_TOKEN` environment variables.
If not set, source them from the skill's `.env` file:

```bash
set -a && source sprint-planner/.env && set +a
```

## Phase 1: Collect Inputs

Ask the user for ALL of the following in a single prompt:

1. **Sprint name** (if not already provided)
   - If omitted, default to the most recently closed sprint, or the active sprint
2. **Team size** — number of engineers (default: 5)
3. **Vacation days** — total person-days of PTO (default: 0)
4. **Sick days** — total person-days of sick leave (default: 0)
5. **Support %** — percentage allocated to support (default: 20%)

## Phase 2: Run Script

Run the script at `sprint-planner/scripts/compute-kpi.py`:

```bash
python3 sprint-planner/scripts/compute-kpi.py \
  --board-name "Mobile Engine" \
  --sprint-name "{sprint_name}" \
  --team-size {team_size} \
  --vacation-days {vacation_days} \
  --sick-days {sick_days} \
  --support-pct {support_pct}
```

The script handles everything autonomously:
- Resolves board ID and sprint ID via Jira Agile REST API
- Fetches the GreenHopper Sprint Report (frozen snapshot at sprint close)
- Classifies planned vs. unplanned using `issueKeysAddedDuringSprint`
- Detects and excludes support bucket
- Computes capacity and sprint stats
- Outputs a markdown-formatted report

## Phase 3: Present Output

The script prints a markdown-formatted report to stdout. Present it directly to the user.

The output format:

```
## Sprint KPI: {sprint_name}

### Capacity
| Metric               | Value    |
|----------------------|----------|
| Team size            | {n}      |
| Gross days           | {x}d     |
| Vacation days        | {v}d     |
| Sick days            | {s}d     |
| Support days ({p}%)  | {sup}d   |
| **Net working days** | **{net}d** |

### Sprint Stats
| Metric           | Planned      | Unplanned    | Total         |
|------------------|-------------|-------------|---------------|
| Issues           | {n}         | {n}         | {n}           |
| Estimated days   | {n}d        | {n}d        | {n}d          |
| Done             | {n} ({p}%)  | {n} ({p}%)  | {n}/{planned} |
| Completed days   | {n}d        | {n}d        | {n}d          |
| Cancelled        | {n} ({d}d)  | {n} ({d}d)  | {n} ({d}d)    |

### Support Bucket
- {issue_key}: {summary} — {estimate}d ([link])

### Sprint Info
- Sprint: {name} (ID: {id}, state: closed)
- Dates: {start} → {end}
```
