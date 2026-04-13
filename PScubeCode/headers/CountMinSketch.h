#ifndef _COUNTMINSKETCH_H
#define _COUNTMINSKETCH_H

// Count-Min Sketch for the Dynamic Threshold Decision module (Phase 1 of P-Scube).
// Provides lightweight, sub-linear frequency estimation of node activity
// within a sliding window to identify gamma-Heavy Hitter (Hub) candidates.

#include <cstring>
#include <cstdint>
#include <climits>

class CountMinSketch {
private:
    static const int CMS_DEPTH = 4;      // number of independent hash rows
    static const int CMS_WIDTH = 65536;  // columns (power-of-2 for fast masking)

    uint32_t table[CMS_DEPTH][CMS_WIDTH];
    uint32_t seeds[CMS_DEPTH];

    uint32_t cms_hash(uint32_t key, uint32_t seed) const {
        key ^= seed;
        key ^= key >> 16;
        key *= 0x45d9f3b;
        key ^= key >> 16;
        return key & (CMS_WIDTH - 1);
    }

public:
    CountMinSketch() {
        memset(table, 0, sizeof(table));
        seeds[0] = 0x9e3779b9u;
        seeds[1] = 0x517cc1b7u;
        seeds[2] = 0x27d4eb2fu;
        seeds[3] = 0xb5ad4ecdu;
    }

    // Increment frequency count for key
    void update(uint32_t key, uint32_t delta = 1) {
        for (int i = 0; i < CMS_DEPTH; i++)
            table[i][cms_hash(key, seeds[i])] += delta;
    }

    // Return minimum-biased frequency estimate for key
    uint32_t query(uint32_t key) const {
        uint32_t minVal = UINT32_MAX;
        for (int i = 0; i < CMS_DEPTH; i++) {
            uint32_t v = table[i][cms_hash(key, seeds[i])];
            if (v < minVal) minVal = v;
        }
        return minVal;
    }

    // Clear all counts (e.g. at window boundary)
    void reset() {
        memset(table, 0, sizeof(table));
    }
};

#endif // _COUNTMINSKETCH_H
