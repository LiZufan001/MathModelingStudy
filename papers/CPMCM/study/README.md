# CPMCM 国一 / S 级论文精读路线

> 目的：把优秀论文从“收藏的 PDF”转化为比赛时真正可调用的建模经验。每篇精读至少产出：完整拆解、模型/算法重构、比赛速查；根据题型增加评审报告、复杂度账本、验证协议或专项审计。

---

# 第一阶段：五类核心能力样本（5/5 完成）

| 顺序 | 年份/题号 | 参赛编号 | 核心训练方向 | 状态 |
|---|---|---|---|---|
| 1 | 2022 C | `C22106140003` | 复杂调度、状态仿真、启发式规则、MILP | ✅ 已完成 |
| 2 | 2020 F | `F20102840100` | 机理建模、动态 minimax、滚动贪心、差分进化 | ✅ 已完成 |
| 3 | 2021 A | `A21102480004` | 矩阵结构、随机 SVD、复杂度与存储 | ✅ 已完成 |
| 4 | 2024 B | `B24102860287` | 通信机理 + 数据驱动、验证设计 | ✅ 已完成 |
| 5 | 2023 B | `B23104860044` | DFT 类矩阵、结构分解、稀疏/量化、硬件复杂度 | ✅ 已完成 |

# 第二阶段：S 级扩展精读（2/8 完成）

> 第二阶段不机械按年份，而按能力互补顺序推进。只有拿到可核验全文后才标记“精读”；校方新闻/摘要不能代替论文正文。

| 总顺序 | 年份/题号 | 参赛编号/目标团队 | 核心训练方向 | 状态 |
|---|---|---|---|---|
| 6 | 2022 B | `B22106140009` | 大规模排样、订单组批、结构化预处理、启发式、下界 | ✅ 已完成 |
| 7 | 2020 C | `C20102860127` 东南大学；另保留电子科大贾召钱队官方方法对照 | 信号处理→通道选择→监督/半监督→资源受限验证 | ✅ 已完成 |
| 8 | 2024 F | `F24104860143` | 物理机理、相对论/运动学修正、非齐次泊松、仿真 | ⏳ 待精读 |
| 9 | 2024 E | 广西大学 王家宝/石磊/施涵 | 视觉提参→拥堵预测→模糊决策，多模型变量传递 | ⏳ 待确认全文后精读 |
| 10 | 2025 C | 中国矿业大学 周缘/牛敏学/王聪 | Frangi、几何特征、Monte Carlo、三维概率重构 | ⏳ 待确认全文后精读 |
| 11 | 2025 D | 辽宁工程技术大学 石彤彤/赵其伟/安雪菱 | 环境场估计、风险量化、航路优化 | ⏳ 待确认全文后精读 |
| 12 | 2025 D | 辽宁工程技术大学 关昊岩/谢卓毅/杨骞 | 多源融合、数值预报校正、同题异解 | ⏳ 待确认全文后精读 |
| 13 | 2025 F | 湖州师范学院 周萌团队 | 主观美学→可计算指标、图模型、路径规划 | ⏳ 待确认全文后精读 |

> **2020 C 来源说明：**原计划优先精读电子科技大学贾召钱、殷康宁、王文超团队。校方官方新闻可核验其一等奖身份和方法链，但当前仓库/公开优秀论文包中未找到能与该队成员精确对应的完整 PDF。为避免把另一队论文冒充目标队，本轮真正逐页精读改用 exact-match 全国一等奖全文 `C20102860127`（东南大学李典泽、付银、程鑫），同时单独保留电子科大官方方法路线对照。若日后找到可核验的电子科大队全文，再新增独立目录，不覆盖本轮资料。

---

# 已完成成果

## 1. 2022 C｜C22106140003

原论文：[`../2022/fulltext/C/C22106140003.pdf`](../2022/fulltext/C/C22106140003.pdf)

- [`2022-C-C22106140003/README.md`](2022-C-C22106140003/README.md)：完整精读与评价
- [`2022-C-C22106140003/MODEL_RECONSTRUCTION.md`](2022-C-C22106140003/MODEL_RECONSTRUCTION.md)：模型、算法与代码重构
- [`2022-C-C22106140003/COMPETITION_PLAYBOOK.md`](2022-C-C22106140003/COMPETITION_PLAYBOOK.md)：比赛速查与迁移模板

## 2. 2020 F｜F20102840100

原论文：[`../2020/fulltext/F/F20102840100.pdf`](../2020/fulltext/F/F20102840100.pdf)

