"""
End-to-end privacy-attack experiment.

Loads a real graph stream (Dataset/sx-stackoverflow or wiki-talk subset), builds
each sketch, then runs three black-box attacks:

  1. Value channel         -- rank nodes by returned node-weight, measure
                              Precision@K recovery of true top-K hubs
  2. Timing channel        -- correlate per-query work (cell probes) with
                              true node degree, then threshold-classify hubs
  3. Edge-probing channel  -- ask edgeWeightQuery(s,d) on a balanced set of
                              real and fake edges, measure TPR/FPR

Results are saved as JSON + a CSV so plotting is separate from running.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sketches import TCM, GSS, Scube


# ---------- dataset loading ---------------------------------------------------

def load_edges(path: Path, limit: int) -> List[Tuple[int, int, int]]:
    edges = []
    with path.open() as f:
        for line in f:
            p = line.split()
            if len(p) < 2: continue
            s, d = int(p[0]), int(p[1])
            w = int(p[2]) if len(p) >= 3 else 1
            if s == d: continue
            edges.append((s, d, w))
            if len(edges) >= limit:
                break
    return edges


def compute_degrees(edges) -> Tuple[Dict[int,int], Dict[Tuple[int,int],int]]:
    deg_out: Dict[int, int] = {}
    weight_edge: Dict[Tuple[int, int], int] = {}
    for s, d, w in edges:
        deg_out[s] = deg_out.get(s, 0) + w
        weight_edge[(s, d)] = weight_edge.get((s, d), 0) + w
    return deg_out, weight_edge


# ---------- attacks -----------------------------------------------------------

def precision_at_k(pred_rank: List[int], true_set: set, K: int) -> float:
    return sum(1 for v in pred_rank[:K] if v in true_set) / K


def attack_value(sketch, nodes: List[int], deg_out: Dict[int,int], K_list=(10, 50, 100, 200)) -> dict:
    """Query all nodes, rank by returned node-weight, measure Precision@K."""
    est = {}
    for v in nodes:
        w, _ = sketch.node_weight_query(v, 0)
        est[v] = w
    pred = sorted(nodes, key=lambda v: est[v], reverse=True)
    true_ranked = sorted(nodes, key=lambda v: deg_out.get(v, 0), reverse=True)
    p_at_k = {}
    for K in K_list:
        true_top = set(true_ranked[:K])
        p_at_k[K] = precision_at_k(pred, true_top, K)
    # also compute ARE (average relative error) on the top 500 hubs -> utility
    top500 = true_ranked[:500]
    are_vals = []
    for v in top500:
        dv = deg_out.get(v, 0)
        if dv > 0:
            are_vals.append(abs(est[v] - dv) / dv)
    return {"precision_at_k": p_at_k, "ARE_top500": float(np.mean(are_vals)) if are_vals else None,
            "estimates": est}


def attack_timing(sketch, nodes: List[int], deg_out: Dict[int,int]) -> dict:
    """Per-query cell-probe count vs. true degree -- latency side-channel."""
    work = {}
    for v in nodes:
        _, cells = sketch.node_weight_query(v, 0)
        work[v] = cells
    # Pearson correlation (degree, work)
    x = np.array([deg_out.get(v, 0) for v in nodes], dtype=float)
    y = np.array([work[v] for v in nodes], dtype=float)
    if x.std() > 0 and y.std() > 0:
        r = float(np.corrcoef(x, y)[0, 1])
    else:
        r = 0.0
    # threshold classifier: top-K by work vs top-K by degree
    K = 100
    pred_rank = sorted(nodes, key=lambda v: work[v], reverse=True)
    true_ranked = sorted(nodes, key=lambda v: deg_out.get(v, 0), reverse=True)
    p_at_k = precision_at_k(pred_rank, set(true_ranked[:K]), K)
    return {"pearson_r": r, "precision_at_100_by_timing": p_at_k, "work": work}


def attack_edge_probe(sketch, real_edges: List[Tuple[int, int]],
                      fake_edges: List[Tuple[int, int]]) -> dict:
    """Membership inference: does edge (s,d) exist in the stream?"""
    # Get raw returned weight -- attacker thresholds at > 0
    real_scores = [sketch.edge_weight_query(s, d)[0] for s, d in real_edges]
    fake_scores = [sketch.edge_weight_query(s, d)[0] for s, d in fake_edges]
    # TPR/FPR at threshold > 0
    tpr_0 = sum(1 for s in real_scores if s > 0) / max(1, len(real_scores))
    fpr_0 = sum(1 for s in fake_scores if s > 0) / max(1, len(fake_scores))
    # ROC sweep
    scores = real_scores + fake_scores
    labels = [1] * len(real_scores) + [0] * len(fake_scores)
    order = np.argsort(-np.array(scores))
    labels_sorted = np.array(labels)[order]
    tp = np.cumsum(labels_sorted == 1)
    fp = np.cumsum(labels_sorted == 0)
    P = max(1, int((np.array(labels) == 1).sum()))
    N = max(1, int((np.array(labels) == 0).sum()))
    tpr = tp / P
    fpr = fp / N
    # AUC via trapezoid
    auc = float(np.trapezoid(tpr, fpr))
    return {
        "tpr_at_threshold_0": tpr_0,
        "fpr_at_threshold_0": fpr_0,
        "AUC": auc,
        "roc_tpr": tpr.tolist(),
        "roc_fpr": fpr.tolist(),
        "real_scores": real_scores,
        "fake_scores": fake_scores,
    }


# ---------- driver ------------------------------------------------------------

def run_one_dataset(name: str, edges_path: Path, n_edges: int,
                    W: int, D: int, out_dir: Path):
    print(f"\n=== {name}: loading up to {n_edges:,} edges ===")
    edges = load_edges(edges_path, n_edges)
    deg_out, edge_wt = compute_degrees(edges)
    print(f"[{name}] nodes(out-deg>0)={len(deg_out):,}  edges={len(edges):,}")

    # node sample for attacks: all nodes with deg>=1 is potentially huge
    # -> restrict to the union of (top-1000 hubs) + (2000 random nodes)
    ranked = sorted(deg_out.keys(), key=lambda v: deg_out[v], reverse=True)
    hub_set = ranked[:1000]
    random.seed(17)
    others = random.sample([v for v in deg_out if v not in set(hub_set)],
                           k=min(2000, len(deg_out) - len(hub_set)))
    attack_nodes = sorted(set(hub_set + others))
    print(f"[{name}] attack node sample size: {len(attack_nodes)}")

    # edge-probe attack set: 500 real edges (sampled from hub-incident), 500 fake
    real_edge_list = list(edge_wt.keys())
    random.shuffle(real_edge_list)
    real_edges = real_edge_list[:500]
    all_nodes = list(deg_out.keys())
    fake_edges = []
    real_set = set(real_edge_list)
    while len(fake_edges) < 500:
        s = random.choice(all_nodes); d = random.choice(all_nodes)
        if s != d and (s, d) not in real_set:
            fake_edges.append((s, d))

    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"dataset": name, "n_edges": len(edges),
               "n_nodes": len(deg_out), "W": W, "D": D,
               "skew": {"degree_histogram": None}}

    # Save degree histogram (log-log)
    degs = np.array(sorted(deg_out.values(), reverse=True))
    results["skew"]["degree_histogram"] = degs.tolist()

    sketch_configs = [
        ("TCM",   TCM,   dict(width=W, depth=D, hashnum=3)),
        ("GSS",   GSS,   dict(width=W, depth=D, r=8, p=16, slot_num=2, fp_len=12)),
        ("Scube", Scube, dict(width=W, depth=D, fp_len=12, theta=16.0)),
    ]
    per_sketch = {}
    for sname, Cls, kw in sketch_configs:
        print(f"  [{name}/{sname}] building... ", end="", flush=True)
        t0 = time.time()
        sk = Cls(**kw)
        for s, d, w in edges:
            sk.insert(s, d, w)
        t_build = time.time() - t0
        print(f"build={t_build:.1f}s  running attacks...", flush=True)

        rv = attack_value(sk, attack_nodes, deg_out)
        rt = attack_timing(sk, attack_nodes, deg_out)
        re = attack_edge_probe(sk, real_edges, fake_edges)
        per_sketch[sname] = {
            "build_seconds": t_build,
            "value": rv, "timing": rt, "edge": re,
        }
        print(f"     P@50={rv['precision_at_k'][50]:.2f}  "
              f"ARE_top500={rv['ARE_top500']:.3f}  "
              f"r(deg,t)={rt['pearson_r']:.3f}  "
              f"edge_AUC={re['AUC']:.3f}  "
              f"FPR@0={re['fpr_at_threshold_0']:.3f}")

    results["sketches"] = per_sketch
    # dump per-node (degree, work) and (degree, estimate) pairs to .npy for plotting;
    # strip them from JSON to keep file size manageable
    for sname in list(per_sketch.keys()):
        work = per_sketch[sname]["timing"].pop("work")
        est  = per_sketch[sname]["value"].pop("estimates")
        tp = np.array([[deg_out.get(v, 0), work[v]] for v in attack_nodes], dtype=float)
        ep = np.array([[deg_out.get(v, 0), est[v]]  for v in attack_nodes], dtype=float)
        np.save(out_dir / f"timing_pairs_{name}_{sname}.npy", tp)
        np.save(out_dir / f"value_pairs_{name}_{sname}.npy",  ep)
    out_path = out_dir / f"results_{name}.json"
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"[{name}] results -> {out_path}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", type=int, default=200_000,
                    help="number of edges to insert per dataset")
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--depth", type=int, default=512)
    ap.add_argument("--datasets", nargs="+",
                    default=["stackoverflow", "wiki-talk"])
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    data = root / "data"
    out = root / "results"
    for name in args.datasets:
        p = data / f"{name}.edges"
        if not p.exists():
            print(f"[skip] {p}"); continue
        run_one_dataset(name, p, args.edges, args.width, args.depth, out)


if __name__ == "__main__":
    main()
