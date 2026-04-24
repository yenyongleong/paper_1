"""
Faithful (in semantics) Python re-implementations of TCM, GSS, and Scube.

Semantics mirror the C++ headers under BaselineCode/ and ScubeCode/:
  - TCM  (BaselineCode/headers/TCM.h)
    * `hashnum` independent width*depth tables of summed weights
    * edgeWeightQuery = min over tables of cell sum
    * nodeWeightQuery = min over tables of row (type=0) sum; uniform per-node work
  - GSS  (BaselineCode/headers/GSS.h)
    * one width*depth matrix; each bucket holds `slot_num` fingerprint-indexed rooms
    * inserts probe up to `p` candidate positions via seed rotation
    * edgeWeightQuery returns the fingerprint-matched room's weight (0 if none)
    * nodeWeightQuery scans r rows x width cols, fingerprint-matched; uniform per-node
  - Scube (ScubeCode/Scube/ScubeKick.h + DegDetector/DegDetectorSlot2bit.h)
    * per-node degree estimate drives A_v = addrQuery(node) in [2, 63]
    * insert probes addr_v + seed[0..A_v-1] rows  (A_v grows with degree)
    * nodeWeightQuery scans exactly A_v rows x width cols x ROOM, fingerprint-matched
    * WORK and ACCURACY both scale linearly with A_v  =>  both leak degree

The three sketches expose the SAME public API so attack code works against all:
    obj.insert(s, d, w=1)
    obj.edge_weight_query(s, d)        -> (weight, cells_scanned)
    obj.node_weight_query(v, type=0)   -> (weight, cells_scanned)

`cells_scanned` is our hardware-independent proxy for query latency -- it counts
the number of bucket probes, which is what the C++ timing channel ultimately
measures.
"""
from __future__ import annotations

import hashlib
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple


# ---------- hash utilities ----------------------------------------------------

def _h(i: int, x: int) -> int:
    """i-th independent 32-bit hash of an integer key.

    Uses md5 with a salt byte per `i`, then truncates to 32 bits. Cheap and
    stable; suitable for experiments -- not cryptographic claims.
    """
    m = hashlib.md5()
    m.update(bytes([i & 0xFF]))
    m.update(int(x).to_bytes(8, "little", signed=False))
    return int.from_bytes(m.digest()[:4], "little")


# ---------- TCM ---------------------------------------------------------------

class TCM:
    """
    Multi-matrix Count-Min-like sketch (matches BaselineCode/headers/TCM.h).
    No fingerprints; every edge (s,d) adds `w` to cell (h(s)%depth, h(d)%width).
    Query = min over tables to suppress collisions.
    """
    def __init__(self, width: int, depth: int, hashnum: int = 3):
        self.W, self.D, self.H = width, depth, hashnum
        self.tables = [np.zeros(depth * width, dtype=np.uint64) for _ in range(hashnum)]

    def insert(self, s: int, d: int, w: int = 1):
        for i in range(self.H):
            r = _h(i, s) % self.D
            c = _h(i + 100, d) % self.W
            self.tables[i][r * self.W + c] += w

    def edge_weight_query(self, s: int, d: int):
        best = None
        for i in range(self.H):
            r = _h(i, s) % self.D
            c = _h(i + 100, d) % self.W
            v = int(self.tables[i][r * self.W + c])
            best = v if best is None else min(best, v)
        # per-query work: H table lookups
        return (best or 0), self.H

    def node_weight_query(self, v: int, type: int = 0):
        # type=0: row-sum in each table, take min
        best = None
        for i in range(self.H):
            if type == 0:
                r = _h(i, v) % self.D
                s = int(self.tables[i][r * self.W : (r + 1) * self.W].sum())
            else:
                c = _h(i + 100, v) % self.W
                s = int(self.tables[i].reshape(self.D, self.W)[:, c].sum())
            best = s if best is None else min(best, s)
        # per-query work: H full rows/cols
        work = self.H * (self.W if type == 0 else self.D)
        return (best or 0), work


# ---------- GSS ---------------------------------------------------------------