- [`2020-F-F20102840100/README.md`](2020-F-F20102840100/README.md)：完整精读；指导老师与评审老师视角分析四问、结果、优点和缺陷
- [`2020-F-F20102840100/MODEL_RECONSTRUCTION.md`](2020-F-F20102840100/MODEL_RECONSTRUCTION.md)：统一机理状态模型、官方约束、minimax 控制与可复现重构
- [`2020-F-F20102840100/REVIEWER_REPORT.md`](2020-F-F20102840100/REVIEWER_REPORT.md)：模拟评审/答辩追问、扣分风险与赛中指导建议
- [`2020-F-F20102840100/COMPETITION_PLAYBOOK.md`](2020-F-F20102840100/COMPETITION_PLAYBOOK.md)：机理 + 动态优化题速查

## 3. 2021 A｜A21102480004

原论文：[`../2021/fulltext/A/A21102480004.pdf`](../2021/fulltext/A/A21102480004.pdf)

- [`2021-A-A21102480004/README.md`](2021-A-A21102480004/README.md)：结构复用、随机 SVD、矩阵内核、压缩与端到端评价
- [`2021-A-A21102480004/MODEL_RECONSTRUCTION.md`](2021-A-A21102480004/MODEL_RECONSTRUCTION.md)：相似图/代表元、低秩近似、Cholesky solve、分块压缩重构
- [`2021-A-A21102480004/REVIEWER_REPORT.md`](2021-A-A21102480004/REVIEWER_REPORT.md)：官方指标、复杂度口径和理论归属审计
- [`2021-A-A21102480004/COMPLEXITY_LEDGER.md`](2021-A-A21102480004/COMPLEXITY_LEDGER.md)：官方 basic-operation complexity、存储 bit、正确 evaluator
- [`2021-A-A21102480004/COMPETITION_PLAYBOOK.md`](2021-A-A21102480004/COMPETITION_PLAYBOOK.md)：矩阵 / 算法复杂度 / 压缩题速查

## 4. 2024 B｜B24102860287

原论文：[`../2024/fulltext/B/B24102860287.pdf`](../2024/fulltext/B/B24102860287.pdf)

- [`2024-B-B24102860287/README.md`](2024-B-B24102860287/README.md)：Q1 发送机会、Q2 MCS/NSS、Q3 吞吐量与正文—代码—原题审计
- [`2024-B-B24102860287/MODEL_RECONSTRUCTION.md`](2024-B-B24102860287/MODEL_RECONSTRUCTION.md)：carrier sensing、grouped modeling、SINR、层次 AMC、物理+残差模型
- [`2024-B-B24102860287/REVIEWER_REPORT.md`](2024-B-B24102860287/REVIEWER_REPORT.md)：A级验证风险、答辩追问与指导门槛
- [`2024-B-B24102860287/VALIDATION_PROTOCOL.md`](2024-B-B24102860287/VALIDATION_PROTOCOL.md)：实验组切分、泄漏防护、pair accuracy、CDF q90
- [`2024-B-B24102860287/COMPETITION_PLAYBOOK.md`](2024-B-B24102860287/COMPETITION_PLAYBOOK.md)：机理 + 数据驱动题速查

## 5. 2023 B｜B23104860044

原论文：[`../2023/fulltext/B/B23104860044.pdf`](../2023/fulltext/B/B23104860044.pdf)

- [`2023-B-B23104860044/README.md`](2023-B-B23104860044/README.md)：BSVD、稀疏/量化、Kronecker、GIG 与原题—更正—公式—代码审计
- [`2023-B-B23104860044/MODEL_RECONSTRUCTION.md`](2023-B-B23104860044/MODEL_RECONSTRUCTION.md)：官方目标、解析 β、FFT baseline、投影优化、ADMM、residual correction
- [`2023-B-B23104860044/REVIEWER_REPORT.md`](2023-B-B23104860044/REVIEWER_REPORT.md)：A级指标风险、数学解释问题、模拟答辩
- [`2023-B-B23104860044/OBJECTIVE_AND_COST_AUDIT.md`](2023-B-B23104860044/OBJECTIVE_AND_COST_AUDIT.md)：目标函数时间线、RMSE evaluator、`C=qL` 审计
- [`2023-B-B23104860044/COMPETITION_PLAYBOOK.md`](2023-B-B23104860044/COMPETITION_PLAYBOOK.md)：结构化矩阵 / 硬件近似 / 稀疏量化题速查

## 6. 2022 B｜B22106140009

原论文：[`../2022/fulltext/B/B22106140009.pdf`](../2022/fulltext/B/B22106140009.pdf)

