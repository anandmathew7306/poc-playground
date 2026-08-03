# Postmortems

## Blameless Culture

Postmortems in this repository follow a **blameless** approach. We focus on system conditions, process gaps, and improvements — not individual fault.

## When to Write a Postmortem

- All P1 incidents require a postmortem within 48 hours
- P2 incidents require a postmortem if SLO impact occurred or root cause was non-obvious
- Near-misses that could have been P1 are encouraged

## Process

1. Copy `postmortems/_template.md` to `postmortems/INC-YYYY-NNN-short-title.md`
2. Fill in timeline from incident ticket and chat logs
3. Identify action items — every action item must have an owner and due date
4. Request review from at least one engineer not involved in the incident
5. Link the postmortem PR to the incident ticket
6. Update runbooks and skills as action items are completed

## Status Lifecycle

- `draft` — initial write-up in progress
- `reviewed` — peer review complete, action items assigned
- `closed` — all action items resolved or tracked in separate issues
