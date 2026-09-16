# Q1 promoted：四策略确定性 portfolio

## 正式结论

问题 1 的正式结果不再停留在 `q1_baseline`。当前 promoted 方案对每个 Appendix-E case 分别运行四个**确定性且独立 evaluator 可重放**的策略：

1. `q1_baseline`：FREE 优先、neutral 次之、计数内存 ALLOC 最后；
2. `q1_pressure`：加入 downstream/release pressure 启发；
3. `q1_frontier`：frontier/depth-first 风格贪心；
4. `q1_lookahead`：仅在正内存 ALLOC 分叉处触发有界前瞻。

对所有合法候选重新使用同一 Q1 evaluator 计算 `peak_residency`，按该官方目标选最小值。外部公开 schedule **不参与选择**，只作为独立横向参照。

## 六组正式结果

| case | baseline peak | promoted peak | promoted method | reduction | reduction % |
|---|---:|---:|---|---:|---:|
| Matmul_Case0 | 9,216 | **9,216** | q1_baseline | 0 | 0 |
| Matmul_Case1 | 34,816 | **34,816** | q1_baseline | 0 | 0 |
| FlashAttention_Case0 | 26,728 | **26,728** | q1_baseline | 0 | 0 |
| FlashAttention_Case1 | 106,992 | **106,992** | q1_baseline | 0 | 0 |
| Conv_Case0 | 80,170 | **80,170** | q1_baseline | 0 | 0 |
| Conv_Case1 | 310,408 | **310,344** | q1_lookahead | **64** | **0.020618%** |

因此五组 case 中 baseline 已经是当前 portfolio 最优；只有 Conv_Case1 的 bounded lookahead 严格改善 64 个 residency units。

## 为什么值得晋升这 64

Q1 的目标就是最小化峰值驻留量。Conv1 的 improvement 虽然只有约 `0.0206%`，但它满足：

- schedule 合法；
- 使用同一独立 evaluator 重算；
- 改善是严格的 `310,408 -> 310,344`；
- 方法是通用 bounded lookahead，而不是手工改一个 NodeId；
- 结果在完整六组 CI 的 policy comparison 中产生；
- fresh `main` run 再次复现同一数值，并且六份 promoted schedule 的 SHA-256 与先前独立 validation 完全一致。

所以论文和正式 Q1 结果应报告当前已验证的 best-known portfolio 点，而不是为了运行更快故意退回较差的 baseline。

## 独立公开参照

Q1 workflow 还下载了一套公开 Problem1 六组 schedule，并用本仓库 evaluator **独立重放**。六组全部 valid，且峰值分别为：

`9,216 / 34,816 / 26,728 / 106,992 / 80,170 / 310,408`

恰好与我们的 baseline 六组一致。这个外部结果只说明 baseline 有很强的横向参照价值，**不构成全局最优证明**，也不参与 promoted policy 的选择。

## 最新 main 验收 provenance

- source head：`8b1f610dd219cc8441f39e4ca7adacb08e14550c`
- workflow：`Test CPMCM 2025 A Q1`
- run：`35077306473`
- conclusion：success
- unit / oracle tests：76 passed
- 六组 baseline：success
- 六组四策略 comparison：success
- published-result verifier：success
- 公开 schedule strict replay：6/6 valid
- artifact：`10439355947`
- digest：`sha256:40b9d9834dae2660c88d56a0f18cea95b2a5640fad0905a19cfe27d7cd81c45e`

`q1_promoted_summary.json` 永久记录六份 promoted best schedule 的 SHA-256；fresh main run 与先前 integration validation 的六份 SHA-256 完全一致。

## 结论边界

当前 promoted Q1 只是四个确定性策略组成的 portfolio best-known 结果：

- 小规模 exact solver/oracle 用于验证算法语义与启发式质量；
- 六组 Appendix-E 大实例没有全局最优性证明；
- 后续如果出现严格更小且通过同一 evaluator/validator 的 schedule，可以再 promotion。
