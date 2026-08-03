---
incident_id: ""         # INC-YYYY-NNN
date: ""
severity: ""            # P1 | P2
duration: ""            # e.g. 47 minutes
author: ""
reviewers: []
status: draft           # draft | reviewed | closed
---

# Postmortem: [Short Title]

## Summary
One paragraph. What happened, what broke, how it was resolved.

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | Engineer paged |
| HH:MM | [key diagnostic step] |
| HH:MM | Root cause identified |
| HH:MM | Fix applied |
| HH:MM | Service restored |

## Root Cause
[Detailed explanation. No blame. Focus on the system condition that allowed this to happen.]

## Impact
- Duration of impact:
- Clients affected:
- SLO impact:

## What Went Well
- [thing]

## What Went Wrong
- [thing]

## Action Items
| Action | Owner | Due | PR/Issue |
|--------|-------|-----|----------|
| Update runbook for [X] | @name | [date] | |
| Update skill [X] | @name | [date] | |
| Fix [root cause] | @name | [date] | |

## Lessons Learned
[What does this teach us about the system or our process?]
