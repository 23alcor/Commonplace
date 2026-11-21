---
type: project-update
created: 2026-11-15
tags: [batcave]
---

The free tier read cap was hit by 7am because of a polling query. Fix: cache the overview for 60 seconds and batch the habit reads. Part of [[Batcave Dashboard]].