- [`2022-B-B22106140009/README.md`](2022-B-B22106140009/README.md)：完整精读；2-Items、stack→stripe→plate、组批 similarity、结果与代码审计
- [`2022-B-B22106140009/MODEL_RECONSTRUCTION.md`](2022-B-B22106140009/MODEL_RECONSTRUCTION.md)：formal model、packing oracle、lower bound、batching feedback、local search 重构
- [`2022-B-B22106140009/REVIEWER_REPORT.md`](2022-B-B22106140009/REVIEWER_REPORT.md)：指导老师/评审老师视角、A级风险与 12 个模拟答辩追问
- [`2022-B-B22106140009/PACKING_BATCHING_AUDIT.md`](2022-B-B22106140009/PACKING_BATCHING_AUDIT.md)：原始数据下界、B2 批次数可行性、正文—表格—代码复现审计
- [`2022-B-B22106140009/COMPETITION_PLAYBOOK.md`](2022-B-B22106140009/COMPETITION_PLAYBOOK.md)：大规模排样 / 组批 / decomposition 现场速查

## 7. 2020 C｜C20102860127

原论文：[`../2020/fulltext/C/C20102860127.pdf`](../2020/fulltext/C/C20102860127.pdf)

- [`2020-C-C20102860127/README.md`](2020-C-C20102860127/README.md)：完整精读；P300 event→字符、稀疏贝叶斯通道选择、S3VM、睡眠分期，以及正文—代码—原题审计
- [`2020-C-C20102860127/MODEL_RECONSTRUCTION.md`](2020-C-C20102860127/MODEL_RECONSTRUCTION.md)：group-aware EEG pipeline、sequential stopping、channel/label/sample resource Pareto 重构
- [`2020-C-C20102860127/REVIEWER_REPORT.md`](2020-C-C20102860127/REVIEWER_REPORT.md)：指导老师/评审老师视角、A级验证风险和 12 个模拟答辩问题
- [`2020-C-C20102860127/SIGNAL_VALIDATION_AUDIT.md`](2020-C-C20102860127/SIGNAL_VALIDATION_AUDIT.md)：epoch 独立性、preprocessing/selection leakage、轮次/标签预算、论文数字和 appendix 复现审计
- [`2020-C-C20102860127/COMPETITION_PLAYBOOK.md`](2020-C-C20102860127/COMPETITION_PLAYBOOK.md)：EEG / 传感器时序 / 少样本学习题现场速查
- [`2020-C-C20102860127/UESTC_METHOD_COMPARISON.md`](2020-C-C20102860127/UESTC_METHOD_COMPARISON.md)：电子科大贾召钱团队校方公开方法链与本篇 exact-match 国一的同题异解对照；不冒充全文精读

---

# 能力矩阵

| 样本 | 核心能力 |
|---|---|
| 2022 C | 复杂工程约束 → 状态仿真 → 启发式调度 |
| 2020 F | 物理机理 → 动态系统 → minimax 控制优化 |
| 2021 A | 矩阵结构 → 计算/存储复杂度 → 低秩与算法工程 |
| 2024 B | 通信机理 → 特征工程 → 数据建模 → 严格验证 |
| 2023 B | 结构化矩阵 → 稀疏/量化 → 硬件代价 → Pareto 设计 |
| 2022 B | NP-hard 大规模组合优化 → 结构降维 → 可行启发式 → lower bound |
| 2020 C | 事件信号 → group-aware validation → 通道/标签/样本资源压缩 |

统一训练目标不是背模型名，而是形成：

```text
题意 / 最新官方指标
      ↓
结构、机理、状态、工艺或数据生成机制
      ↓
硬约束与软目标
      ↓
baseline + lower bound
      ↓
可计算模型 / decomposition / 算法
      ↓
唯一官方 evaluator
      ↓
验证、消融、复杂度、稳健性
      ↓
单一结果源自动生成论文数字
```

---

# 使用原则

1. **先复现作者问题链，再抽象可迁移范式。** 不把专用技巧生搬硬套。
2. **区分“官方题意、赛中更正、论文写法、公开代码、我们的二次判断”。**
3. **优先学习闭环，而不是算法名。**
4. **正式比赛以最新官方口径为准，并同步检查更正通知。**
5. **一等奖论文也要批判性阅读。** 奖项不代表每个公式/参数/代码都无误。
6. **算法型题维护 complexity ledger。** Big-O、官方计价、wall-clock、硬件/内存分开。
7. **数据型题把 validation protocol 当成模型的一部分。** 切片数据必须先定义独立 group。
8. **NP-hard 优化题必须同时报告 feasibility 与 lower bound。** heuristic 好坏不能只看目标值。
9. **formal model 与 actual solver 必须解释关系。** 若用 decomposition，要明确说明为什么。
10. **所有题先锁定 evaluator。** 摘要、正文、表格、CSV、图尽量由同一机器可读结果源生成。
