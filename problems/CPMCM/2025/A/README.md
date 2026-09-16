# 2025 A题实现与验收

本目录面向 2025 年 A 题“通用神经网络处理器下的核内调度问题”。当前已经形成：

- Q1 可复现调度基线；
- Q2 严格连续地址分配 / SPILL 实现与六组 promoted 策略；
- Q3 双 evaluator、formal fixed-traffic optimizer、Traffic–Cycles refined Pareto，以及正式 Problem3 输出链。

所有正式结果都要求独立 validator/evaluator、Appendix-E 六组真实 replay 和 CI 回归证据，不能只凭单次实验数字晋升。

## 已实现

### Q1 基础设施

- `src/model.py`：统一图/节点数据模型；
- `src/parser.py`：严格读取附录 E 的 Nodes / Edges CSV；
- `src/validators.py`：独立检查拓扑序、buffer 生命周期和 L0 同类单驻留约束；
- `src/evaluator.py`：独立复算 Q1 的 L1+UB 峰值驻留量；
- `src/q1_scheduler.py`：deterministic Kahn baseline；
- `src/batch_q1.py`：一次跑完附录 E 六组数据，并核对题面节点/边数量；
- `tests/test_core.py`：小规模 oracle / 反例测试。

Q1 baseline 的完整结果与历史证据见 [`results/q1_baseline/README.md`](results/q1_baseline/README.md)。

### Q2 严格实现与优化

- `src/q2_allocator.py`：连续地址分配、SPILL victim 选择、官方 SPILL 对插入；
- `src/q2_validator.py`：独立严格 replay，检查地址区间、resident 状态、SPILL 顺序与额外搬运量；
- `src/q2_unit_cache_oracle.py`：Matmul 等大小 L1 page 的精确 Belady oracle；
- `src/q2_reuse_scheduler.py`：Q2-aware footprint 调度器；
- `src/q2_optimized.py` / `src/q2_promoted.py`：正式提升策略及六组 exact regression gate；
- `src/batch_q2.py`：`baseline` / `optimized` 双策略正式生成入口，输出官方 schedule / memory / spill 文件；
- `src/benchmark_q2_reuse_scheduler.py`：候选参数实验、Matmul 选择和六组 strict replay；
- `tests/test_q2.py`、`tests/test_q2_reuse_scheduler.py`：allocator / validator / L0 task routing 回归测试。

正式 Q2 optimized 结果、算法边界、复现命令和 CI 证据见 [`results/q2_optimized/README.md`](results/q2_optimized/README.md)。

### Q3 正式 evaluator 与 fixed-traffic optimizer

- `src/q3_evaluator.py`：同时计算题面 `official_literal` 与物理安全 `residency_safe`；
- `src/q3_official_optimizer.py`：地址 portfolio、critical pipeline reschedule、critical-reuse recolor；
- `src/q3_spill_batch_optimizer.py`：fresh-rerank critical-SPILL batch 局部搜索；
- `src/q3_official_spill_optimizer.py`：formal core + spill-batch 的稳定组合入口；
- `src/export_q3_formal_fixed_traffic.py`：输出正式 `Problem3/<case>_schedule|memory|spill.txt`；
- `experiments/q3_critical_spill_switch.py`：critical-SPILL single-switch bubble 邻域；
- `experiments/probe_q3_single_switch_saturation.py`：checkpointed single-switch 饱和搜索；
- `experiments/probe_q3_cycle_filtered_batch.py` / `probe_q3_cycle_filtered_batch_saturation.py`：Conv1 cycle-filtered critical-SPILL checkpointed 饱和搜索；
- `experiments/accept_q3_conv1_cycle_filtered_artifact.py`：从搜索 artifact 独立重建 promoted Q2、双 evaluator 重放并复查 no-improvement 的正式验收入口；
- `experiments/reconcile_q3_refined_frontier.py`：把 fixed-traffic evidence 与已有 trade-off 重新做 strict-valid-only Pareto reconciliation；
- `tests/test_q3_*`：evaluator、official optimizer、spill-batch、formal wrapper 与 frontier reconciliation 回归。

