/*
 * Comprehensive Privacy Leakage Demo for Scube
 * ==============================================
 * Uses a Zipf (power-law) degree distribution to simulate a realistic
 * skewed graph, then demonstrates three query-level attacks:
 *
 *   Attack 1: Hub Extraction        — nodeWeightQuery reveals who the hubs are
 *   Attack 2: Sensitive Edge Probing — edgeWeightQuery confirms private relationships
 *   Attack 3: Timing Side-Channel   — query latency leaks degree class
 *
 * The degree distribution follows P(degree=k) ~ k^{-gamma}, matching
 * real-world networks like social graphs and financial transaction networks.
 */
#include <iomanip>
#include <algorithm>
#include <random>
#include <set>
#include <map>
#include <vector>
#include <fstream>
#include <numeric>
#include <cmath>
#include "Scube/ScubeKick.h"

using namespace std;

struct NodeResult {
    uint32_t id;
    uint32_t true_degree;
    int queried_weight;
    double latency_us;
};

struct EdgeProbe {
    uint32_t src, dst;
    bool truly_exists;
    int queried_weight;
    double latency_us;
};

static double avg(const vector<double>& v) {
    if (v.empty()) return 0;
    return accumulate(v.begin(), v.end(), 0.0) / v.size();
}

static double stdev(const vector<double>& v) {
    if (v.size() < 2) return 0;
    double m = avg(v);
    double sq = 0;
    for (auto x : v) sq += (x - m) * (x - m);
    return sqrt(sq / (v.size() - 1));
}

// Zipf distribution: returns values in [1, n] with P(k) ~ k^{-gamma}
static vector<int> generate_zipf_degrees(int num_nodes, double gamma,
                                          int min_deg, int max_deg, mt19937& rng) {
    // Build CDF for Zipf over [min_deg, max_deg]
    vector<double> weights;
    for (int k = min_deg; k <= max_deg; k++) {
        weights.push_back(1.0 / pow((double)k, gamma));
    }
    double total = accumulate(weights.begin(), weights.end(), 0.0);
    for (auto& w : weights) w /= total;

    // Build CDF
    vector<double> cdf(weights.size());
    cdf[0] = weights[0];
    for (size_t i = 1; i < weights.size(); i++)
        cdf[i] = cdf[i-1] + weights[i];

    uniform_real_distribution<double> unif(0.0, 1.0);
    vector<int> degrees(num_nodes);
    for (int i = 0; i < num_nodes; i++) {
        double u = unif(rng);
        auto it = lower_bound(cdf.begin(), cdf.end(), u);
        int idx = (int)(it - cdf.begin());
        degrees[i] = min_deg + idx;
    }
    return degrees;
}

