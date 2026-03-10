# Usage Examples

Example interactions showing how the Jira skill behaves.

## 1. Create a Simple Task

**User:** Create a task to update the CI pipeline config

**Skill behavior:**
1. Reads config.json for defaults (project: MOB, type: Task, team: Mobile Engine Team)
2. Asks for missing info: description, priority, epic, estimate, classification
3. Displays confirmation:
   ```
   About to create:
   - Project: MOB
   - Type: Task
   - Summary: Update the CI pipeline config
   - Assignee: Unassigned
   - Team: Mobile Engine Team
   - Classification: (asks user)
   - Estimate: None
   Proceed?
   ```
4. After creation: `Created: [MOB-15001](https://evinced.atlassian.net/browse/MOB-15001)`

## 2. Create a Bug with Team from Title Tag

**User:** Create a bug: [iOS] App crashes on launch after update

**Skill behavior:**
1. Detects `[iOS]` tag -> looks up "Mobile iOS Team" in team-structure.json
2. Sets team UUID: `3bc7088d-6cd8-47be-bf97-bc0c47da0a5b`
3. Sets issue type to Bug
4. Displays confirmation with iOS team pre-filled
5. Creates with correct team assignment

## 3. Create Task with Assignee

**User:** Create a task for oleksandr kholiavko: Implement new API endpoint, 3d estimate, under epic MOB-14735

**Skill behavior:**
1. Looks up "oleksandr kholiavko" in team-structure.json -> found in Mobile Engine Team
2. Sets team to Mobile Engine Team UUID automatically
3. Sets estimate to "3d", epic to "MOB-14735"
4. Displays full confirmation, creates on approval

## 4. Update an Existing Issue

**User:** Set MOB-14850 priority to High and add 2d estimate

**Skill behavior:**
1. Fetches MOB-14850 current state with `jira_get_issue`
2. Shows what will change:
   ```
   Updating MOB-14850:
   - Priority: Medium -> High
   - Estimate: None -> 2d
   Proceed?
   ```
3. After update: `Updated: [MOB-14850](https://evinced.atlassian.net/browse/MOB-14850)`

## 5. Search for Issues

**User:** Find all open bugs assigned to me

**Skill behavior:**
1. Translates to JQL: `project = MOB AND issuetype = Bug AND assignee = "Sasha Sidorenko" AND status != Done`
2. Calls `jira_search` with this JQL
3. Formats results as a table:
   ```
   | Key | Summary | Status | Priority |
   |-----|---------|--------|----------|
   | [MOB-14800](link) | Login crash on iOS 17 | In Progress | High |
   | [MOB-14750](link) | Memory leak in scanner | To Do | Medium |
   ```

## 6. Transition an Issue

**User:** Move MOB-14850 to In Progress

**Skill behavior:**
1. Calls `jira_get_transitions(issue_key="MOB-14850")` to get available transitions
2. Finds "In Progress" transition and its ID
3. Confirms: "Transition MOB-14850 to In Progress?"
4. Calls `jira_transition_issue` with the transition ID
5. Reports success with link

## 7. Batch Create from a List

**User:** Create these tasks under epic MOB-14735:
1. [Engine] Implement Section508 enum - 2d - oleksandr kholiavko
2. [iOS] Update XCUI scanner - 3d - Anton Yereshchenko
3. [Android] Fix Espresso timeout - 1d - Gil Becker

**Skill behavior:**
1. Parses 3 tasks, looks up teams from tags and assignees
2. Displays full breakdown:
   ```
   Batch create 3 tasks under MOB-14735:

   1. [Engine] Implement Section508 enum
      Team: Mobile Engine Team | Assignee: oleksandr kholiavko | Est: 2d
   2. [iOS] Update XCUI scanner
      Team: Mobile iOS Team | Assignee: Anton Yereshchenko | Est: 3d
   3. [Android] Fix Espresso timeout
      Team: Mobile Android Team | Assignee: Gil Becker | Est: 1d

   Proceed with all 3?
   ```
3. Creates sequentially, reports after each
4. Final summary with all links

## 8. Log Time on an Issue

**User:** Log 4 hours on MOB-14850

**Skill behavior:**
1. Calls `jira_add_worklog(issue_key="MOB-14850", time_spent="4h")`
2. Reports: "Logged 4h on [MOB-14850](https://evinced.atlassian.net/browse/MOB-14850)"

## 9. Link Issues

**User:** MOB-14848 is a duplicate of MOB-8721

**Skill behavior:**
1. Creates link: `jira_create_issue_link(link_type="Duplicate", inward_issue_key="MOB-14848", outward_issue_key="MOB-8721")`
2. Verifies by fetching both issues
3. Reports success with links to both
