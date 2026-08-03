---
title: ""
platform: ""          # ocp | rosa | rosa-hcp | eks | acm | all
severity: ""          # P1 | P2 | P3
last_updated: ""
last_tested: ""
author: ""
---

# [Alert/Issue Name]

## Symptom
What the engineer sees — alert text, error message, or observable behaviour.

## Impact
What breaks for the client if this is not resolved.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check [what]
oc get [resource] -n [namespace]

# 2. Check [what]
oc describe [resource] [name] -n [namespace]

# 3. Check [what]
oc logs [pod] -n [namespace] --tail=50
```

## Common Causes

### Cause 1: [Name]
**Symptoms:** what makes you think this is the cause
**Fix:**
```bash
[commands]
```

### Cause 2: [Name]
**Symptoms:**
**Fix:**
```bash
[commands]
```

## Escalation Criteria
Escalate to next level if:
- [ ] [condition]
- [ ] [condition]
- [ ] More than [X] minutes elapsed without progress

## Related
- Skill: [which skill covers this]
- Runbook: [related runbooks]
- Dashboard: [relevant Grafana dashboard]

## Change Log
| Date | Author | Change |
|------|--------|--------|
| | | Initial version |
