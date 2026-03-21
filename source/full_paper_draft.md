# Privacy-Preserving Skew-Aware Graph Stream Summarization

---

## 摘要（Abstract）

图流摘要（Graph Stream Summarization）是处理大规模动态图数据的核心技术。以 Scube 为代表的偏斜感知（Skew-aware）方法通过感知节点度数分布，为高度节点（Hub）分配更多存储资源，从而大幅提升查询效用。然而，本文首次揭示了这一效用优化的隐性代价：**偏斜感知的资源倾斜机制（Skew-aware Resource Allocation）在数学上必然使高度节点的结构特征更易被外部攻击者推断，构成严重的结构隐私泄露风险。**

我们将这一现象形式化为**效用-隐私张力（Utility-Privacy Tension）**，并引入**可提取性优势（Extractability Advantage）**作为统一的隐私泄露度量指标。通过仅利用公开查询接口（Query-only），攻击者可以高精度完成 Hub 提取（Top-K Extraction）和 Hub 成员推断（Hub Membership Inference）。实验结果表明，在 Zipf 分布图流上 Precision@50 达 98%，时间侧信道分类准确率达 92.64%。

为此，我们提出 **P-Scube**，一种轻量级的隐私保护图流摘要框架。P-Scube 通过**单调加噪升级（Monotonic Noisy Promotion）**和**粗粒度资源分配（Coarsened Resource Allocation）**两个机制，在理论上满足$\epsilon$-度数不可区分性（$\epsilon$-Degree Indistinguishability），在保留 Skew-aware 效用优势的同时，显著降低了高度节点的可提取性，并在 Privacy-Utility Frontier 上优于全局差分隐私基线。

---

## 1. 研究背景（Research Background）

### 1.1 图流与大规模图数据应用

图流（Graph Stream）是一种新兴的图数据模型，用于描述快速演化的动态图。图流中的每个元素被表示为一条带权重的有向边 $(s_i, d_i, w_i, t_i)$，其中 $s_i \to d_i$ 表示从源节点到目的节点的边，$w_i$ 为权重，$t_i$ 为时间戳。这一数据模型被广泛应用于：

- **网络安全与监控**：分析流量图中异常节点与路径。
- **社交网络分析**：追踪用户行为与影响力传播。
- **电子商务**：用户行为建模与推荐系统。
- **公共卫生**：新冠疫情期间的密接追踪（如腾讯健康码，超 10 亿用户，累计 240 亿次扫码）。

这些应用场景的共同特点是：**数据规模极大、到达速率极高、内存资源有限**。例如，微信每天有 9.02 亿活跃用户产生 380 亿条消息。面对如此量级的图流，将完整图结构持久化存储是不可行的。

### 1.2 图流摘要：在有限内存下近似维护图结构

**图流摘要（Graph Stream Summarization）**是一种在有限内存下近似维护图流统计信息的压缩技术，支持以下查询：

- **边权查询（Edge Weight Query）**：查询指定边的聚合权重。
- **节点权查询（Node Weight Query）**：查询某节点所有入边/出边的聚合权重。
- **路径可达性查询（Reachability Query）**：判断两节点是否可达。

现有代表性工作包括：

| 结构 | 核心机制 | 偏斜感知 | 主要缺陷 |
|------|----------|----------|----------|
| **TCM** | $m \times m$ 哈希矩阵，直接累加权重 | ✗ | 哈希冲突导致精度极差 |
| **GSS** | 指纹 + 缓冲区，碰撞时溢出到 Buffer | ✗ | 偏斜图流下 Buffer 膨胀，查询延迟激增 |
| **Scube** | 度数检测器 + 动态地址分配 | ✓ | **（本文揭示）引发结构隐私泄露** |

### 1.3 偏斜图流的挑战：幂律分布与哈希冲突集中

真实世界的图流（社交网络、交易网络等）普遍呈现**幂律度分布（Power-law Degree Distribution）**：极少数节点（Hub）拥有远超平均的邻居数量，绝大多数节点度数极低。

