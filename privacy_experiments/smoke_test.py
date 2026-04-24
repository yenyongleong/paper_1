"""Quick smoke test: insert 5000 edges, verify sketches don't blow up."""
import sys, time
sys.path.insert(0, "/Volumes/external_disk_macos /thesis/paper_1/privacy_experiments")
from sketches import TCM, GSS, Scube

import random
random.seed(0)

# Synthetic skewed stream
N = 5000
hubs = list(range(1, 11))
edges = []
for _ in range(N):
    if random.random() < 0.5:
        s = random.choice(hubs); d = random.randint(11, 500)
    else:
        s = random.randint(11, 500); d = random.randint(11, 500)
    edges.append((s, d, 1))

for name, Cls, kw in [
    ("TCM",   TCM,   dict(width=64, depth=64, hashnum=3)),
    ("GSS",   GSS,   dict(width=64, depth=64, r=4, p=8, slot_num=2, fp_len=10)),
    ("Scube", Scube, dict(width=64, depth=64, fp_len=10, theta=8.0)),
]:
    t0 = time.time()
    o = Cls(**kw)
    for s, d, w in edges:
        o.insert(s, d, w)
    t1 = time.time()
    # a few queries
    nq_work = []
    for v in hubs + [50, 100, 200]:
        w, work = o.node_weight_query(v, 0)
        nq_work.append((v, w, work))
    ew, ework = o.edge_weight_query(hubs[0], 12)
    print(f"{name:5s} build={t1-t0:.2f}s  edge_q({hubs[0]},12)={ew} (work={ework})")
    for v, w, work in nq_work[:5]:
        print(f"    node_q({v}) -> weight={w}, work={work}")