class GSS:
    """
    Mini-GSS (matches BaselineCode/headers/GSS.h semantics used for accuracy).
    - single matrix of width*depth buckets
    - each bucket has `slot_num` rooms, each holding (fp_src, fp_dst, idx, w)
    - insert scans up to `p` candidate positions (r x r grid, seed-rotated)
    - nodeWeightQuery scans r rows x width cols, keeps only fp-matching rooms
    Buffer overflow is collapsed into a single hash-map counter -- faithful
    enough for attack experiments that only read {edge, node} weights.
    """
    def __init__(self, width: int, depth: int, r: int = 8, p: int = 16,
                 slot_num: int = 2, fp_len: int = 12):
        self.W, self.D, self.r, self.p = width, depth, r, p
        self.slot_num, self.fp_len = slot_num, fp_len
        self.mask = (1 << fp_len) - 1
        # bucket rooms: arrays of (fp_src, fp_dst, idx, w) -- idx encodes (i1 | i2<<4)
        self.fp_src = np.zeros((depth * width, slot_num), dtype=np.int32)
        self.fp_dst = np.zeros((depth * width, slot_num), dtype=np.int32)
        self.idx    = np.zeros((depth * width, slot_num), dtype=np.int32)
        self.wt     = np.zeros((depth * width, slot_num), dtype=np.uint64)
        self.buffer: Dict[Tuple[int, int], int] = {}

    def _fp_h(self, x: int):
        hv = _h(0, x)
        g = hv & self.mask
        if g == 0: g = 1
        h = (hv >> self.fp_len)
        return g, h

    def _seeds(self, g: int):
        # GSS.h: tmp[i] = (tmp[i-1]*timer + prime) % bigger_p, timer=5, prime=739
        TIMER, PRIME, BIGP = 5, 739, 1048576
        seeds = [g]
        for _ in range(1, self.r):
            seeds.append((seeds[-1] * TIMER + PRIME) % BIGP)
        return seeds

    def insert(self, s: int, d: int, w: int = 1):
        g1, h1 = self._fp_h(s); h1 %= self.D
        g2, h2 = self._fp_h(d); h2 %= self.W
        t1 = self._seeds(g1); t2 = self._seeds(g2)
        key = g1 + g2
        TIMER, PRIME, BIGP = 5, 739, 1048576
        for _ in range(self.p):
            key = (key * TIMER + PRIME) % BIGP
            idx = key % (self.r * self.r)
            i1, i2 = idx // self.r, idx % self.r
            p1 = (h1 + t1[i1]) % self.D
            p2 = (h2 + t2[i2]) % self.W
            pos = p1 * self.W + p2
            combined = i1 | (i2 << 4)
            for j in range(self.slot_num):
                if self.idx[pos, j] == combined and self.fp_src[pos, j] == g1 and self.fp_dst[pos, j] == g2:
                    self.wt[pos, j] += w
                    return
                if self.fp_src[pos, j] == 0:
                    self.idx[pos, j] = combined
                    self.fp_src[pos, j] = g1
                    self.fp_dst[pos, j] = g2
                    self.wt[pos, j] = w
                    return
        # overflow -> buffer
        self.buffer[(s, d)] = self.buffer.get((s, d), 0) + w

    def edge_weight_query(self, s: int, d: int):
        g1, h1 = self._fp_h(s); h1 %= self.D
        g2, h2 = self._fp_h(d); h2 %= self.W
        t1 = self._seeds(g1); t2 = self._seeds(g2)
        key = g1 + g2
        TIMER, PRIME, BIGP = 5, 739, 1048576
        probes = 0
        for _ in range(self.p):
            key = (key * TIMER + PRIME) % BIGP
            idx = key % (self.r * self.r)
            i1, i2 = idx // self.r, idx % self.r
            p1 = (h1 + t1[i1]) % self.D
            p2 = (h2 + t2[i2]) % self.W
            pos = p1 * self.W + p2
            combined = i1 | (i2 << 4)
            probes += self.slot_num
            for j in range(self.slot_num):
                if (self.idx[pos, j] == combined and
                    self.fp_src[pos, j] == g1 and
                    self.fp_dst[pos, j] == g2):
                    return int(self.wt[pos, j]), probes
        if (s, d) in self.buffer:
            return int(self.buffer[(s, d)]), probes
        return 0, probes

    def node_weight_query(self, v: int, type: int = 0):
        g1, _ = self._fp_h(v)
        hv = _h(0, v)
        t1 = self._seeds(g1)
        total = 0
        probes = 0
        if type == 0:
            h1 = (hv >> self.fp_len) % self.D
            for i in range(self.r):
                p1 = (h1 + t1[i]) % self.D
                row = slice(p1 * self.W, (p1 + 1) * self.W)
                # fp-match: only rooms with idx low-nibble == i and fp_src == g1 count
                fp_match = (self.fp_src[row] == g1)
                idx_match = (self.idx[row] & 0x0F) == i
                total += int(self.wt[row][fp_match & idx_match].sum())
                probes += self.W * self.slot_num
        else:
            h1 = (hv >> self.fp_len) % self.W
            for i in range(self.r):
                p1 = (h1 + t1[i]) % self.W
                col = self.idx.reshape(self.D, self.W, self.slot_num)[:, p1, :]
                fp_match = (self.fp_dst.reshape(self.D, self.W, self.slot_num)[:, p1, :] == g1)
                idx_match = ((col >> 4) & 0x0F) == i
                wts = self.wt.reshape(self.D, self.W, self.slot_num)[:, p1, :]
                total += int(wts[fp_match & idx_match].sum())
                probes += self.D * self.slot_num
        # sum buffer
        if type == 0:
            for (s2, _d2), w in self.buffer.items():
                if s2 == v: total += w
        else:
            for (_s2, d2), w in self.buffer.items():
                if d2 == v: total += w
        return total, probes


