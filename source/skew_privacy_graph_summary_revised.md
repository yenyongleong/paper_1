# Skew-Aware Privacy-Preserving Graph Stream Summarization

## 1. Research Background
Graph streams are widely used in critical applications such as financial transaction networks, social media interactions, and communication systems. Sketch-based summarization techniques (e.g., TCM, GSS) have been proposed to enable efficient queries under strict memory constraints. 

Real-world graph streams inherently exhibit **structural skew** (e.g., power-law degree distributions), where a small number of "hub" (heavy) nodes are associated with a massive number of edges. Traditional skew-unaware sketches suffer from severe hash collisions and degraded utility for these hubs. To address this, recent **skew-aware summarization methods (e.g., Scube)** introduce degree detectors and dynamic resource allocation, explicitly granting more storage and higher precision to high-degree nodes.

## 2. Research Problem
While skew-aware optimizations successfully improve query utility, they introduce a critical but previously overlooked vulnerability: **the "special treatment" of hub nodes acts as a side-channel, inadvertently amplifying their privacy leakage.**

Specifically, we aim to answer the following questions:
1. **The Utility-Privacy Tension:** Does the resource-skewed allocation in methods like Scube make high-degree nodes significantly more vulnerable to structural inference attacks (e.g., hub extraction) compared to skew-unaware methods?
2. **Attack Surface:** Can adversaries exploit query responses (e.g., precision variations) and timing side-channels (e.g., query latency caused by dynamic addressing) to accurately infer the identity and degree class of sensitive hub nodes?
3. **The Mitigation:** Can we decouple "resource allocation" from "deterministic node identity" to suppress this extractability without sacrificing the efficiency and utility benefits of skew-aware designs?

## 3. Research Challenges
- **Quantifying the Privacy Cost of Skew-Awareness:** Defining formal metrics to measure the "extractability advantage" an adversary gains specifically from the skew-aware mechanisms, separating it from the baseline leakage of standard sketches.
- **Concealing Deterministic States:** Skew-aware methods rely on deterministic degree thresholds to trigger resource expansion. Obfuscating these states without destroying the statistical accuracy of the summary is mathematically challenging.
- **Balancing Privacy, Utility, and Throughput:** Applying heavy cryptographic privacy frameworks (e.g., global Differential Privacy) to high-speed graph streams causes unacceptable throughput drops and utility loss. The defense must be extremely lightweight.

## 4. Research Objectives
- **Analyze and Expose:** Formally analyze how skew-aware mechanisms (degree detection, dynamic addressing, kick-out strategies) translate into observable privacy leakages (state leakage and query-path leakage).
- **Design Selective Protection:** Propose a lightweight, privacy-aware decoupling framework that selectively obfuscates the mapping between a node's true degree and its allocated resources.
- **Maintain Skew-Aware Advantages:** Ensure the proposed defense maintains high insertion throughput and acceptable query accuracy, proving that privacy and skew-awareness can coexist.

## 5. Proposed Idea: P-Scube (Privacy-Aware Scube)
Instead of applying global noise, we propose a **Selective Privacy Framework** that specifically targets the vulnerabilities introduced by skew-aware optimizations. The core mechanisms include:

1. **Noisy Degree Promotion:** Replace the deterministic degree threshold for resource expansion with a probabilistic, noise-injected promotion mechanism (e.g., adding Laplace noise to the promotion score). This makes the ranking of near-threshold nodes unstable, thwarting Top-K hub extraction.
2. **Coarsened Resource Allocation:** Instead of allowing fine-grained, continuous address expansion (which acts as a precise degree fingerprint), we bucketize the allocated resources into a few discrete levels (e.g., low, mid, high). This forces nodes of varying degrees to share the same observable resource class, increasing indistinguishability.
3. **Oblivious Query & Kick-out (Optional/Advanced):** Introduce dummy memory accesses (padding scans) during queries to flatten the timing side-channel, ensuring that querying a low-degree node takes the same time as querying a high-degree node within the same bucket.

## 6. Baselines for Evaluation
- **Target/Vulnerable Baseline:** `Scube` (State-of-the-art skew-aware summary; expected to show high utility but high leakage).
- **Skew-Unaware Baseline:** `GSS` (Fingerprint-based sketch; expected to show lower hub leakage but poor utility/latency under skew).
- **Naive Privacy Baseline:** `Scube + Global DP Noise` (Expected to show good privacy but unacceptable utility degradation).
- **Proposed Method:** `P-Scube` (Expected to match GSS's privacy level while retaining Scube's utility advantages).

## 7. Contributions
1. **Novel Vulnerability Discovery:** We are the first to reveal the inherent tension between "skew-aware utility optimization" and "structural privacy" in graph stream summarization, demonstrating that resource allocation acts as a strong privacy side-channel.
2. **Comprehensive Attack Framework:** We introduce a systematic extractability analysis framework, including Top-K Hub Extraction, Hub Membership Inference, and Timing-based Degree Inference, proving that query-only access is sufficient to compromise hub privacy.
3. **Lightweight Defense System:** We propose a novel, privacy-aware skew management framework that uses noisy promotion and coarsened allocation to significantly reduce hub extractability with minimal overhead, establishing a new Pareto frontier for privacy and utility in graph streams.
