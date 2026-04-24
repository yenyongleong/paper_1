# Privacy Leakage in Skew-Aware Graph Stream Summarization

Reproducible experiment comparing **TCM** (baseline, uniform per-node work),
**GSS** (baseline, uniform per-node work), and **Scube** (skew-aware allocation
`A_v = f(d_v)`) under three black-box query attacks, using real heavy-tailed
streams from `Dataset/`.

## Files
- `sketches.py`        — Python re-implementations of TCM/GSS/Scube with
                          the same query semantics as the C++ headers.
- `extract_subset.py`  — Slices `stackoverflow` and `wiki-talk` edge streams.
- `run_attacks.py`     — Builds each sketch on a dataset, runs three attacks,
                          dumps JSON + per-node (degree, work) and
                          (degree, estimate) pairs.
- `plot_results.py`    — Produces six figures in `figures/`.
- `results/`           — Raw metrics + `.npy` arrays.
- `figures/`           — Final plots.

## Reproduce
```
python3 extract_subset.py
python3 run_attacks.py --edges 150000 --width 512 --depth 512 \
                      --datasets stackoverflow wiki-talk
python3 plot_results.py
```

## Headline numbers (150k edges, 512×512 matrix)

| Attack channel            | Metric            | TCM      | GSS      | **Scube**  |
|---------------------------|-------------------|----------|----------|------------|
| Value (hub identification)| Precision@50      | 0.58–0.80| 1.00     | **1.00**   |
| Timing (latency)          | Pearson r(deg,t)  | 0.00     | 0.00     | **0.91–1.00** |
| Edge probing              | AUC               | 0.96–1.00| 1.00     | 1.00       |

**Key takeaway.** TCM/GSS have _constant per-node query work_; only Scube's
work scales linearly with node degree, opening a **timing side-channel unique
to skew-aware designs**. The efficiency mechanism _is_ the leakage mechanism.
