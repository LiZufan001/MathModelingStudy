# Q2 外部提交语义审计（2026-09-11）

## 结论

公开仓库 `Zysishuiyears/2025Huaweicup_Cachenpuscheduling` 中保存的 2025-09-25 原始比赛附件，不能作为问题 2 的严格可行解 benchmark。其 `spill.txt` 可用于分析“曾选择哪些 victim buffer”，但其 schedule / spill 输出和原题规定的 SPILL 语义不一致，因此不能把其较低的 spill 数或按 BufId 重算得到的搬运量视为合法上界。

本项目后续只接受通过 `q2_validator.py` 独立重放的结果作为严格 Q2 结果。

## 原题必须满足的 SPILL 语义

根据仓库内原始题面 DOCX 的直接提取结果：

1. 每次 SPILL 必须生成一对节点：`SPILL_OUT` 与 `SPILL_IN`。
2. 若原图节点数为 `N`，第 `m` 次 SPILL 的两个节点必须使用题面规定的连续数值 Id。
3. `SPILL_OUT` 后目标 buffer 不驻留；后续任何再次使用前必须先执行对应 `SPILL_IN`。
4. 依赖至少包含 `ALLOC -> SPILL_OUT -> SPILL_IN -> FREE`，并按 SPILL_OUT 位置重连该 buffer 已执行/未执行的使用节点。
5. `spill.txt` 第二列是 `NewOffset`，即 SPILL_IN 的新核内地址偏移，不是搬运 cost。
6. COPY_IN-backed buffer 的额外流量为 `Size`，其他 buffer 为 `2*Size`。

权威规则由 `extract_statement_rules.py` 从原始 DOCX 提取，严格实现位于 `q2_model.py` / `q2_validator.py`。

## 对 2025-09-25 原始提交代码的审计

原始代码路径：

`archive/submission_packages/extracted_A25100550012/A25100550012/代码/问题二三代码.py`

### 1. 只生成一个内部 SPILL 标记，没有 SPILL_IN

`spill_victims()` 对 victim：

- 计算一次 cost；
- 追加一个 `spill_<type>_<counter>` 节点；
- 立即调用 `self.free(victim_buf)`。

代码中没有 `pending_spill` 状态，没有第二个 SPILL_IN 节点，也没有在目标 buffer 后续使用前重新分配/回载该 buffer。

因此这不是题面定义的一次完整 SPILL pair。

### 2. allocator 不检查普通操作的 buffer 是否仍驻留

主循环只对 `ALLOC` 调用 allocator，对 `FREE` 调用 `free`。普通计算/搬运节点不会检查其 `Bufs` 中的数据是否仍 resident。

所以一个 buffer 被 victim eviction 后，即使后续 operation 继续使用它，该实现也不会触发 reload 或报错。

### 3. `spill.txt` 把 Cost 写成了 NewOffset

原始 `spill_log` 记录：

`(victim_buf, cost, current_time)`

但 `write_outputs()` 对 tuple 输出：

`rec[0]:rec[1]`

因此提交文件实际写成了：

`BufId:Cost`

而不是题面要求的：

`BufId:NewOffset`

这直接解释了 Conv_Case0 中多个 1536-byte L1 buffer 的第二列为 `3072`：它正好等于 `2*1536`，若解释为 offset，则 reload 区间 `[3072,4608)` 超出 L1=4096。

严格检查发现 Conv_Case0 最后 33 条此类记录越界。

### 4. COPY_IN 与 victim lifetime 信息没有实际进入原始评分

原始主函数使用：

`manager = MultiPoolManager(capacities, {})`

即 COPY_IN 标记表为空，所有 victim 都按普通 buffer 处理。

同时 `MultiPoolManager.alloc()` 只把当前新申请 buffer 自己的 `free_time` 放入传给 pool 的字典。候选 victim 通常不在该字典中，因此其 `remaining_time` 使用固定 fallback，而不是真实 next-use / free 时间。

所以该代码中的所谓 WCB 式 score 不能直接移植为已验证策略。

## 严格复算结果

对原始比赛附件的 `spill.txt`，只按 BufId 和官方 buffer 元数据重算“假设每条记录都是完整官方 SPILL pair 时”的流量：

| Case | 外部记录数 | 条件性官方流量 | Offset 检查 | 严格 schedule |
|---|---:|---:|---|---|
| Matmul_Case0 | 96 | 12,288 | pass | fail（内部字符串 SPILL 标记） |
| Matmul_Case1 | 480 | 61,440 | pass | fail |
| FlashAttention_Case0 | 191 | 48,896 | pass | fail |
| FlashAttention_Case1 | 1,078 | 213,024 | pass | fail |
| Conv_Case0 | 393 | 221,408 | **fail：33 条 reload offset 越界** | fail |
| Conv_Case1 | 5,805 | 655,720 | pass | fail |

注意：上表“条件性官方流量”不是合法解得分，只回答“如果这些 BufId 每条都代表一对完整官方 SPILL，按官方公式会是多少”。原代码实际没有实现这些 pair。

## Schedule-swap 消融

保持本项目严格 Q2 allocator 与 validator 完全不变，仅替换原节点拓扑顺序：

- 对方 Problem1 顺序在 Matmul_Case0/1 上得到的严格 Q2 结果与我们的 Q1 顺序完全相同：`34,816 / 460,800`。
- 从对方 Problem2 schedule 中仅去掉其明确的 `spill_L1_n / spill_UB_n` 内部标记，再将剩余原节点顺序交给我们的严格 allocator，Matmul 反而变为 `47,360 / 522,112`。

因此，对方较低的记录数不能由其 Q1/Q2 原节点顺序解释，主要来自不同且不完整的 SPILL 语义。

## 后续工程决策

1. 不把该公开提交的 `12,288 / 61,440 / ...` 当作严格性能上界。
2. 可以借鉴其“地址窗口选择、长时间不用的 victim、减少碎片”的启发，但任何新策略必须继续生成官方 SPILL pair，并通过独立 validator。
3. 优化重点转为分析本项目严格 allocator 的重复 SPILL 结构与全局 victim 决策，而不是继续追逐外部无效分数或重做 Q1 顺序。