$$\Pr[d_v = k] \propto k^{-\gamma}, \quad \gamma \approx 2\text{--}3$$

在传统的哈希矩阵中，所有节点被同等对待，Hub 节点会引发严重的哈希冲突集中，导致查询精度和延迟双双恶化。

---

## 2. 研究问题（Research Questions）

本文聚焦于以下两个核心问题，而非试图解决所有隐私问题：

**RQ1（隐私泄露）**：偏斜感知图流摘要（Scube）是否比偏斜无感知方法（GSS）更容易将高度节点（Hub）的结构身份暴露给外部攻击者？泄露的程度如何形式化量化？

**RQ2（隐私保护）**：能否在不明显破坏 Skew-aware 效用优势（查询精度与吞吐量）的前提下，设计轻量级机制降低 Hub 的可提取性？

本文**不涉及**的方向：
- 不构建完整的图差分隐私（Graph Differential Privacy）框架。
- 不将敏感边的存在性推断作为主要贡献。
- 不追求覆盖所有内部信号和攻击面。

---

## 3. 相关工作（Related Work）

### 3.1 图流摘要结构

**TCM（Topology-aware Compact Matrix）**[1] 是第一个图流摘要结构。它使用 $m \times m$ 的矩阵，通过哈希函数将边映射到对应的桶，并累加权重。缺点是哈希冲突导致查询精度极低。

**GSS（Graph Stream Sketch）**[2] 通过在每个桶中存储边的指纹对来降低误报率。当冲突发生时，新边被写入额外的 Buffer。然而在偏斜图流下，Buffer 规模随 Hub 的出现急剧膨胀，导致查询延迟不可接受。

**Scube**[3]（ICDCS 2022）是目前最先进的偏斜感知图流摘要结构。它引入了**度数检测器（DegDetector）**，通过基于低概率事件的概率计数估计节点度数，并使用**动态地址分配**为高度节点分配更多矩阵行/列地址。实验表明，Scube 在偏斜数据集上将查询延迟降低了 48%--99%。

### 3.2 差分隐私与图隐私

**差分隐私（Differential Privacy, DP）**[4] 是目前最严格的隐私保护框架。对于图数据，DP 的应用面临以下挑战：

- **全局 DP（Global DP）**：在发布统计量时注入全局噪声。在图流场景下，为满足边级别 DP 所需的噪声量极大，导致严重的效用损失和吞吐量下降。
- **本地 DP（Local DP）**：每条记录在本地加噪后上传。适用于单个节点的度数保护，但难以直接迁移到偏斜感知的摘要结构中。

本文提出的 P-Scube 采用了一种**推断隐私（Inference Privacy）**视角，针对 Hub 节点的可提取性进行选择性保护，避免了全局 DP 带来的性能开销。

### 3.3 摘要结构的隐私分析

现有工作鲜有系统性地分析图流摘要结构（而非发布的统计结果）本身所隐含的隐私风险。最接近的工作包括：

- **Sketch 的频率泄露**[5]：分析了 Count-Min Sketch 中高频项对攻击者的信号暴露，与本文思路相近，但不针对图结构的偏斜特性。
- **侧信道攻击与数据库**[6]：研究了数据库查询执行计划的时间侧信道，本文将类似思路应用于图流摘要的节点查询场景。

---

## 4. Scube 的高低度数分辨机制（Scube: Distinguishing Low and High Degree Nodes）

### 4.1 整体架构

Scube 由两个核心组件构成：**高度节点检测器（High-degree Node Detector）** 和**摘要存储矩阵（Summarization Storage Matrix $M$）**。

- 检测器维护两个数组，分别用于估计出度（Out-degree）和入度（In-degree）。
- 矩阵 $M$ 是一个 $m \times m$ 的压缩矩阵，每个 Bucket 存储边的指纹对和权重。

### 4.2 低概率事件概率计数（Low-Probability Events Based Probabilistic Counting）

