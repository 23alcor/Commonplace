# Lane B add-on: Decision 1 calibration (after your eval run; due 3:40 PM)
Using the routing decisions your eval already logs (both the baseline-free pipeline runs), for every routed
answer (note_type, folder, merge) record (confidence, was_correct). Then:
- eval/results/calibration.png: reliability diagram (confidence bins 0.5-0.6 ... 0.9-1.0 vs actual accuracy,
  diagonal = perfect), with bin counts, plus the 0.75 threshold marked.
- Expected calibration error (ECE) and: accuracy of auto-filed (>=0.75) vs escalated (<0.75) cases, and how
  often Neon fixed an escalated case the router would have gotten wrong.
- Add a short "Is Decision 1's confidence trustworthy?" section to eval/results/summary.md. Small n: say so.
No new API calls needed beyond your eval. Commit.
