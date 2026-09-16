# CPMCM 2025 A 论文 Claim Ledger

> 用途：把论文中的关键结论绑定到唯一证据和允许措辞。正式写作时先查本表，再落句子。
> 原则：没有证据条目的“更优 / 最优 / 不变 / 饱和 / 精确 / 验证”不进入正文。

## 证据等级

- **PUBLISHED**：已进入 `results/` 正式发布文件，并有 CI/验收门禁；可用于正文定量结论。
- **ACCEPTED**：有独立 validator/evaluator 或 formal acceptance；可用于方法可信度和边界说明。
- **EXTERNAL-REPLAY**：第三方/历史公开结果经本仓库 evaluator 重放；只能作横向参照，不参与本队正式解选择。
- **EXPERIMENTAL**：实验脚本或探针结果，未 promotion；默认不写成正式结论。

---

## Q1

### Q1-C1｜问题 1 的正式目标

**允许结论**  
在满足 DAG 拓扑依赖和 L0 硬约束的合法调度序列中，最小化 L1+UB 逻辑驻留量的峰值。

**证据**
- `study/README.md`：题面规则与 `Vstay / Vpeak` 定义；
- `src/evaluator.py`：独立 Q1 evaluator；
- `src/validators.py`：拓扑 / buffer 生命周期 / L0 约束。

**禁止扩写**
- 不把 L0 容量计入 Q1 的 L1+UB objective；
- 不把 schedule-position liveness 写成 wall-clock residency。

### Q1-C2｜四策略 promoted portfolio

**允许结论**  
当前正式 Q1 结果取 `q1_baseline / q1_pressure / q1_frontier / q1_lookahead` 四个确定性合法策略中经同一 evaluator 重算后的最小 `peak_residency`。

**证据等级**：PUBLISHED + ACCEPTED  
**证据**
- `results/q1_promoted/q1_promoted_summary.csv`
- `results/q1_promoted/q1_promoted_summary.json`
- `src/compare_q1.py`
- `src/verify_q1_promoted_results.py`
- `.github/workflows/test-cpmcm-2025-a.yml`

**边界措辞**  
“当前四策略 portfolio 的 promoted / best-known 结果”。

**禁止措辞**
- “全局最优拓扑序”；
- “理论最优”。

### Q1-C3｜Conv1 的严格小幅改善

**允许结论**  
Conv_Case1 的 bounded lookahead 将峰值驻留量从 `310,408` 降至 `310,344`，减少 `64`，即 `0.020618%`；其余五组当前 portfolio 与 baseline 持平。

**证据等级**：PUBLISHED  
**证据**
- `results/q1_promoted/q1_promoted_summary.csv`
- fresh Q1 CI comparison + published-result verifier

**禁止措辞**
- “显著改善”——相对幅度很小；
- “所有六组均改善”。

### Q1-C4｜外部公开 Problem1 schedule 对照

**允许结论**  
Q1 CI 下载的一套公开六组 Problem1 schedule 经本仓库 evaluator 独立重放后全部合法，六组 peak 与本队 baseline 恰好一致。

**证据等级**：EXTERNAL-REPLAY  
**证据**
- Q1 validation artifact / `q1-public-benchmark.csv`
- `results/q1_promoted/README.md`

**禁止措辞**
- 不称该外部仓库为“官方最优答案”；
- 不用它证明本队 Q1 全局最优；
- 不把外部 schedule 当本队 promoted 选择来源。

---

## Q2

### Q2-C1｜物理连续地址约束

**允许结论**  
Q2 要在真实缓存容量内为 resident buffer 分配连续地址区间；同缓存池、residency 重叠的 buffer 区间不得重叠，因此存在 external fragmentation。

**证据**
- `study/README.md`
- `src/q2_allocator.py`
- `src/q2_validator.py`

### Q2-C2｜Q2 的目标是额外搬运字节数，不是 SPILL 次数

**允许结论**  
正式 Q2 promotion 首要比较 `extra_traffic`，SPILL 次数仅作次级指标，因此“更少 SPILL”不能替代“更少搬运字节”。

**证据等级**：PUBLISHED  
**证据**
- `results/q2_optimized/README.md`
- `results/q2_optimized/q2_optimized_summary.csv`
- `src/q2_promoted.py`
- strict replay CI

### Q2-C3｜六组正式 extra traffic

**允许结论**

- Matmul_Case0：`28,800`
- Matmul_Case1：`430,208`
- FlashAttention_Case0：`54,016`
- FlashAttention_Case1：`242,552`
- Conv_Case0：`177,904`
- Conv_Case1：`721,464`

**证据等级**：PUBLISHED  
**证据**：`results/q2_optimized/q2_optimized_summary.csv`

### Q2-C4｜Matmul promotion 改善

**允许结论**  
在 promotion 验收中，Matmul 两组总额外搬运量由 `495,616` 降至 `459,008`，减少 `36,608`（`7.386%`）；SPILL 次数由 `3,872` 降至 `3,586`。FlashAttention / Conv 四组严格保持原 baseline 指标。

**证据等级**：ACCEPTED  
**证据**
- `results/q2_optimized/README.md`
- Q2 full validation workflow / artifact

**注意**  
该合计比较目前来源于正式 promotion 验收说明，不从论文脚本反向解析 README 制图；正文可文字引用，图表只用 committed summary CSV。

### Q2-C5｜Q2 验证