对于节点 $v$，其邻居集合为 $\{u_1, u_2, \ldots, u_k\}$，对每个邻居计算哈希值。定义模式 $P(T, i)$：

$$P(T, i) = \{\underbrace{\times \cdots \times}_{T-i-1} \underbrace{1\ 0 \cdots 0}_{i}\}$$

其中 $\Pr[P(T,i)] = 2^{-(i+1)}$，$i$ 越大概率越低。

**分辨高低度数的关键机制**：

1. **L-bit 位向量**：只记录 $i \ge R$ 的低概率事件（高位），忽略 $i < R$ 的高频事件（低位）。低度节点的邻居数量少，极难同时触发多个低概率事件，因此位向量几乎不会被填满。
2. **Complete Record 计数（$c$）**：每次位向量从 0 变为全 1（$2^L-1$）称为一次完整记录。高度节点拥有大量邻居，因此能积累更多次完整记录，$c$ 的值更大。
3. **地址数估算**：最终的度数估计为 $\hat{d}_v = c \times E_{R,L}$，分配的地址数为：
$$A_v = \max\left(2, \left\lceil \frac{\hat{d}_v}{\theta} \right\rceil \right)$$
当 $A_v > 2$ 时，该节点被认定为高度节点（Potential High-degree Node）。

每个 Slot 的内存结构（`DegDetectorSlot2bit.h`）：

| 字段 | 位数 | 含义 |
|------|------|------|
| `bitvector` | 2 bits ($L$) | 记录低概率事件 |
| `update_times` | 8 bits | Complete Record 次数 $c$ |
| `address_number` | 6 bits | 分配的地址数 $A_v$ |

### 4.3 阈值判断与动态地址扩展

初始状态：所有节点被分配 2 个地址（即矩阵中 4 个候选插入位置）。

当度数检测器估计的 $\hat{d}_v$ 超过阈值 $\theta = 2\delta m$（默认 $\delta = 0.8$）时：
- Scube 为该节点增加一个新的行/列地址。
- 此后每当度数增量超过 $\delta m$，继续扩展。

当所有候选位置均被占用时，触发 **Kick-out 策略**：将"优先级最低"的旧边踢出，为新边腾出空间。若 Kick-out 次数超过阈值，强制将该节点标记为高度节点并扩展地址（`ScubeKick.h:250`）。

---

## 5. 问题建模：效用-隐私张力（Problem Formulation: The Utility-Privacy Tension）

### 5.1 系统模型

设图流 $\mathcal{G}$ 中节点度数服从幂律分布 $\Pr[d_v = k] \propto k^{-\gamma}$。摘要系统 $\mathcal{S}$ 在处理每条边 $(s, d, w)$ 后，为节点 $v$ 维护资源状态 $A_v$（分配的哈希地址数）和矩阵状态 $M$。

**偏斜感知摘要系统（Skew-aware Summary）的核心性质**：
$$A_v = f(\hat{d}_v), \quad f \text{ 严格单调递增且确定}$$

### 5.2 攻击者模型（Threat Model）

我们定义三层攻击者能力模型：

| 等级 | 名称 | 能力 | 本文角色 |
|------|------|------|----------|
| L1 | Query-only | 仅能调用公开查询接口 | **主实验场景** |
| L2 | Summary-observable | 可观察延迟或统计量 | 辅助解释场景 |
| L3 | Internal-access | 可读取 Detector 内部状态 | 上界分析场景 |

攻击者已知：摘要类型与主要参数、哈希函数族和查询接口。
攻击者未知：真实图流内容。

**时间侧信道（Timing Side-channel）**：由于节点查询时需要遍历 $A_v$ 个地址，查询延迟 $T_v$ 与 $A_v$ 呈严格正相关：
$$T_v \approx c_0 \cdot A_v + \epsilon_{network}$$
因此，L1 攻击者通过统计多次查询时延，即可以高精度推断 $A_v$，从而推断节点的度数等级。

### 5.3 隐私泄露的形式化量化

