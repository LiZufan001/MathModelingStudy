# Q2 optimized：正式提升与六组严格验收

## 结论

2026-09-11 将 pure-footprint `footprint_m8` 调度策略从实验候选提升为正式 Q2 生成路径。正式入口为：

```bash
python problems/CPMCM/2025/A/src/batch_q2.py \
  --strategy optimized \
  --data-dir problems/CPMCM/2025/A/data/csv \
  --out-dir /tmp/q2-optimized-results
```

该入口执行：Q2-aware schedule → strict allocator → 第二次独立 validator replay → exact promotion metric regression gate → 官方 schedule / memory / spill 文件输出。

## 正式配置

配置定义在 `src/q2_optimized.py`，固定为：

```text
hot_window=1
direct_affinity_weight=0
release_weight=0
probe_per_buffer=64
footprint_weight=1
footprint_min_buffers=8
```

这不是按算子名称做 Matmul 特判。scheduler 从 L0 缓冲区的局部使用关系构建到 counted L1/UB buffer 的两跳 footprint；跨 task anchor 只允许由 L0C 建立。L0A/L0B 可以在已有 L0C task anchor 下作为从属资源一起路由，但不得在没有 L0C anchor 时凭自己的历史 footprint 独立跨任务 chaining。

这一约束来自实际反例：允许输入侧 L0A/L0B 独立建立或追逐 task footprint 时，Conv 会出现 `task_anchor=None` 但某个 L0B 已被独立打开并阻塞后续任务的死锁。收紧为 L0C 主导后，Conv0/1 恢复严格可行，同时 Matmul 的复用收益完整保留。

## 六组 Appendix-E 验收

| case | q1_peak | baseline spills | optimized spills | baseline traffic | optimized traffic | traffic delta | footprint decisions | strict valid |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Matmul_Case0 | 9216 | 272 | **225** | 34816 | **28800** | **-6016 (-17.279%)** | 119 | True |
| Matmul_Case1 | 34816 | 3600 | **3361** | 460800 | **430208** | **-30592 (-6.639%)** | 495 | True |
| FlashAttention_Case0 | 26728 | 301 | 301 | 55188 | 55188 | 0 | 0 | True |
| FlashAttention_Case1 | 106992 | 1782 | 1782 | 242552 | 242552 | 0 | 0 | True |
| Conv_Case0 | 80170 | 493 | 493 | 178212 | 178212 | 0 | 0 | True |
| Conv_Case1 | 310408 | 9550 | 9550 | 724630 | 724630 | 0 | 0 | True |

Matmul 聚合：

- traffic：`495616 → 459008`，减少 `36608`，即 `-7.386%`；
- spills：`3872 → 3586`，减少 `286`，即 `-7.386%`；
- q1_peak 聚合保持 `44032`；
- footprint 决策共 `614` 次。

FA / Conv 四组没有 footprint 决策，因此正式 pure-footprint 策略退化为 baseline 行为，不引入 direct-hot heuristic 的随机收益或回退。

## 验收证据

Promotion commit：

`07a57ee7d576e566680f1621208e8cd2d6265e7a`

GitHub Actions：

- workflow：`Test CPMCM 2025 A Q2`
- run：`34576610370`
- conclusion：`success`
- Python：3.12
- tests：`40 passed`
- `Run Q2 baseline on all six official Appendix-E cases`：success
- `Compare Matmul strict allocator with exact uniform-page Belady oracle`：success；baseline Matmul0/1 spill 与 traffic gap 均为 0
- `Benchmark Q2-aware reuse scheduler and replay winner on all six cases`：success；winner=`footprint_m8`，`six_case_all_valid=true`
- `Generate promoted Q2 optimized solutions with exact regression gates`：success
- `Hold Q2 allocator fixed and ablate schedule order`：success
- `Upload Q2 acceptance evidence`：success

Artifact：

- name：`cpmcm-2025-a-q2-validation`
- artifact id：`10189941551`
- files：52
- ZIP size：766635 bytes
- SHA-256：`e0e0744b07e1df56483b0531f29976ece91098d89dc750e1fbf5c7e3e24bdc0c`
- run URL：`https://github.com/LiZufan001/MathModelingStudy/actions/runs/34576610370`

Artifact 中同时保留 baseline、optimized、Belady oracle、reuse parameter sweep、spill profiles、外部 archived solution 审计以及 order ablation 结果。

## 关于外部 archived 参赛附件

当前 workflow 也继续下载并审计公开仓库 `Zysishuiyears/2025Huaweicup_Cachenpuscheduling` 中归档的 A25100550012 Problem2 附件。其 schedule 使用 `spill_L1_0` / `spill_UB_0` 等非题面要求的纯数字节点 token，且 Conv_Case0 还存在部分 reload 地址超出 L1 容量的问题，因此在我们的严格题面解释下 `strict_valid=False`。

这些归档结果只作为思路/指标研究材料，**不作为正确性 oracle 或正式验收基准**。

## 后续修改的硬门禁

后续 scheduler / allocator 优化只有同时满足以下条件，才允许替换当前正式策略：

1. `pytest` 全部通过；
2. 六组官方 Appendix-E 输出均能生成；
3. 独立 `q2_validator` strict replay 全部通过；
4. Matmul uniform-page 场景继续与 exact oracle 对账；
5. 六组 `q1_peak / spill_count / extra_traffic` 不得无意回退；
6. 若声称新的性能提升，必须保存相同口径的 baseline 对照、真实 CI 日志和可复现 artifact。

机器无关的核心验收数字另存于 `q2_optimized_summary.csv` / `q2_optimized_summary.json`；运行时间不作为固定回归指标。
