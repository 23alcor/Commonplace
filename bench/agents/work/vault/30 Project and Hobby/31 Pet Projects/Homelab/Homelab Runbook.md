---
type: reference
created: '2026-11-21'
source: pdf
tags:
- homelab
- ubuntu
- tailscale
- tmux
- cron
- runbook
---

# Homelab Runbook

- **Box:** Headless Ubuntu
- **Reachability:** Tailscale + MagicDNS
- **Long jobs:** `tmux` sessions (survive SSH drop)
- **Cron:** Moved off laptop Nov 14

## Setup Checklist
- [ ] `tailscale up`
- [ ] `tmux new -s agents`
- [ ] ACL: only home devices

## Follow-ups
- [ ] Document exit nodes
- [ ] ACL cleanup after Nov 20 session
- [ ] Keep cron on the box, not laptop

## Related
- [[Homelab Server]]
- [[Tailscale]]
- [[tmux]]
- [[Cron jobs]]
- [[2026-11-14 Homelab - Moved cron jobs off laptop]]
- [[2026-11-20 Homelab - Tailscale ACL cleanup]]