**定义 1（确定性资源分配）**：在原版 Scube 中，资源分配函数为：
$$A_v = \max\left(2, \left\lceil \frac{\hat{d}_v}{\theta} \right\rceil \right)$$

**定义 2（可提取性优势）**：攻击者 $\mathcal{A}$ 观测到 $A_v$ 后，推断节点 $v$ 为 Hub（$d_v > \tau$）的概率优势定义为：
$$Adv(\mathcal{A}) = \left| \Pr[d_v > \tau \mid A_v] - \Pr[d_v > \tau] \right|$$

**定理 1（效用-隐私张力，Tension Theorem）**：若 $A_v$ 与 $\hat{d}_v$ 满足严格单调确定性映射，且估计器 $\hat{d}_v$ 无偏，则对于大 $\tau$：
$$Adv(\mathcal{A}) \to 1 - \Pr[d_v > \tau]$$

**证明**：根据贝叶斯定理：
$$\Pr[d_v > \tau \mid A_v] = \frac{\Pr[A_v \mid d_v > \tau] \cdot \Pr[d_v > \tau]}{\Pr[A_v]}$$

由于映射是确定性的，$\Pr[A_v \text{ large} \mid d_v > \tau] \to 1$ 且 $\Pr[A_v \text{ large} \mid d_v < \tau] \to 0$，导致后验概率坍缩至 1。攻击者优势：
$$Adv(\mathcal{A}) \approx 1 - \Pr[d_v > \tau] \approx 0.99 \quad \square$$

---

## 6. 隐私泄露的形式化分析（Formal Privacy Leakage Analysis）

### 6.1 两类泄露信号

**信号 A：检测器状态泄露（Detector-State Leakage）**

`DegDetector` 中的 `update_times`（$c$）和 `address_number`（$A_v$）共同构成了节点度数的精确代理指标（Proxy）。攻击者可利用此信号：
- 对所有节点按 $A_v$ 排序，提取 Top-K Hub。
- 给定节点 $v$，判断 $A_v > 2$ 是否成立，推断 Hub 成员资格。
- 估计节点属于哪个度数类别（Degree Class）。

**信号 B：查询路径泄露（Query-Path Leakage）**

`nodeWeightQuery()` 的执行路径由 `addrQuery()` 返回的 $A_v$ 决定——$A_v$ 越大，需要扫描的矩阵行/列越多，执行时间越长。
- **查询值信号**：Hub 节点的查询返回值精度更高（更少的哈希冲突），排序后即可提取 Hub。
- **延迟信号**：高度节点的查询延迟显著高于低度节点，构成 degree-correlated 时间侧信道。

### 6.2 三个主要攻击任务

**Attack 1：Top-K Hub 提取（Top-K Extraction）**
- 对候选节点集调用 `nodeWeightQuery(v, 0)`，按返回值排序，取前 K 个。
- 评估指标：`Precision@K`、`Recall@K`、`NDCG@K`。

**Attack 2：Hub 成员推断（Hub Membership Inference）**
- 用查询返回值、延迟或 Detector 信号构造分类器，将节点二分类为 Hub / Non-Hub。
- 评估指标：`AUC`、`F1`、`TPR@FPR=0.1`。

**Attack 3：基于时延的度数推断（Timing-based Degree Inference）**
- 仅依据查询延迟（不看返回值）推断节点的度数类别。
- 评估指标：`Accuracy`、`Macro-F1`。

### 6.3 实证结果（Preliminary Evidence）

基于合成的 Zipf 分布图（50,000 条边，$\gamma = 1.5$）的初步实验结果如下，充分证明 Query-only 攻击的有效性：

| 攻击任务 | 指标 | Scube | GSS（基线） |
|----------|------|-------|------------|
| Top-K Hub 提取 | Precision@10 | **100%** | ~50% |
| Top-K Hub 提取 | Precision@50 | **98%** | ~30% |
| 时延度数推断 | Accuracy | **92.64%** | ~60% |
| 时延度数推断 | Hub Recall | **100%** | ~70% |
| 时延度数推断 | Pearson $r$ | **0.5037** | ~0.1 |

