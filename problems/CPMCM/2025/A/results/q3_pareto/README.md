# Q3 Traffic–Cycles Pareto：双口径正式结果

## 结论

本目录记录 2025 A 题问题 3 在 promoted Q2 解基础上的受控 Traffic–Cycles 权衡实验。实验不使用任意加权和，而采用 epsilon-constraint：以 Q2 额外数据搬运量为基线，在 `epsilon = 0% / 1% / 3% / 5%` 的流量上限内寻找更小的执行周期。

候选由统一的 critical-window scheduler 生成：`window=0` 精确复现 promoted Q2 原始顺序；窗口增大时，只允许当前 ready 节点在有限的原始位置范围内按 critical bottom level 提前，同时冻结 L0A/L0B/L0C 的单驻留先后。实验窗口为 `0 / 8 / 32 / 128 / 512`。

每个候选依次经过：

1. Q1 生命周期、拓扑和 L0 合法性检查；
2. strict Q2 连续地址分配与 SPILL 重放；
3. `residency_safe` 时序审计；
4. 若额外 traffic 不超过 Q2 基线的 5%，执行两轮 zero-traffic address/pipeline 单调优化；
5. 同时计算 `residency_safe` 和 Appendix-C `official_literal` 两个 cycles 口径；
6. 分别按两个口径构造 epsilon frontier。

这里必须区分两个目标：

- `official_literal`：按题面 Appendix C 字面依赖计算，是论文和比赛结果的主目标视图；
- `residency_safe`：额外加入 SPILL 后 residency epoch 的物理区间安全约束，是内部硬审计和保守实现口径。

任何进入 official frontier 的候选都必须先通过 `residency_safe` 硬门禁；但最终 official frontier 的选优依据是 `official_literal_cycles`，不会把我们自加的保守依赖冒充为官方目标。

## Official-literal frontier

| case | epsilon | window | traffic | official cycles | official improvement vs Q2 |
|---|---:|---:|---:|---:|---:|
| Matmul_Case0 | 0/1/3/5% | 0 | 28,800 | **133,682** | **1.036408%** |
| Matmul_Case1 | 0/1/3/5% | 0 | 430,208 | **1,531,946** | **0.174115%** |
| FlashAttention_Case0 | 0/1/3% | 0 | 55,188 | 197,374 | 0 |
| FlashAttention_Case0 | 5% | **8** | 57,088 | **194,235** | **1.590382%** |
| FlashAttention_Case1 | 0/1/3% | 0 | 242,552 | 962,746 | 0 |
| FlashAttention_Case1 | 5% | **8** | 250,584 | **942,667** | **2.085597%** |
| Conv_Case0 | 0/1/3/5% | 0 | 178,212 | 631,915 | 0 |
| Conv_Case1 | 0/1/3/5% | 0 | 724,630 | **3,650,628** | **3.899306%** |

最明确的真实 trade-off 出现在 FlashAttention：

- FA0：traffic `55,188 -> 57,088`，增加 `1,900`（`+3.442777%`），official cycles `197,374 -> 194,235`（`-1.590382%`）；safe cycles 同时 `212,425 -> 200,966`（`-5.394374%`）。
- FA1：traffic `242,552 -> 250,584`，增加 `8,032`（`+3.311455%`），official cycles `962,746 -> 942,667`（`-2.085597%`）；safe cycles同时 `1,026,762 -> 970,684`（`-5.461636%`）。

因此在当前候选族中，约 5% 的 traffic 预算确实能为 FlashAttention 换到两个时序口径一致的收益，而 1%/3% 尚不足以容纳该候选。

## Safe frontier 与 official frontier 的分叉

Matmul 是最重要的反例，证明两个口径不能混用：

- Matmul0 在 5% safe frontier 中选择 `window=8`：safe cycles `160,005 -> 158,495`，但 official cycles 从 `133,682` 变为 `136,214`；相对原 Q2 official baseline `135,082` 反而退化 `0.838010%`。因此 official frontier 正确地仍选择 `window=0`。
- Matmul1 在 1%/3%/5% safe frontier 中选择 `window=8`：safe cycles `1,669,574 -> 1,650,497`；但 official cycles `1,531,946 -> 1,537,478`，相对原 Q2 official baseline `1,534,618` 退化 `0.186366%`。official frontier 仍保持 `window=0`。

所以后续算法必须采用“safe 作为硬门禁、official 作为接受目标”的双层策略，而不能继续只按 safe cycles 选优。

## Conv 的负结果同样有价值

Conv0 的非零窗口很快使 traffic 接近或超过 Q2 的两倍，并且部分候选在 safe wall-clock replay 中出现 residency overlap，因此当前 critical-window 方向没有形成有效的 5% 内权衡。

Conv1 更值得注意：`window=32` 的 Q2 traffic 仅从 `724,630` 增至 `725,986`，只增加 `1,356`（约 `0.18713%`），但该候选在 `residency_safe` 时序审计中出现物理区间重叠，因此被硬门禁拒绝。说明 Conv 下一阶段更需要地址分配与流水时序联合优化，而不是单纯扩大调度窗口。

## 文件

- `q3_pareto_candidates.csv`：五个窗口 × 六组数据的候选摘要，包括被 5% 上限拒绝或被 safe overlap 拒绝的原因。
- `q3_safe_frontier.csv`：按 `residency_safe_cycles` 选出的 epsilon frontier。
- `q3_official_frontier.csv`：按 Appendix-C `official_literal_cycles` 选出的 epsilon frontier；论文主结果优先使用此表。

完整机器输出（两个 frontier 的 JSON、candidate JSON、trace、兼容 alias）保存在对应 GitHub Actions artifact 中，不在仓库重复保存。

## 验收证据

- branch：`agent/q3-pipeline-20260911`
- run head commit：`a3bf7ec00e9419166edb18182f81980a596e8be7`
- 双前沿实现 commit：`9b1b617f05527f2e368fdd098a2b467e64f386fa`
- GitHub Actions run：`34583105800`
- conclusion：`success`
- focused tests：`14 passed`
- `q3_safe_frontier.csv`：生成且非空
- `q3_official_frontier.csv`：生成且非空
- `q3_epsilon_frontier.csv`：兼容 alias，生成且非空
- artifact id：`10192731193`
- artifact ZIP size：`12,512 B`
- artifact SHA-256：`1d2e296b5c6e661d4c1ccc0b5aee1f56eac006e50b0f6c043d81bb356161317f`

## 下一阶段

下一步实现 official-oriented zero-traffic optimizer：保持 Q2 traffic、SPILL victim 序列不变，所有候选必须通过 `residency_safe`，但地址重着色和 critical pipeline 变换只在 `official_literal_cycles` 严格下降时接受。这样可以直接针对 Matmul 当前暴露出的目标错位继续优化，同时保留物理安全审计。