# 2025 A题实现与验收

本目录面向 2025 年 A 题“通用神经网络处理器下的核内调度问题”。当前已经形成一条完整的三阶段正式链：

- **Q1**：四策略确定性 portfolio（baseline / pressure / frontier / bounded lookahead），六组 promoted 结果与 published-result verifier；
- **Q2**：严格连续地址分配 / SPILL 实现与六组 promoted 策略；
- **Q3**：双 evaluator、formal fixed-traffic optimizer、Traffic–Cycles refined Pareto，以及正式 Problem3 输出与 artifact-native acceptance。

所有正式结果都要求独立 validator/evaluator、Appendix-E 六组真实 replay 和 CI 回归证据，不能只凭单次实验数字晋升。

## Q1：promoted 拓扑调度 portfolio

核心实现：

- `src/model.py`：统一图/节点数据模型；
- `src/parser.py`：严格读取附录 E Nodes / Edges CSV；
- `src/validators.py`：独立检查拓扑序、buffer 生命周期和 L0 同类单驻留约束；
- `src/evaluator.py`：独立复算 Q1 的 L1+UB 峰值驻留量；
- `src/q1_scheduler.py`：deterministic Kahn baseline；
- `src/q1_advanced.py`：pressure-aware 调度；
- `src/q1_frontier.py`：frontier/depth-first 调度；
- `src/q1_lookahead.py`：bounded lookahead 调度；
- `src/compare_q1.py`：六组四策略统一比较并导出 best schedule；
- `src/verify_q1_promoted_results.py`：fresh comparison ↔ published promoted summary 门禁；
- `src/batch_q1.py`：六组 baseline 批处理入口；
- `tests/test_core.py` 等：小规模 oracle / 反例测试。

正式结果见 [`results/q1_promoted/README.md`](results/q1_promoted/README.md)，历史 baseline 证据保留在 [`results/q1_baseline/README.md`](results/q1_baseline/README.md)。

当前六组 promoted peak：

| case | baseline peak | promoted peak | method |
|---|---:|---:|---|
| Matmul_Case0 | 9,216 | **9,216** | q1_baseline |
| Matmul_Case1 | 34,816 | **34,816** | q1_baseline |
| FlashAttention_Case0 | 26,728 | **26,728** | q1_baseline |
| FlashAttention_Case1 | 106,992 | **106,992** | q1_baseline |
| Conv_Case0 | 80,170 | **80,170** | q1_baseline |
| Conv_Case1 | 310,408 | **310,344** | q1_lookahead |

Conv1 严格减少 64 residency units（`0.020618%`）。这是当前**四策略 portfolio 的 best-known promoted 点**，不是全局最优证明。

最新 main fresh acceptance：run `35077306473`。76 个 unit/oracle tests、六组 baseline、六组 policy comparison、published-result verifier 和外部六组 schedule strict replay 全部通过；artifact `10439355947`，digest `sha256:40b9d9834dae2660c88d56a0f18cea95b2a5640fad0905a19cfe27d7cd81c45e`。

## Q2：严格连续地址分配与 SPILL 优化

核心实现：

- `src/q2_allocator.py`：连续地址分配、SPILL victim 选择、官方 SPILL 对插入；
- `src/q2_validator.py`：独立严格 replay，检查地址区间、resident 状态、SPILL 顺序与额外搬运量；
- `src/q2_unit_cache_oracle.py`：Matmul 等大小 L1 page 的精确 Belady oracle；
- `src/q2_reuse_scheduler.py`：Q2-aware footprint 调度器；
- `src/q2_optimized.py` / `src/q2_promoted.py`：正式提升策略及六组 exact regression gate；
- `src/batch_q2.py`：`baseline` / `optimized` 双策略正式生成入口；
- `src/benchmark_q2_reuse_scheduler.py`：候选参数实验、Matmul 选择和六组 strict replay。

正式结果、算法边界、复现命令和 CI 证据见 [`results/q2_optimized/README.md`](results/q2_optimized/README.md)。

当前六组 extra traffic：

| case | spill count | extra traffic |
|---|---:|---:|
| Matmul_Case0 | 225 | **28,800** |
| Matmul_Case1 | 3,361 | **430,208** |
| FlashAttention_Case0 | 316 | **54,016** |
| FlashAttention_Case1 | 1,782 | **242,552** |
| Conv_Case0 | 522 | **177,904** |
| Conv_Case1 | 9,646 | **721,464** |

