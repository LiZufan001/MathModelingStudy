# 2025 A题实现与验收

本目录面向 2025 年 A 题“通用神经网络处理器下的核内调度问题”，当前已经形成 Q1 可复现基线、Q2 严格缓存分配/换入换出实现，以及经过六组附录 E 官方数据真实验收的 Q2 调度优化路径。

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
- `src/q2_optimized.py`：正式提升的 pure-footprint 配置及六组 exact regression gate；
- `src/batch_q2.py`：`baseline` / `optimized` 双策略正式生成入口，输出官方 schedule / memory / spill 文件；
- `src/benchmark_q2_reuse_scheduler.py`：候选参数实验、Matmul 选择和六组 strict replay；
- `tests/test_q2.py`、`tests/test_q2_reuse_scheduler.py`：allocator / validator / L0 task routing 回归测试。

正式 Q2 optimized 结果、算法边界、复现命令和 CI 证据见 [`results/q2_optimized/README.md`](results/q2_optimized/README.md)。

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

Q2 baseline 对照：

```bash
python problems/CPMCM/2025/A/src/batch_q2.py \
  --strategy baseline \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q2-baseline-results
```

Q2 正式 optimized 生成：

```bash
python problems/CPMCM/2025/A/src/batch_q2.py \
  --strategy optimized \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q2-optimized-results
```

`optimized` 模式不是“只要 validator 通过就接受”：程序会在独立 strict replay 之后继续逐 case 核对 promotion 时锁定的 `q1_peak / spill_count / extra_traffic`，任何静默性能回退都会直接失败。

任何后续候选顺序都必须先通过独立 validator/evaluator、六组官方数据真实 replay 和指标回归门禁，才能替换当前正式策略。