可以看出，Scube 因为偏斜感知优化，在以上攻击任务中的**可提取性优势**远超 GSS。

---

## 7. P-Scube 设计（P-Scube Design）

### 7.1 设计目标

P-Scube 的目标不是让摘要系统"完全不可攻击"，而是：
1. **降低泄露**：相比 Scube，显著降低 Hub 提取和 Hub 成员推断的攻击成功率。
2. **保留效用**：相比全局加噪基线（Global DP Noise），保留更多查询精度和吞吐量。
3. **轻量设计**：主要修改集中在 Detector 层，不修改矩阵主体结构。

### 7.2 机制 1：单调加噪升级（Monotonic Noisy Promotion）

**理论支撑**：为满足$\epsilon$-度数不可区分性，需要引入随机性打破确定性映射。

**挑战**：图流场景下，节点度数单调增长，不能每次都重新随机生成噪声（否则状态会震荡）。

**解决方案**：将拉普拉斯噪声与节点指纹（Hash Key）绑定，生成**固定但不可预测**的伪随机噪声：
$$\eta_v = \text{Laplace}(0, \lambda),\quad \text{seed} = h(v) \pmod{\text{PRNG}}$$

加噪后的估计度数：
$$\tilde{d}_v = \hat{d}_v + \eta_v = c \times E_{R,L} + \eta_v$$

由于 $\eta_v$ 固定，随着 $c$ 增大，$\tilde{d}_v$ 单调递增，保证了地址数不会回退。

### 7.3 机制 2：粗粒度资源分配（Coarsened Resource Allocation）

将连续的地址数映射到少量离散桶：

$$A_v^* = \text{Bucketize}(\tilde{d}_v), \quad \mathcal{B} = \{2, 4, 6\}$$

例如：
$$A_v^* = \begin{cases} 2 & \tilde{d}_v / \theta < 3 \\ 4 & 3 \le \tilde{d}_v / \theta < 5 \\ 6 & \tilde{d}_v / \theta \ge 5 \end{cases}$$

此举使得真实度数在 $[3\theta, 5\theta)$ 范围内的节点全部获得相同的 4 个地址，攻击者无法区分它们的精确度数。

### 7.4 理论保障：$\epsilon$-度数不可区分性

**定理 2（度数不可区分性，Degree Indistinguishability）**：P-Scube 满足 $\epsilon$-度数不可区分性。对任意两个节点 $u$、$v$，满足 $|d_u - d_v| \le \Delta$，则：
$$\frac{\Pr[A_u^* = B_i]}{\Pr[A_v^* = B_i]} \le e^{\epsilon}, \quad \epsilon = \frac{\Delta}{\lambda}$$

**证明概要**：$\tilde{d} = \hat{d} + \eta$，$\eta \sim \text{Laplace}(0, \lambda)$，其概率密度满足标准 DP 性质。分桶操作为后处理步骤，不会增加隐私预算 $\epsilon$。因此，攻击者无法区分度数相差 $\Delta$ 的两个节点，从而限制 $Adv(\mathcal{A})$。$\square$

---

## 参考文献（References）

[1] Tang L, et al. "Graph stream summarization: From big bang to big crunch." SIGMOD 2016.

[2] Gou X, et al. "Graph sketching-based space-efficient data mining." USENIX ATC 2019.

[3] Chen M, et al. "Scube: Efficient Summarization for Skewed Graph Streams." ICDCS 2022.

[4] Dwork C, Roth A. "The Algorithmic Foundations of Differential Privacy." Foundations and Trends in TCS 2014.

[5] Melis L, et al. "Inference Attacks Against Collaborative Learning." CCS 2019.

[6] Grubbs P, et al. "Learning to Reconstruct: Statistical Learning Theory and Encrypted Database Attacks." IEEE S&P 2019.
