# 2025 A题实现：第一阶段（Q1 基础设施 + baseline）

这一阶段先把“结果是否真的合法、指标是否真的算对”做成稳定底座，再迭代高级启发式。

## 已实现

- `src/model.py`：统一图/节点数据模型；
- `src/parser.py`：严格读取附录 E 的 Nodes / Edges CSV；
- `src/validators.py`：独立检查拓扑序、buffer 生命周期和 Q1 的 L0 同类单驻留约束；
- `src/evaluator.py`：独立复算 Q1 的 L1+UB 峰值驻留量；
- `src/q1_scheduler.py`：deterministic Kahn baseline（FREE → neutral → counted-memory ALLOC），并做 L0 可行性过滤；
- `src/experiment.py`：单 case 运行入口，同时复算原始 NodeId 顺序作为对照；
- `src/batch_q1.py`：一次跑完附录 E 六组数据，并核对题面节点/边数量；
- `tests/test_core.py`：小规模 oracle / 反例测试。

> 这里的 `q1_baseline` 只是可复现基线，不是最终 Q1 算法。下一阶段将在 evaluator 不变的前提下加入 unlock-FREE、critical path、lookahead / beam search，并通过小图精确解报告 optimality gap。

## 已验收结果

六组附录 E 完整数据已经在 GitHub Runner 上通过真实运行验收；聚合结果、运行证据和当前限制见 [`results/q1_baseline/README.md`](results/q1_baseline/README.md)。

## 本地运行

从仓库根目录执行：

```bash
python -m pip install pytest
python -m pytest problems/CPMCM/2025/A/tests -q

python problems/CPMCM/2025/A/src/experiment.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --case Matmul_Case0 \
  --method q1_baseline \
  --out-dir problems/CPMCM/2025/A/results/q1_baseline

python problems/CPMCM/2025/A/src/batch_q1.py \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir problems/CPMCM/2025/A/results/q1_baseline
```

任何候选顺序都必须先通过独立 validator/evaluator，才能进入结果表和后续论文分析。