int main() {
    ofstream out("privacy_demo_output.txt");
    auto& O = out;
    O << fixed << setprecision(4);

    const int TOTAL_NODES   = 5000;
    const double ZIPF_GAMMA = 1.2;
    const int MIN_DEGREE    = 2;
    const int MAX_DEGREE    = 3000;
    const int TOP_K_HUBS    = 50;    // ground-truth top-K for evaluation
    const int TIMING_REPEAT = 20;

    // ================================================================
    //  GENERATE ZIPF DEGREE SEQUENCE
    // ================================================================
    mt19937 rng(42);
    vector<int> degrees = generate_zipf_degrees(TOTAL_NODES, ZIPF_GAMMA,
                                                 MIN_DEGREE, MAX_DEGREE, rng);

    // Sort degree array to find the true top-K threshold
    vector<pair<int,int>> deg_rank; // (degree, node_id)
    for (int i = 0; i < TOTAL_NODES; i++)
        deg_rank.push_back({degrees[i], i + 1});
    sort(deg_rank.begin(), deg_rank.end(), greater<pair<int,int>>());

    set<int> true_hub_ids;
    for (int i = 0; i < TOP_K_HUBS; i++)
        true_hub_ids.insert(deg_rank[i].second);
    int hub_threshold = deg_rank[TOP_K_HUBS - 1].first;

    // ================================================================
    //  BUILD THE SCUBE INSTANCE AND INSERT EDGES
    // ================================================================
    int width = 3000, depth = 3000;
    int fplen = 16, slots = 8191;
    int ignore_bits = 10, reserved_bits = 2;
    double alpha = 0.8, exp_deg = 4779;

    Scube* scube = new ScubeKick(width, depth, fplen, 10, slots,
                                  exp_deg, ignore_bits, reserved_bits, alpha);

    uint32_t total_edges = 0;
    map<uint32_t, uint32_t> true_out_degree;
    set<pair<uint32_t,uint32_t>> real_edges;

    for (int node = 1; node <= TOTAL_NODES; node++) {
        int deg = degrees[node - 1];
        set<int> targets;
        for (int e = 0; e < deg; e++) {
            int dst = (rng() % TOTAL_NODES) + 1;
            if (dst == node) continue;
            if (targets.count(dst)) continue;
            targets.insert(dst);
            scube->insert(to_string(node), to_string(dst), 1);
            real_edges.insert({(uint32_t)node, (uint32_t)dst});
            total_edges++;
        }
        true_out_degree[node] = targets.size();
    }

    // Compute degree distribution stats
    double deg_avg = 0, deg_max = 0, deg_min = 1e9;
    double deg_median = 0;
    vector<int> sorted_degs;
    for (int i = 0; i < TOTAL_NODES; i++) {
        int d = true_out_degree[i + 1];
        sorted_degs.push_back(d);
        deg_avg += d;
        if (d > deg_max) deg_max = d;
        if (d < deg_min) deg_min = d;
    }
    deg_avg /= TOTAL_NODES;
    sort(sorted_degs.begin(), sorted_degs.end());
    deg_median = sorted_degs[TOTAL_NODES / 2];
    double deg_p90 = sorted_degs[(int)(TOTAL_NODES * 0.90)];
    double deg_p99 = sorted_degs[(int)(TOTAL_NODES * 0.99)];

    O << "================================================================" << endl;
    O << " SCUBE PRIVACY LEAKAGE DEMO (Zipf Distribution)" << endl;
    O << "================================================================" << endl;
    O << endl;
    O << "Graph setup:" << endl;
    O << "  Nodes: " << TOTAL_NODES << endl;
    O << "  Degree distribution: Zipf (gamma=" << ZIPF_GAMMA << ")" << endl;
    O << "  Degree range: [" << MIN_DEGREE << ", " << MAX_DEGREE << "]" << endl;
    O << "  Total edges inserted: " << total_edges << endl;
    O << "  Matrix size: " << width << " x " << depth << endl;
    O << endl;
    O << "Degree statistics:" << endl;
    O << "  Min: " << (int)deg_min << ", Median: " << (int)deg_median
      << ", Mean: " << deg_avg << ", P90: " << (int)deg_p90
      << ", P99: " << (int)deg_p99 << ", Max: " << (int)deg_max << endl;
    O << "  Hub threshold (top-" << TOP_K_HUBS << "): degree >= " << hub_threshold << endl;
    O << endl;

    O << "True top-20 nodes by degree:" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << " Rank | Node ID | True Degree " << endl;
    O << "-------------------------------------------------------------------" << endl;
    for (int i = 0; i < 20; i++) {
        O << setw(5) << (i + 1) << " | "
          << setw(7) << deg_rank[i].second << " | "
          << setw(11) << true_out_degree[deg_rank[i].second] << endl;
    }
    O << "-------------------------------------------------------------------" << endl;
    O << endl;

    // ================================================================
    //  ATTACK 1: HUB EXTRACTION via nodeWeightQuery
    // ================================================================
    O << "================================================================" << endl;
    O << " ATTACK 1: Hub Extraction via nodeWeightQuery" << endl;
    O << "================================================================" << endl;
    O << endl;
    O << "Method: Query nodeWeightQuery(v, 0) for all " << TOTAL_NODES
      << " nodes, sort by returned weight. Top-K = suspected hubs." << endl;
    O << endl;

    vector<NodeResult> §;
    for (int node = 1; node <= TOTAL_NODES; node++) {
        double total_lat = 0;
        int w = 0;
        for (int r = 0; r < TIMING_REPEAT; r++) {
            timeval t1, t2;
            gettimeofday(&t1, NULL);
            w = scube->nodeWeightQuery(to_string(node), 0);
            gettimeofday(&t2, NULL);
            total_lat += (t2.tv_sec - t1.tv_sec) * 1e6 + (t2.tv_usec - t1.tv_usec);
        }
        NodeResult nr;
        nr.id = node;
        nr.true_degree = true_out_degree[node];
        nr.queried_weight = w;
        nr.latency_us = total_lat / TIMING_REPEAT;
        node_results.push_back(nr);
    }

    sort(node_results.begin(), node_results.end(),
         [](const NodeResult& a, const NodeResult& b) {
             return a.queried_weight > b.queried_weight;
         });

    O << "Top-20 nodes ranked by queried weight (attacker's view):" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << " Rank | Node ID | Queried Wt | True Degree | Avg Latency | True Hub?" << endl;
    O << "-------------------------------------------------------------------" << endl;
    for (int i = 0; i < 20 && i < (int)node_results.size(); i++) {
        bool is_hub = true_hub_ids.count(node_results[i].id);
        O << setw(5) << (i + 1) << " | "
          << setw(7) << node_results[i].id << " | "
          << setw(10) << node_results[i].queried_weight << " | "
          << setw(11) << node_results[i].true_degree << " | "
          << setw(8) << node_results[i].latency_us << " us | "
          << (is_hub ? "*** HUB ***" : "") << endl;
    }
    O << "-------------------------------------------------------------------" << endl;
    O << endl;

    // Precision@K and Recall@K
    O << "Attack success (Precision@K — fraction of attacker's top-K that are true hubs):" << endl;
    int K_values[] = {10, 20, 50, 100};
    for (int K : K_values) {
        int hits = 0;
        for (int i = 0; i < K && i < (int)node_results.size(); i++) {
            if (true_hub_ids.count(node_results[i].id)) hits++;
        }
        double prec = (double)hits / min(K, TOP_K_HUBS);
        O << "  Precision@" << setw(3) << K << " = " << hits << "/"
          << min(K, TOP_K_HUBS) << " = " << prec * 100 << "%" << endl;
    }
    O << endl;

    // Rank correlation: Spearman-like — for true top-50, what's their avg rank in attacker's list?
    O << "Rank analysis of true top-" << TOP_K_HUBS << " hubs in attacker's ranking:" << endl;
    vector<int> hub_ranks;
    for (int i = 0; i < (int)node_results.size(); i++) {
        if (true_hub_ids.count(node_results[i].id))
            hub_ranks.push_back(i + 1);
    }
    sort(hub_ranks.begin(), hub_ranks.end());
    O << "  Best rank:  " << hub_ranks.front() << endl;
    O << "  Worst rank: " << hub_ranks.back() << endl;
    O << "  Avg rank:   " << avg(vector<double>(hub_ranks.begin(), hub_ranks.end())) << endl;
    O << endl;

    // Queried weight vs true degree accuracy
    O << "Query accuracy for hubs vs non-hubs (|queried - true| / true):" << endl;
    vector<double> hub_errs, nonhub_errs;
    for (auto& nr : node_results) {
        double err = (nr.true_degree > 0) ?
            fabs((double)nr.queried_weight - nr.true_degree) / nr.true_degree : 0;
        if (true_hub_ids.count(nr.id)) hub_errs.push_back(err);
        else nonhub_errs.push_back(err);
    }
    O << "  Hub nodes    (n=" << hub_errs.size() << "): avg relative error = "
      << avg(hub_errs) * 100 << "%" << endl;
    O << "  Non-hub nodes (n=" << nonhub_errs.size() << "): avg relative error = "
      << avg(nonhub_errs) * 100 << "%" << endl;
    O << "  (Lower error for hubs = skew-aware optimization helps hubs more = easier to extract)" << endl;
    O << endl;

    // ================================================================
    //  ATTACK 2: SENSITIVE EDGE PROBING via edgeWeightQuery
    // ================================================================
    O << "================================================================" << endl;
    O << " ATTACK 2: Sensitive Edge Probing via edgeWeightQuery" << endl;
    O << "================================================================" << endl;
    O << endl;
    O << "Method: Attacker has a suspect list of (src, dst) pairs." << endl;
    O << "Query edgeWeightQuery(src, dst): if result > 0, the edge exists." << endl;
    O << "Test set: 100 true edges + 100 non-existent edges (randomly sampled)." << endl;
    O << endl;

    vector<EdgeProbe> probes;

    // Sample 100 random real edges (from various degree nodes, not just hubs)
    vector<pair<uint32_t,uint32_t>> all_edges(real_edges.begin(), real_edges.end());
    shuffle(all_edges.begin(), all_edges.end(), rng);
    for (int i = 0; i < 100 && i < (int)all_edges.size(); i++) {
        EdgeProbe ep;
        ep.src = all_edges[i].first;
        ep.dst = all_edges[i].second;
        ep.truly_exists = true;
        probes.push_back(ep);
    }

    // Sample 100 random non-existent edges
    int fake_found = 0;
    while (fake_found < 100) {
        uint32_t s = (rng() % TOTAL_NODES) + 1;
        uint32_t d = (rng() % TOTAL_NODES) + 1;
        if (s == d) continue;
        if (real_edges.count({s, d})) continue;
        EdgeProbe ep;
        ep.src = s; ep.dst = d;
        ep.truly_exists = false;
        probes.push_back(ep);
        fake_found++;
    }

    shuffle(probes.begin(), probes.end(), rng);

    int TP = 0, FP = 0, TN = 0, FN = 0;
    for (auto& ep : probes) {
        timeval t1, t2;
        gettimeofday(&t1, NULL);
        ep.queried_weight = scube->edgeWeightQuery(to_string(ep.src), to_string(ep.dst));
        gettimeofday(&t2, NULL);
        ep.latency_us = (t2.tv_sec - t1.tv_sec) * 1e6 + (t2.tv_usec - t1.tv_usec);

        bool predicted_exists = (ep.queried_weight > 0);
        if (ep.truly_exists && predicted_exists)   TP++;
        if (ep.truly_exists && !predicted_exists)  FN++;
        if (!ep.truly_exists && predicted_exists)   FP++;
        if (!ep.truly_exists && !predicted_exists)  TN++;
    }

    O << "Probe results (200 total: 100 real + 100 fake edges):" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << "              | Predicted Exists | Predicted Absent |" << endl;
    O << "  Actually Yes |  TP = " << setw(4) << TP << "        |  FN = " << setw(4) << FN << "        |" << endl;
    O << "  Actually No  |  FP = " << setw(4) << FP << "        |  TN = " << setw(4) << TN << "        |" << endl;
    O << "-------------------------------------------------------------------" << endl;

    double precision_e = (TP + FP > 0) ? (double)TP / (TP + FP) : 0;
    double recall_e    = (TP + FN > 0) ? (double)TP / (TP + FN) : 0;
    double fpr         = (FP + TN > 0) ? (double)FP / (FP + TN) : 0;
    O << "  Precision (of positive predictions): " << precision_e * 100 << "%" << endl;
    O << "  Recall (of actual edges found):      " << recall_e * 100 << "%" << endl;
    O << "  False Positive Rate:                 " << fpr * 100 << "%" << endl;
    O << endl;

    O << "Sample probes (first 15):" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << "  Src -> Dst  | Exists? | Src Deg | Dst Deg | Query Wt | Verdict" << endl;
    O << "-------------------------------------------------------------------" << endl;
    for (int i = 0; i < 15 && i < (int)probes.size(); i++) {
        auto& ep = probes[i];
        O << "  " << setw(4) << ep.src << " -> " << setw(4) << ep.dst
          << " | " << (ep.truly_exists ? "  YES  " : "  NO   ")
          << " | " << setw(7) << true_out_degree[ep.src]
          << " | " << setw(7) << true_out_degree[ep.dst]
          << " | " << setw(8) << ep.queried_weight
          << " | " << (ep.queried_weight > 0 ? "EXISTS" : "ABSENT") << endl;
    }
    O << "-------------------------------------------------------------------" << endl;
    O << endl;

    // ================================================================
    //  ATTACK 3: TIMING SIDE-CHANNEL via query latency
    // ================================================================
    O << "================================================================" << endl;
    O << " ATTACK 3: Timing Side-Channel — Degree Class from Latency" << endl;
    O << "================================================================" << endl;
    O << endl;
    O << "Method: Even if returned values are noised, query LATENCY" << endl;
    O << "reveals degree class. Scube scans addr_num rows per query;" << endl;
    O << "more rows = higher latency = higher degree." << endl;
    O << endl;

    vector<double> hub_latencies, nonhub_latencies;
    for (auto& nr : node_results) {
        if (true_hub_ids.count(nr.id))
            hub_latencies.push_back(nr.latency_us);
        else
            nonhub_latencies.push_back(nr.latency_us);
    }

    double hub_avg    = avg(hub_latencies);
    double hub_std    = stdev(hub_latencies);
    double nonhub_avg = avg(nonhub_latencies);
    double nonhub_std = stdev(nonhub_latencies);

    O << "Latency statistics (averaged over " << TIMING_REPEAT << " repeats per node):" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << "  Hub nodes     (n=" << setw(4) << hub_latencies.size()
      << "): avg = " << setw(8) << hub_avg
      << " us, stdev = " << setw(8) << hub_std << " us" << endl;
    O << "  Non-hub nodes (n=" << setw(4) << nonhub_latencies.size()
      << "): avg = " << setw(8) << nonhub_avg
      << " us, stdev = " << setw(8) << nonhub_std << " us" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << "  Latency ratio (hub / non-hub): " << hub_avg / nonhub_avg << "x" << endl;
    O << endl;

    // Timing-based classification
    double threshold = (hub_avg + nonhub_avg) / 2.0;
    int timing_TP = 0, timing_FP = 0, timing_TN = 0, timing_FN = 0;
    for (auto& nr : node_results) {
        bool is_hub = true_hub_ids.count(nr.id);
        bool predicted_hub = (nr.latency_us > threshold);
        if (is_hub && predicted_hub)    timing_TP++;
        if (is_hub && !predicted_hub)   timing_FN++;
        if (!is_hub && predicted_hub)   timing_FP++;
        if (!is_hub && !predicted_hub)  timing_TN++;
    }

    O << "Timing-based hub classification (threshold = " << threshold << " us):" << endl;
    O << "-------------------------------------------------------------------" << endl;
    O << "              | Predicted Hub | Predicted Normal |" << endl;
    O << "  Actually Hub |  TP = " << setw(4) << timing_TP
      << "     |  FN = " << setw(4) << timing_FN << "          |" << endl;
    O << "  Actually Norm|  FP = " << setw(4) << timing_FP
      << "     |  TN = " << setw(4) << timing_TN << "          |" << endl;
    O << "-------------------------------------------------------------------" << endl;
    double timing_acc = (double)(timing_TP + timing_TN) / TOTAL_NODES;
    double timing_prec = (timing_TP + timing_FP > 0) ? (double)timing_TP / (timing_TP + timing_FP) : 0;
    double timing_recall = (timing_TP + timing_FN > 0) ? (double)timing_TP / (timing_TP + timing_FN) : 0;
    O << "  Accuracy:  " << timing_acc * 100 << "%" << endl;
    O << "  Precision: " << timing_prec * 100 << "%" << endl;
    O << "  Recall:    " << timing_recall * 100 << "%" << endl;
    O << endl;

    // Degree-latency correlation (Pearson)
    vector<double> all_degs_d, all_lats;
    for (auto& nr : node_results) {
        all_degs_d.push_back((double)nr.true_degree);
        all_lats.push_back(nr.latency_us);
    }
    double mean_d = avg(all_degs_d), mean_l = avg(all_lats);
    double cov = 0, var_d = 0, var_l = 0;
    for (size_t i = 0; i < all_degs_d.size(); i++) {
        double dd = all_degs_d[i] - mean_d;
        double dl = all_lats[i] - mean_l;
        cov += dd * dl;
        var_d += dd * dd;
        var_l += dl * dl;
    }
    double pearson = (var_d > 0 && var_l > 0) ? cov / sqrt(var_d * var_l) : 0;
    O << "Degree-latency Pearson correlation: r = " << pearson << endl;
    O << "(Strong positive correlation confirms timing side-channel)" << endl;
    O << endl;

    // ================================================================
    //  COMBINED ANALYSIS
    // ================================================================
    O << "================================================================" << endl;
    O << " ANALYSIS: Why Skew-Awareness Amplifies Privacy Leakage" << endl;
    O << "================================================================" << endl;
    O << endl;
    O << "Even with a natural Zipf degree distribution (not a contrived" << endl;
    O << "binary split), Scube's skew-aware design amplifies leakage:" << endl;
    O << endl;
    O << "1. HIGHER ACCURACY for high-degree nodes" << endl;
    O << "   → nodeWeightQuery returns near-exact degree for hubs" << endl;
    O << "   → Attacker simply sorts by queried weight to find top-K" << endl;
    O << endl;
    O << "2. LOWER FALSE POSITIVE RATE for edge queries" << endl;
    O << "   → edgeWeightQuery with fingerprint matching is highly reliable" << endl;
    O << "   → Attacker can confirm/deny any suspected relationship" << endl;
    O << endl;
    O << "3. DEGREE-CORRELATED QUERY LATENCY" << endl;
    O << "   → High-degree nodes scan more rows (higher addr_num)" << endl;
    O << "   → Even without seeing the returned value, timing leaks degree class" << endl;
    O << endl;
    O << "THE CORE TENSION:" << endl;
    O << "  Better skew-aware service = Higher accuracy for important nodes" << endl;
    O << "                            = Easier extraction of important nodes" << endl;
    O << "                            = Greater privacy risk" << endl;
    O << endl;

    O << "================================================================" << endl;
    O << " END OF DEMO" << endl;
    O << "================================================================" << endl;

    out.close();
    cout << "Results written to privacy_demo_output.txt" << endl;

    delete scube;
    return 0;
}
