# Q1 baseline · 六组附录 E 真实数据验收

> 这是第一阶段的 **deterministic baseline**，用于验证 parser / validator / evaluator / scheduler 的完整闭环，不代表问题 1 的最终优化结果。

## 验收环境

- 代码 commit：`a6d58ba10e3c1941f5a8e2b589a83f5e1f2c3d23`
- GitHub Actions run：`34562094364`
- Python：3.12.14
- oracle / regression tests：7 passed
- 六组完整数据批处理步骤：success
- 批处理步骤耗时：约 1.13 s（04:24:55.115 → 04:24:56.241，包含解析、调度、独立复算和结果写出）
- Actions artifact：`cpmcm-2025-a-q1-baseline`，artifact id `10184674663`（完整六组 schedule CSV + summary；artifact 仅作运行留档，仓库内结果可由代码重新生成）

## Baseline 结果

Q1 指标按当前已核实口径统计 L1 + UB 的峰值驻留量；每个输出顺序均重新经过独立 topology / buffer-lifetime / L0 validator 与 evaluator。

| Case | Nodes | Edges | Valid | Peak residency | Peak position |
|---|---:|---:|:---:|---:|---:|
| Matmul_Case0 | 4160 | 7104 | ✓ | 9216 | 691 |
| Matmul_Case1 | 30976 | 55040 | ✓ | 34816 | 2539 |
| FlashAttention_Case0 | 1716 | 2712 | ✓ | 26728 | 434 |
| FlashAttention_Case1 | 6952 | 11184 | ✓ | 106992 | 1590 |
| Conv_Case0 | 2580 | 3869 | ✓ | 80170 | 884 |
| Conv_Case1 | 36086 | 85653 | ✓ | 310408 | 7478 |

节点数和边数已由 batch runner 与附录 E 六组登记值逐 case 核对，全部一致。

## 一个重要发现

不能把 `NodeId` 从小到大直接当作原始合法调度序列：六组数据的 `sorted(NodeId)` 全部未通过独立拓扑/生命周期验收，因此表中的 `original_order_valid=False`，也就没有伪造所谓“相对原始编号顺序降低了多少”的改善率。

后续比较必须选择**合法 baseline**，或者与小规模精确最优解/公开可复核方案比较。

## 下一阶段

保持 parser / validator / evaluator 不变，继续实现 Q1 强化算法：

1. unlock-FREE potential；
2. critical-path / downstream pressure；
3. bounded lookahead / beam search；
4. 小规模 exact solver（枚举/DP/Branch-and-Bound），用 optimality gap 验证启发式质量。

只有上述方案重新跑过同一套六组验收后，才进入论文中的“优化算法结果”表。
