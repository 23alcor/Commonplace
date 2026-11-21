# Lane B task: re-run after Lane A's folder fix (starts when main has "folder descriptions"; due 4:00 PM)
Merge main into lane-b, then re-run the SAME 15 cases (same media, same seeds) through the pipeline only
(baseline numbers stay). Add to README Results: a "What we changed after seeing failures" subsection with a
before -> after table (folder accuracy, link F1, verify pass, escalation, median latency) and which of the 3
listed failures are fixed or still failing. Also write eval/results/rerun.json with the after numbers:
{"folder_acc":..,"link_f1":..,"verify":..,"escalation":..,"latency_s":..}. Honest even if it doesn't improve.