**允许结论**  
Q2 候选通过独立 strict replay；此外 small Matmul unit-cache 与 exact Belady oracle 比较用于验证启发式/代价语义，公开历史 Problem2 附件也被独立重放。

**证据等级**：ACCEPTED + EXTERNAL-REPLAY  
**证据**
- `.github/workflows/test-cpmcm-2025-a-q2.yml`
- `src/benchmark_q2_matmul_oracle.py`
- `src/q2_validator.py`

**禁止措辞**
- exact micro oracle 不能外推为六组大实例全局最优证明。

---

## Q3 fixed-traffic 主链

### Q3-C1｜优化目标与安全门禁分离

**允许结论**  
Q3 正式排序目标为 `official_literal_cycles`；`residency_safe` 只作物理安全可行性门禁，并要求 safe overlap error 为 0。

**证据等级**：PUBLISHED + ACCEPTED  
**证据**
- `src/q3_evaluator.py`
- `results/q3_formal_fixed_traffic/README.md`
- `q3_formal_fixed_traffic_summary.csv/json`

**禁止误解**  
不能把 safe cycles 当成与 official cycles 等权的优化目标。

### Q3-C2｜fixed-Q2 invariants

**允许结论**  
正式 fixed-traffic Q3 主链保持 promoted Q2 的 SPILL identity/order/count 与 `extra_traffic` 不变，在该不变量下优化 official cycles。

**证据等级**：PUBLISHED + ACCEPTED  
**证据**
- `results/q3_formal_fixed_traffic/README.md`
- formal CSV / JSON
- formal acceptance scripts

### Q3-C3｜六组正式 official cycles

**允许结论**

- Matmul_Case0：`133,682`
- Matmul_Case1：`1,531,946`
- FlashAttention_Case0：`187,945`
- FlashAttention_Case1：`962,022`
- Conv_Case0：`595,302`
- Conv_Case1：`3,749,777`

**证据等级**：PUBLISHED  
**证据**：`results/q3_formal_fixed_traffic/q3_formal_fixed_traffic_summary.csv`

### Q3-C4｜六组相对 promoted-Q2 raw 的改善率

**允许结论**

- Matmul0：`1.036408%`
- Matmul1：`0.174115%`
- FA0：`3.253288%`
- FA1：`0.075202%`
- Conv0：`6.415831%`
- Conv1：`2.667485%`

**证据等级**：PUBLISHED  
**证据**：formal CSV + published arithmetic verifier。

### Q3-C5｜Conv1 的正式 post-pass 改善

**允许结论**  
Conv1 在旧正式点 `3,767,326` 上通过 cycle-filtered critical-SPILL post-pass 进一步降至 `3,749,777`，再减少 `17,549` cycles；SPILL count 仍为 `9,646`，extra traffic 仍为 `721,464`，safe overlap 为 0。

**证据等级**：ACCEPTED  
**证据**
- search run `35056138452`
- formal acceptance run `35064897835`
- `results/q3_formal_fixed_traffic/q3_conv1_cycle_filtered_acceptance.json`
- formal summary CSV/JSON

### Q3-C6｜局部饱和

**允许结论**  
Conv1 当前 `max_switches=16` cycle-filtered critical-SPILL 邻域达到首个 `no_improvement` round，formal acceptance 又独立重跑同邻域得到 `improved=false`，因此可称**该命名邻域局部饱和**。

**禁止措辞**
- “Q3 已收敛到全局最优”；
- “不存在任何更优调度”。

---

## FA1 Traffic–Cycles 权衡

### P-C1｜三个 refined 正式点

**允许结论**

| variant | traffic delta vs promoted Q2 | official cycles | reduction vs raw |
|---|---:|---:|---:|
| fixed traffic | `0%` | `962,022` | `0.075202%` |
| `1>1` | `+0.616775%` | `947,002` | `1.635322%` |
| `2>1` | `+1.034005%` | `912,556` | `5.213213%` |

**证据等级**：PUBLISHED  
**证据**：`results/q3_pareto/q3_refined_official_frontier.csv`

**允许解释**  
少量额外 traffic 可在 FA1 上换取更大周期下降，体现真实多目标 trade-off。

**禁止扩写**
- 三个点不等于完整连续 Pareto front；
- higher-traffic 两点不替代 fixed-traffic 六组主结果。

---

## 可复现性与写作证据

### R-C1｜论文图表可复现

**允许结论**  
正文候选数据图、方法图与 LaTeX 表均由仓库脚本从正式结果生成，并由 public GitHub Actions 做非空输出检查。

**证据**
- `paper/Makefile`
- `paper/figures/scripts/`
- `paper/tables/scripts/`
- `paper/diagrams/scripts/`
- `.github/workflows/build-cpmcm-2025-a-paper-assets.yml`

### R-C2｜不要把 CI 数字写成算法性能

CI runtime、artifact size、run ID、SHA256 只属于可复现性证据，不用于声称算法更快/更优，除非正文专门做 runtime benchmark。

---

## 全文禁止词 / 限定词

除非未来补出严格证明，否则正文禁止无修饰使用：

- “全局最优”
- “最优解”
- “理论最优”
- “绝对优于”
- “完全解决”
- “证明不存在更优解”

优先替换为：

- “当前正式结果”
- “promoted best-known point”
- “在所测试策略组合中最优”
- “在 fixed-Q2-traffic 约束下”
- “在该局部邻域达到 no-improvement”
- “经独立 evaluator / strict replay 验证”
