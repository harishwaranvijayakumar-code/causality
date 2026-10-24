
# Causality: Experimental Findings

## 1. Purpose

Causality investigates latency regressions in distributed traces by comparing baseline and degraded datasets, ranking candidate operations, and reporting evidence that may help engineers investigate possible causes.

The current experiments evaluate synthetic datasets with known injected regressions. They are intended to assess algorithm behavior under controlled conditions, not to demonstrate production accuracy.

## 2. Experimental setup

The experiment suite currently contains 12 scenarios:

- `single_regression`
- `multiple_regressions`
- `parent_only_regression`
- `serial_execution`
- `noisy_traces`
- `incomplete_traces`
- `parallel_child_regressions`
- `small_regression`
- `child_regression_unchanged_parent`
- `magnitude_10ns_noise_10pct`
- `magnitude_100ns_noise_0pct`
- `magnitude_100ns_noise_10pct`

The project compares two ranking approaches:

1. Simple latency-delta ranking.
2. Execution-aware ranking, which adjusts candidate scores using descendant regression evidence.

The evaluation uses known synthetic ground truth to measure top-1 and top-3 hits, precision, recall, and false attributions. Sensitivity experiments vary trace count, random seed, regression magnitude, and noise.

## 3. Main experiment-suite results

The recorded experiment-suite summary evaluated 11 scenarios. One scenario was unevaluable because it had no ground-truth regression.

| Metric | Simple ranking | Execution-aware ranking |
|---|---:|---:|
| Top-1 hit rate | 0.455 | 0.909 |
| Top-3 hit rate | 0.909 | 0.909 |
| Mean precision | 0.667 | 0.667 |
| Mean recall | 0.909 | 0.909 |
| False attributions | 7 | 7 |

### Interpretation

Execution-aware ranking substantially improved top-1 hit rate in this experiment suite. Top-3 hit rate, mean precision, mean recall, and total false attributions did not improve in the recorded aggregate results.

These results suggest that adjusting for descendant evidence can improve candidate ordering in the tested cases. They do not show that every candidate is correctly attributed or that the approach will generalize to real production traces.

## 4. Focused benchmark results

The focused benchmark evaluated three scenarios over 20 seeds and trace counts of 10, 25, and 50:

- `parent_only_regression`
- `parallel_child_regressions`
- `multiple_regressions`

### Parent-only regression

Both algorithms achieved top-1 and top-3 hit rates of 1.0, with precision and recall of 1.0 and zero false attributions.

This is a controlled case where the parent operation itself is the injected regression source.

### Parallel child regressions

Simple ranking achieved a top-1 hit rate of 0.0. Execution-aware ranking achieved a top-1 hit rate of 1.0.

Both achieved top-3 hit rates of 1.0, precision of approximately 0.667, recall of 1.0, and one false attribution per run. The checkout parent was falsely attributed in this benchmark.

### Multiple regressions

The recorded results matched the parallel-child scenario:

- Simple ranking top-1 hit rate: 0.0
- Execution-aware ranking top-1 hit rate: 1.0
- Top-3 hit rate: 1.0 for both
- Precision: approximately 0.667 for both
- Recall: 1.0 for both
- False attributions: one per run

### Interpretation

The focused benchmark indicates that execution-aware ranking can place injected child regression sources ahead of a parent whose latency increase reflects downstream work.

However, the parent false-attribution results show that the current heuristic does not eliminate incorrect candidate attribution. Identical outcomes across the tested trace counts do not establish general robustness beyond these scenarios.

## 5. Sensitivity results

The sensitivity analysis varies trace count across 10, 25, and 50 traces and uses 20 random seeds. The recorded results show:

| Scenario | Observed result |
|---|---|
| `small_regression` | Perfect recorded metrics |
| 10 ns regression with 10% noise | Top-1 hit rate varied from 0.75 to 0.80 across trace counts; false-attribution rate varied between 0.35 and 0.65 |
| 100 ns regression without noise | Perfect recorded metrics |
| 100 ns regression with 10% noise | Top-1 hit rate remained 1.0; precision was approximately 0.80 at 10 traces and 0.775 at 25 and 50 traces; false-attribution rate was approximately 0.40 and 0.45, respectively |

The two algorithms produced the same results in these recorded sensitivity scenarios.

### Interpretation

Noise can change which operation appears to have regressed, especially when the injected change is small relative to the measurement variation. A correct top-1 result does not necessarily imply high precision because other operations can also be incorrectly flagged.

The recorded results for the small-regression scenario are not sufficient to conclude that small regressions are consistently detectable. The noisy 10 ns scenario provides direct evidence of unstable attribution.

## 6. Known failure cases and limitations

### Small regression under noise

In `magnitude_10ns_noise_10pct`, the recorded diagnostic output ranked inventory above payment. Inventory had an observed delta of 5 ns, while payment had an observed delta of -15 ns despite payment being the injected regression source.

This demonstrates that the observed latency delta can diverge from the injected ground truth under noise.

### Parent false attribution

A parent operation can show an increased duration because of downstream latency. The current execution-aware ranking discounts some parent candidates when descendant evidence is sufficiently large, but the focused benchmarks still record false attribution of the checkout parent.

### Synthetic data only

The experiments use controlled generated traces. They do not account for the full range of production conditions, including complex trace sampling, missing spans, clock behavior, changing workloads, heterogeneous dependencies, and varying concurrency.

### Heuristic evidence

Descendant regression evidence and evidence classifications are reporting signals, not proof of causation. The current method should be presented as candidate ranking for investigation.

### Evaluation limitations

The experiment-suite summary excludes an unevaluable scenario from aggregate metrics. False-attribution counts are measured according to the suite's evaluation definitions and should not be interpreted as unique real-world incidents.

## 7. Reproduction commands

Run these commands from the project root with the virtual environment active:

```powershell
python -m pytest -q
python run_experiments.py
python run_sensitivity_experiments.py
python run_focused_benchmark.py
python run_evidence_report.py
```

Expected responsibilities:

- `pytest` verifies the current automated test suite.
- `run_experiments.py` runs the general experiment suite.
- `run_sensitivity_experiments.py` evaluates sensitivity across trace counts and seeds.
- `run_focused_benchmark.py` evaluates the selected regression scenarios.
- `run_evidence_report.py` prints ranked candidates and their evidence classifications.

Record the actual output, Python version, code revision, and run date when creating a formal experiment report. The figures in this document reflect previously recorded runs and should be checked against fresh output before publication.

## 8. Engineering decisions

Based on the current evidence:

1. Preserve the current ranking algorithm while documenting its known limitations.
2. Keep evidence reporting separate from ranking logic so labels and explanations do not silently change scores.
3. Retain deterministic seeds and reproducible synthetic scenarios.
4. Continue testing small regressions, noisy traces, parallel children, and parent-only regressions.
5. Do not claim that the method proves causality or achieves a particular level of production accuracy.
6. Before integration into a web application, establish clear input validation, error handling, and a documented result schema.

## 9. Current conclusion

The current synthetic experiments provide preliminary evidence that execution-aware ranking improves top-1 attribution for selected scenarios involving downstream latency.

The evidence also shows that small regressions under noise and parent false attribution remain unresolved limitations. Further validation using more varied synthetic traces and, eventually, appropriately obtained real trace data is needed before making claims about real-world performance.