# ---------- Scube -------------------------------------------------------------

class Scube:
    """
    Scube (matches ScubeCode/Scube/ScubeKick.h + DegDetectorSlot2bit).
    - degree detector estimates d_v and assigns A_v in [A_MIN, A_MAX]
    - insert stores (fp_src, fp_dst, ext=(i,j), w) in one of ROOM slots per cell
    - nodeWeightQuery scans A_v rows x width cols x ROOM, fp-matched
    - BOTH accuracy and work scale with A_v  =>  A_v ~ d_v
    """
    ROOM = 2
    A_MIN, A_MAX = 2, 63

    def __init__(self, width: int, depth: int, fp_len: int = 12,
                 theta: float = 8.0):
        self.W, self.D = width, depth
        self.fp_len, self.mask = fp_len, (1 << fp_len) - 1
        self.theta = theta  # scaling factor: A_v = min(A_MIN + floor(d/theta), A_MAX)
        N = width * depth
        self.fp_src = np.zeros((N, self.ROOM), dtype=np.int32)
        self.fp_dst = np.zeros((N, self.ROOM), dtype=np.int32)
        self.ext_s  = np.zeros((N, self.ROOM), dtype=np.int16)  # which seed-i it was stored under
        self.ext_d  = np.zeros((N, self.ROOM), dtype=np.int16)
        self.wt     = np.zeros((N, self.ROOM), dtype=np.uint64)
        self.occ    = np.zeros((N, self.ROOM), dtype=bool)
        # degree detector: simple exact counter -- we only need A_v = f(deg)
        # (DegDetectorSlot2bit is probabilistic but converges to this map)
        self.deg_out: Dict[int, int] = {}
        self.deg_in:  Dict[int, int] = {}

    def _fp_h(self, x: int):
        hv = _h(0, x)
        g = hv & self.mask
        if g == 0: g = 1
        h = (hv >> self.fp_len)
        return g, hv, h

    def _seed_row(self, fp_v: int, i: int):
        MUL, INC, MOD = 5, 739, 1048576
        s = fp_v
        for _ in range(i):
            s = (s * MUL + INC) % MOD
        return s

    def addr_query(self, v: int, type: int = 0) -> int:
        d = (self.deg_out if type == 0 else self.deg_in).get(v, 0)
        a = self.A_MIN + int(d // self.theta)
        return max(self.A_MIN, min(self.A_MAX, a))

    def insert(self, s: int, d: int, w: int = 1):
        self.deg_out[s] = self.deg_out.get(s, 0) + 1
        self.deg_in[d]  = self.deg_in.get(d, 0) + 1
        g_s, hv_s, _ = self._fp_h(s)
        g_d, hv_d, _ = self._fp_h(d)
        addr_s = (hv_s >> self.fp_len) % self.D
        addr_d = (hv_d >> self.fp_len) % self.W
        A_s = self.addr_query(s, 0)
        A_d = self.addr_query(d, 1)
        # look for an existing identical edge to accumulate
        for i in range(A_s):
            for j in range(A_d):
                row = (addr_s + self._seed_row(g_s, i)) % self.D
                col = (addr_d + self._seed_row(g_d, j)) % self.W
                pos = row * self.W + col
                for k in range(self.ROOM):
                    if (self.occ[pos, k] and
                        self.fp_src[pos, k] == g_s and self.fp_dst[pos, k] == g_d and
                        self.ext_s[pos, k] == i and self.ext_d[pos, k] == j):
                        self.wt[pos, k] += w
                        return
        # find first free room
        for i in range(A_s):
            for j in range(A_d):
                row = (addr_s + self._seed_row(g_s, i)) % self.D
                col = (addr_d + self._seed_row(g_d, j)) % self.W
                pos = row * self.W + col
                for k in range(self.ROOM):
                    if not self.occ[pos, k]:
                        self.occ[pos, k] = True
                        self.fp_src[pos, k] = g_s
                        self.fp_dst[pos, k] = g_d
                        self.ext_s[pos, k] = i
                        self.ext_d[pos, k] = j
                        self.wt[pos, k] = w
                        return
        # all rooms full -> drop (kick-out simplified). Not critical for attacks.

    def edge_weight_query(self, s: int, d: int):
        g_s, hv_s, _ = self._fp_h(s)
        g_d, hv_d, _ = self._fp_h(d)
        addr_s = (hv_s >> self.fp_len) % self.D
        addr_d = (hv_d >> self.fp_len) % self.W
        A_s = self.addr_query(s, 0)
        A_d = self.addr_query(d, 1)
        probes = 0
        for i in range(A_s):
            for j in range(A_d):
                row = (addr_s + self._seed_row(g_s, i)) % self.D
                col = (addr_d + self._seed_row(g_d, j)) % self.W
                pos = row * self.W + col
                probes += self.ROOM
                for k in range(self.ROOM):
                    if (self.occ[pos, k] and
                        self.fp_src[pos, k] == g_s and self.fp_dst[pos, k] == g_d and
                        self.ext_s[pos, k] == i and self.ext_d[pos, k] == j):
                        return int(self.wt[pos, k]), probes
        return 0, probes

    def node_weight_query(self, v: int, type: int = 0):
        g_v, hv, _ = self._fp_h(v)
        total = 0; probes = 0
        if type == 0:
            addr_v = (hv >> self.fp_len) % self.D
            A_v = self.addr_query(v, 0)
            for i in range(A_v):
                row = (addr_v + self._seed_row(g_v, i)) % self.D
                row_slice = slice(row * self.W, (row + 1) * self.W)
                fp_match = (self.fp_src[row_slice] == g_v) & self.occ[row_slice]
                ext_match = (self.ext_s[row_slice] == i)
                total += int(self.wt[row_slice][fp_match & ext_match].sum())
                probes += self.W * self.ROOM
        else:
            addr_v = (hv >> self.fp_len) % self.W
            A_v = self.addr_query(v, 1)
            for j in range(A_v):
                col = (addr_v + self._seed_row(g_v, j)) % self.W
                fp_reshape = self.fp_dst.reshape(self.D, self.W, self.ROOM)[:, col, :]
                occ_reshape = self.occ.reshape(self.D, self.W, self.ROOM)[:, col, :]
                wt_reshape  = self.wt.reshape(self.D, self.W, self.ROOM)[:, col, :]
                ext_reshape = self.ext_d.reshape(self.D, self.W, self.ROOM)[:, col, :]
                mask = (fp_reshape == g_v) & occ_reshape & (ext_reshape == j)
                total += int(wt_reshape[mask].sum())
                probes += self.D * self.ROOM
        return total, probes