Q3 正式 fixed-traffic 结果见 [`results/q3_formal_fixed_traffic/README.md`](results/q3_formal_fixed_traffic/README.md)，论文直接引用的当前 Pareto 前沿见 [`results/q3_pareto/q3_refined_official_frontier.csv`](results/q3_pareto/q3_refined_official_frontier.csv)。

## 当前正式 Q2 策略

正式策略为 `footprint_m8` 等价配置：

- `hot_window=1`
- `direct_affinity_weight=0`
- `release_weight=0`
- `probe_per_buffer=64`
- `footprint_weight=1`
- `footprint_min_buffers=8`

核心约束：只有 L0C 可以建立跨 task anchor；L0A/L0B 只能在已有 L0C anchor 时接受 footprint 引导，不能在无 L0C anchor 时独立跨任务 chaining。这样在 Matmul 上利用两跳 L0→L1 footprint 复用，同时避免在 Conv 上产生输入侧 L0 死锁。

2026-09-11 的 promotion 验收中，Matmul 两组总额外搬运量由 `495616` 降至 `459008`，减少 `36608`（`-7.386%`），SPILL 次数由 `3872` 降至 `3586`；FlashAttention / Conv 四组严格保持 baseline 指标不变。六组均通过 strict replay。

## 当前正式 Q3 fixed-traffic 结果

Q3 主目标按 `official_literal_cycles` 排序，`residency_safe` 只作为硬可行性门禁。formal Q3 不增加 Q2 traffic，也不改变 SPILL 身份/顺序和次数。

| case | official cycles | safe cycles | extra traffic |
|---|---:|---:|---:|
| Matmul_Case0 | **133,682** | 160,005 | 28,800 |
| Matmul_Case1 | **1,531,946** | 1,669,574 | 430,208 |
| FlashAttention_Case0 | **187,945** | 204,875 | 54,016 |
| FlashAttention_Case1 | **962,022** | 1,026,634 | 242,552 |
| Conv_Case0 | **595,302** | 789,619 | 177,904 |
| Conv_Case1 | **3,749,777** | 4,114,811 | 721,464 |

六组基础 critical-SPILL batch 均已到首个 no-improvement round；这是对应算子族的**局部饱和**，不是全局最优证明。Conv0 在 batch 终点 `597,969` 后再用 checkpointed single-switch bubble 降到 `595,302`，随后该 `max_switches=4` 邻域 no-op，并由 formal acceptance 完整重放通过。

Conv1 先由 deterministic saturated shortcut 与完整 promoted-Q2 -> deep formal chain 独立复现旧正式点 `3,767,326`。在这个已验证起点上，新的 cycle-filtered critical-SPILL post-pass 继续 checkpoint 搜索到 **`3,749,777`**，相对旧正式点再减少 `17,549` cycles；最后一轮首次 no-improvement。formal acceptance run `35064897835` 又从搜索 artifact 独立重建 promoted Q2、重放 strict/official/safe，并再次得到 no-improvement，确认 exact SPILL records、spill count `9,646` 与 extra traffic `721,464` 均不变。

当前 refined Pareto 仍为 8 行。FA0 原 `w=1 = 55,036 / 191,230` 已被 fixed-traffic 点 `54,016 / 187,945` 严格支配并删除；FA1 的 `1>1`、`2>1` 两个 higher-traffic trade-off 仍保留。发布数据由 `verify_q3_published_results.py` 同时检查 CSV / JSON / refined frontier / reconcile report 以及 improvement arithmetic。

## 本地运行

从仓库根目录执行：

```bash
python -m pip install pytest
python -m pytest problems/CPMCM/2025/A/tests -q
```

Q1 baseline：

```bash
python problems/CPMCM/2025/A/src/batch_q1.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir problems/CPMCM/2025/A/results/q1_baseline
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

Conv1 的当前正式 post-pass 使用 checkpointed cycle-filtered workflow，并以 `accept_q3_conv1_cycle_filtered_artifact.py` 做 artifact-native 独立验收。永久 provenance 与三份 accepted Problem3 的 SHA-256 见 `results/q3_formal_fixed_traffic/q3_conv1_cycle_filtered_acceptance.json`。

任何后续候选都必须先通过独立 validator/evaluator、六组官方数据真实 replay、固定 Q2 traffic/SPILL 不变量和指标回归门禁，才能替换当前正式结果。
