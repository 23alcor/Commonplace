# Lane A task: fix the "parent folder" failures (due 3:35 PM, then Lane B re-runs)
Eval failures (README "Where it still fails"): the PHYS 230 memo went to the parent academic folder, the
Fault detection concept went under a course, the Plant Watering Bot capture went to Sessions/. Same cause:
the router/manager pick a generic or parent folder because folder names alone don't say what belongs there.
Fix: give Decision 1's folder choices and Neon's prompt a one-line description of each folder, built from
the vault itself: the hub note in that folder (note whose title matches the folder, or type course/project/hub),
its first sentence + its `type`, plus 3 example child titles. Concepts folder: "one note per reusable concept".
Prefer the most specific folder when a capture names a course/project. Keep it deterministic and cached
per vault load. Add a test on mock_vault. Don't change schemas. Commit by 3:35 and say "folder fix committed".
