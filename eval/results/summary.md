# Held-out evaluation

Dataset: synthetic demo vault. Scores include completed cases only; errors are reported separately.

| Method | Done / attempted | Folder acc | Link P | Link R | Link F1 | Verify pass | Median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 4 / 4 | 100.0% | 100.0% | 87.5% | 91.7% | 100.0% | 5.36s |

## Failures by capture

| Method | Media kind | Runs | Failures |
|---|---|---:|---:|
| baseline | handwritten | 1 | 0 |
| baseline | scanned_pdf | 1 | 0 |
| baseline | screenshot | 1 | 0 |
| baseline | voice_memo | 1 | 0 |

## Failures by difficulty

| Method | Difficulty | Runs | Failures |
|---|---|---:|---:|
| baseline | audio SNR <10 dB | 1 | 0 |
| baseline | blur <1 px | 2 | 0 |
| baseline | blur ≥1 px | 1 | 0 |

## Worst cases

- h003 (baseline, scanned_pdf): missed or extra links
- h001 (baseline, screenshot): passed
- h002 (baseline, handwritten): passed
- h004 (baseline, voice_memo): passed

![Accuracy by difficulty](accuracy_by_difficulty.png)
