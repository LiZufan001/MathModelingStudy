# Q3 zero-traffic：保守安全时序下的第一阶段正式结果

## 结论

问题 3 的第一阶段采用“先不增加任何额外 DDR 搬运量，再压缩流水”的保守路线。基于已经提升的 Q2 解，依次尝试：

1. 固定调度与 SPILL victim，仅对各 residency epoch 重新分配物理地址；
2. 固定原始依赖、SPILL 分区依赖和物理驻留先后，仅按 critical bottom level 重排独立节点；
3. 每个变换只有在独立 `q3_evaluator` 的 `residency_safe` 口径下严格减少 cycles 才接受；
4. 再迭代一轮，若无继续下降则停止。

六组 Appendix-E 数据表明，两轮搜索在第一轮之后已经收敛：Matmul0/1 接受“地址重着色 + critical reschedule”，Conv1 只接受 critical reschedule；FlashAttention0/1 与 Conv0 的候选均因没有改善而被拒绝。

在 **SPILL 数、SPILL victim 序列与总额外数据搬运量均不增加** 的前提下，六组合计的保守安全总周期从 `8,218,257` 降至 `7,950,145`，减少 `268,112` cycles，即 `3.262395%`。

## 六组结果

| case | Q2 traffic | spill count | Q2 safe cycles | Q3 zero-traffic cycles | cycles delta | improvement |
|---|---:|---:|---:|---:|---:|---:|
| Matmul_Case0 | 28,800 | 225 | 195,024 | **160,005** | -35,019 | **17.956252%** |
| Matmul_Case1 | 430,208 | 3,361 | 1,771,302 | **1,669,574** | -101,728 | **5.743120%** |
| FlashAttention_Case0 | 55,188 | 301 | 212,425 | 212,425 | 0 | 0 |
| FlashAttention_Case1 | 242,552 | 1,782 | 1,026,762 | 1,026,762 | 0 | 0 |
| Conv_Case0 | 178,212 | 493 | 798,190 | 798,190 | 0 | 0 |
| Conv_Case1 | 724,630 | 9,550 | 4,214,554 | **4,083,189** | -131,365 | **3.116937%** |

## 收敛轨迹

- Matmul_Case0：`195024 -> 163760 (next_fit) -> 160005 (critical)`；第二轮地址与 critical 都不再改善。
- Matmul_Case1：`1771302 -> 1685733 (next_fit) -> 1669574 (critical)`；第二轮不再改善。
- FlashAttention_Case0：地址保持原样；critical 候选 `213573` 比 `212425` 更差，拒绝。
- FlashAttention_Case1：地址保持原样；critical 候选 `1029487` 比 `1026762` 更差，拒绝。
- Conv_Case0：地址保持原样；critical 候选 `808899` 比 `798190` 更差，拒绝。
- Conv_Case1：地址保持原样；critical `4214554 -> 4083189`，第二轮不再改善。

因此当前 two-stage transformation portfolio 已到达固定点；继续无条件增加迭代轮数不会产生收益。

## 关于 `official_literal` 与 `residency_safe`

附录 C 的字面规则只要求按 ALLOC 顺序为地址复用添加 `FREE(a) -> ALLOC(b)`。严格照此计算时，当前 Q2 六组解在并行 wall-clock 重放中都会出现 SPILL 后 residency epoch 的物理地址同时占用现象。

因此本阶段优化以 `residency_safe` 作为更严格的内部硬门禁：除题面字面复用依赖外，还保证 SPILL 后重新驻留的 epoch 不会在实际时间轴上与同一物理区间冲突。这个口径是**保守安全扩展**，不是把它伪称为题面官方公式。后续 Pareto 实验会同时保留：

- official-literal cycles：用于对照题面附录 C 的字面计算；
- residency-safe cycles：用于内部物理安全审计和保守优化选择。

## 验收证据

Zero-traffic acceptance snapshot：

- branch：`agent/q3-pipeline-20260911`
- commit：`69b20415fe1cbaaa8e571ffcb254e4c17ef932a2`
- GitHub Actions run：`34580011246`
- conclusion：`success`
- tests：`51 passed`
- 六组 baseline：success
- 地址 policy benchmark：success
- critical pipeline benchmark：success
- 两轮 monotone zero-traffic benchmark：success
- artifact id：`10191430523`
- artifact SHA-256：`c74a66434bdf927aec3a4c2684d65bdffb0651fccd670dc23a23d0a9c9023cc6`

该 snapshot 之后的 Pareto 开发提交进一步增加了“SPILL victim BufId 顺序不得改变”的显式断言；新代码需以其对应 CI 全绿为准，不反向覆盖本文件记录的已验收 snapshot。

## 下一阶段

当前 `epsilon=0` 已有可信基线。下一阶段使用通用 critical-window scheduler 对 promoted Q2 原始顺序做受控偏离：`window=0` 必须精确复现 Q2，窗口增大才允许更长关键路径的 ready 节点在局部范围提前。每个候选重新经过 strict Q2 allocator，再在 `epsilon = 0/1%/3%/5%` 的额外 traffic 上限内选取最小 safe cycles，构成可复现的 Traffic-Cycles Pareto 前沿。