2026-09-11 promotion 验收中，Matmul 两组总额外搬运量由 `495,616` 降至 `459,008`，减少 `36,608`（`-7.386%`），SPILL 次数由 `3,872` 降至 `3,586`；FlashAttention / Conv 四组严格保持 baseline 指标不变。六组均通过 strict replay。

## Q3：正式 evaluator 与 fixed-traffic optimizer

核心实现：

- `src/q3_evaluator.py`：同时计算题面 `official_literal` 与物理安全 `residency_safe`；
- `src/q3_official_optimizer.py`：地址 portfolio、critical pipeline reschedule、critical-reuse recolor；
- `src/q3_spill_batch_optimizer.py`：fresh-rerank critical-SPILL batch 局部搜索；
- `src/q3_official_spill_optimizer.py`：formal core + spill-batch 稳定组合入口；
- `src/export_q3_formal_fixed_traffic.py`：输出正式 `Problem3/<case>_schedule|memory|spill.txt`；
- `experiments/q3_critical_spill_switch.py`：critical-SPILL single-switch bubble 邻域；
- `experiments/probe_q3_cycle_filtered_batch*.py`：Conv1 cycle-filtered checkpointed 饱和搜索；
- `experiments/accept_q3_conv1_cycle_filtered_artifact.py`：artifact-native 独立正式验收；
- `experiments/reconcile_q3_refined_frontier.py`：strict-valid-only Pareto reconciliation。

正式 fixed-traffic 结果见 [`results/q3_formal_fixed_traffic/README.md`](results/q3_formal_fixed_traffic/README.md)，论文直接引用的 Pareto 前沿见 [`results/q3_pareto/q3_refined_official_frontier.csv`](results/q3_pareto/q3_refined_official_frontier.csv)。

Q3 主目标按 `official_literal_cycles` 排序，`residency_safe` 只作为硬可行性门禁。正式主链不增加 Q2 traffic，也不改变 SPILL identity/order/count。

| case | official cycles | safe cycles | extra traffic |
|---|---:|---:|---:|
| Matmul_Case0 | **133,682** | 160,005 | 28,800 |
| Matmul_Case1 | **1,531,946** | 1,669,574 | 430,208 |
| FlashAttention_Case0 | **187,945** | 204,875 | 54,016 |
| FlashAttention_Case1 | **962,022** | 1,026,634 | 242,552 |
| Conv_Case0 | **595,302** | 789,619 | 177,904 |
| Conv_Case1 | **3,749,777** | 4,114,811 | 721,464 |

Conv0 在 formal batch 后由 single-switch 邻域继续降至 `595,302`；Conv1 cycle-filtered post-pass 降至 `3,749,777`。二者的“no-improvement”只表示对应**命名局部邻域饱和**，不是全局最优证明。

Conv1 formal acceptance run `35064897835` 独立重建 promoted Q2、重放 strict/official/safe，并再次得到 no-improvement；exact SPILL records、spill count `9,646` 与 extra traffic `721,464` 均不变。

## 论文工程

论文资产工作区：[`paper/`](paper/)

- `paper/ASSET_PLAN.md`：正文/附录图表规划；
- `paper/manuscript/OUTLINE.md`：章节施工图；
- `paper/manuscript/CLAIM_LEDGER.md`：关键结论 ↔ 正式证据与措辞边界；
- `paper/figures/`、`tables/`、`diagrams/`：可复现论文资产脚本。

论文的图表与数据表只读取正式 `results/`，不重新求解模型、不手抄指标。

## 本地运行

从仓库根目录：

```bash
python -m pip install pytest
python -m pytest problems/CPMCM/2025/A/tests -q
```

Q1 baseline 六组：

```bash
python problems/CPMCM/2025/A/src/batch_q1.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q1-baseline-results
```

Q1 四策略 promoted comparison：

```bash
python problems/CPMCM/2025/A/src/compare_q1.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q1-promoted-comparison
```

Q2 正式 optimized 生成：

```bash
python problems/CPMCM/2025/A/src/batch_q2.py \
  --strategy optimized \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q2-optimized-results
```

单 case 正式 Q3 Problem3 导出：

```bash
python problems/CPMCM/2025/A/src/export_q3_formal_fixed_traffic.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --case FlashAttention_Case0 \
  --out-dir /tmp/q3-formal \
  --spill-max-rounds 12 \
  --require-spill-saturated
```

论文资产：

```bash
make -C problems/CPMCM/2025/A/paper assets
```

任何后续候选都必须先通过独立 validator/evaluator、六组官方数据真实 replay 和对应 published-result regression gate，才能替换当前正式结果。
