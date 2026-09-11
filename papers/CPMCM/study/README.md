# CPMCM 国一 / S 级论文精读路线

> 目的：把优秀论文从“收藏的 PDF”转化为比赛时真正可调用的建模经验。每篇精读至少产出完整拆解、模型/算法重构、比赛速查；根据题型增加评审报告、复杂度账本、验证协议或专项审计。

---

## ⭐ 正赛总手册入口

> 单篇精读用于学习案例；真正比赛时优先从下面三个文件进入。

- [`COMPETITION_MASTER_PLAYBOOK.md`](COMPETITION_MASTER_PLAYBOOK.md)：**主手册**。拿题→选题→evaluator→baseline→模型选型→验证→代码→图表→论文→团队协作的完整统一框架。
- [`QUICK_REFERENCE_CARD.md`](QUICK_REFERENCE_CARD.md)：**速查卡**。按“症状→第一动作”组织，正赛卡住时直接翻。
- [`FINAL_AUDIT_CHECKLIST.md`](FINAL_AUDIT_CHECKLIST.md)：**赛末审计表**。冻结模型后逐项打勾，优先排除 evaluator、硬约束、泄漏、单位、结果版本等一票否决错误。

核心纪律：**先证明结果是真的，再证明方法很强。**

---

# 当前进度：9 / 13

## 第一阶段：五类核心能力样本（5/5 完成）

| 顺序 | 年份/题号 | 参赛编号 | 核心训练方向 | 状态 |
|---|---|---|---|---|
| 1 | 2022 C | `C22106140003` | 复杂调度、状态仿真、启发式规则、MILP | ✅ |
| 2 | 2020 F | `F20102840100` | 机理建模、动态 minimax、滚动贪心、差分进化 | ✅ |
| 3 | 2021 A | `A21102480004` | 矩阵结构、随机 SVD、复杂度与存储 | ✅ |
| 4 | 2024 B | `B24102860287` | 通信机理 + 数据驱动、验证设计 | ✅ |
| 5 | 2023 B | `B23104860044` | DFT 类矩阵、稀疏/量化、硬件复杂度 | ✅ |

## 第二阶段：S 级扩展精读（4/8 完成）

> 第二阶段按能力互补推进。只有拿到可核验全文后才标记“精读”；校方新闻/摘要不能代替论文正文。

| 总顺序 | 年份/题号 | 参赛编号/目标团队 | 核心训练方向 | 状态 |
|---|---|---|---|---|
| 6 | 2022 B | `B22106140009` | 大规模排样、订单组批、结构化预处理、启发式、下界 | ✅ |
| 7 | 2020 C | `C20102860127` 东南大学；另保留电子科大目标队方法对照 | 信号处理→通道选择→监督/半监督→资源受限验证 | ✅ |
| 8 | 2024 F | `F24104860143` 武汉大学 | 轨道机理、参考系/时间尺度、相对论时延、NHPP 仿真 | ✅ |
| 9 | 2024 E | `E24102910005` 南京工业大学；另保留广西大学目标队官方方法对照 | 视频标定→交通状态→时序预测→滞回控制→反事实评估 | ✅ |
| 10 | 2025 C | 中国矿业大学 周缘/牛敏学/王聪 | Frangi、几何特征、Monte Carlo、三维概率重构 | 🟡 证据重构，待封面核验 |
| 11 | 2025 D | 辽宁工程技术大学 石彤彤/赵其伟/安雪菱 | 环境场估计、风险量化、航路优化 | 🟡 证据重构，待封面核验 |
| 12 | 2025 D | 辽宁工程技术大学 关昊岩/谢卓毅/杨骞 | 多源融合、数值预报校正、同题异解 | 🟡 同题候选证据重构；目标队全文未找到 |
| 13 | 2025 F | 湖州师范学院 周萌团队 | 主观美学→可计算指标、图模型、路径规划 | 🟡 F1候选证据重构；目标队全文未找到 |

> **2020 C 来源说明：**原路线点名电子科技大学贾召钱、殷康宁、王文超团队。校方可核验其一等奖身份和方法链，但当前公开优秀论文包中未找到与该队成员精确对应的完整 PDF。为避免冒充全文，本轮实际逐页精读 exact-match 国一 `C20102860127`（东南大学李典泽、付银、程鑫），并另建 UESTC 方法对照。若日后获得可核验全文，再新增独立目录。

> **2024 E 来源说明：**原路线点名广西大学王家宝、石磊、施涵团队（`E24105930017`）。校方官方报道可核验其全国一等奖身份，并公开 YOLOv10+FairMOT、AHP、K-means、改进机器学习、模糊逻辑的总体方法链，但当前公开全文包未收录与该队精确对应的 PDF。本轮实际逐页精读 `E24102910005`（南京工业大学任碧芸、张朝凯、武瑞，全国一等奖、数模之星提名），同时另建广西大学官方方法对照；若日后获得广西大学全文，再新增独立目录。

---

# 已完成成果索引

## 1. 2022 C｜C22106140003

原论文：[`../2022/fulltext/C/C22106140003.pdf`](../2022/fulltext/C/C22106140003.pdf)

- [`2022-C-C22106140003/README.md`](2022-C-C22106140003/README.md)：完整精读与评价
- [`2022-C-C22106140003/MODEL_RECONSTRUCTION.md`](2022-C-C22106140003/MODEL_RECONSTRUCTION.md)：模型/算法/代码重构
- [`2022-C-C22106140003/COMPETITION_PLAYBOOK.md`](2022-C-C22106140003/COMPETITION_PLAYBOOK.md)：复杂调度比赛速查

## 2. 2020 F｜F20102840100

原论文：[`../2020/fulltext/F/F20102840100.pdf`](../2020/fulltext/F/F20102840100.pdf)

- [`2020-F-F20102840100/README.md`](2020-F-F20102840100/README.md)：完整精读
- [`2020-F-F20102840100/MODEL_RECONSTRUCTION.md`](2020-F-F20102840100/MODEL_RECONSTRUCTION.md)：机理状态与 minimax 重构
- [`2020-F-F20102840100/REVIEWER_REPORT.md`](2020-F-F20102840100/REVIEWER_REPORT.md)：评审/答辩审计
- [`2020-F-F20102840100/COMPETITION_PLAYBOOK.md`](2020-F-F20102840100/COMPETITION_PLAYBOOK.md)：机理 + 动态优化速查

## 3. 2021 A｜A21102480004

原论文：[`../2021/fulltext/A/A21102480004.pdf`](../2021/fulltext/A/A21102480004.pdf)

- [`2021-A-A21102480004/README.md`](2021-A-A21102480004/README.md)：完整精读
- [`2021-A-A21102480004/MODEL_RECONSTRUCTION.md`](2021-A-A21102480004/MODEL_RECONSTRUCTION.md)：低秩/矩阵内核重构
- [`2021-A-A21102480004/REVIEWER_REPORT.md`](2021-A-A21102480004/REVIEWER_REPORT.md)：评审审计
- [`2021-A-A21102480004/COMPLEXITY_LEDGER.md`](2021-A-A21102480004/COMPLEXITY_LEDGER.md)：复杂度/存储统一记账
- [`2021-A-A21102480004/COMPETITION_PLAYBOOK.md`](2021-A-A21102480004/COMPETITION_PLAYBOOK.md)：矩阵算法题速查

## 4. 2024 B｜B24102860287

原论文：[`../2024/fulltext/B/B24102860287.pdf`](../2024/fulltext/B/B24102860287.pdf)

- [`2024-B-B24102860287/README.md`](2024-B-B24102860287/README.md)：完整精读
- [`2024-B-B24102860287/MODEL_RECONSTRUCTION.md`](2024-B-B24102860287/MODEL_RECONSTRUCTION.md)：通信机理 + 数据模型重构
- [`2024-B-B24102860287/REVIEWER_REPORT.md`](2024-B-B24102860287/REVIEWER_REPORT.md)：评审审计
- [`2024-B-B24102860287/VALIDATION_PROTOCOL.md`](2024-B-B24102860287/VALIDATION_PROTOCOL.md)：group split / q90 / leakage 协议
- [`2024-B-B24102860287/COMPETITION_PLAYBOOK.md`](2024-B-B24102860287/COMPETITION_PLAYBOOK.md)：机理 + 数据驱动速查

## 5. 2023 B｜B23104860044

原论文：[`../2023/fulltext/B/B23104860044.pdf`](../2023/fulltext/B/B23104860044.pdf)

- [`2023-B-B23104860044/README.md`](2023-B-B23104860044/README.md)：完整精读
- [`2023-B-B23104860044/MODEL_RECONSTRUCTION.md`](2023-B-B23104860044/MODEL_RECONSTRUCTION.md)：FFT / sparse / quantization 重构
- [`2023-B-B23104860044/REVIEWER_REPORT.md`](2023-B-B23104860044/REVIEWER_REPORT.md)：评审审计
- [`2023-B-B23104860044/OBJECTIVE_AND_COST_AUDIT.md`](2023-B-B23104860044/OBJECTIVE_AND_COST_AUDIT.md)：目标函数与硬件成本审计
- [`2023-B-B23104860044/COMPETITION_PLAYBOOK.md`](2023-B-B23104860044/COMPETITION_PLAYBOOK.md)：结构化矩阵速查

## 6. 2022 B｜B22106140009

原论文：[`../2022/fulltext/B/B22106140009.pdf`](../2022/fulltext/B/B22106140009.pdf)

- [`2022-B-B22106140009/README.md`](2022-B-B22106140009/README.md)：完整精读
- [`2022-B-B22106140009/MODEL_RECONSTRUCTION.md`](2022-B-B22106140009/MODEL_RECONSTRUCTION.md)：packing oracle / batching 重构
- [`2022-B-B22106140009/REVIEWER_REPORT.md`](2022-B-B22106140009/REVIEWER_REPORT.md)：评审审计
- [`2022-B-B22106140009/PACKING_BATCHING_AUDIT.md`](2022-B-B22106140009/PACKING_BATCHING_AUDIT.md)：下界、硬约束与复现审计
- [`2022-B-B22106140009/COMPETITION_PLAYBOOK.md`](2022-B-B22106140009/COMPETITION_PLAYBOOK.md)：排样/组批速查

## 7. 2020 C｜C20102860127

原论文：[`../2020/fulltext/C/C20102860127.pdf`](../2020/fulltext/C/C20102860127.pdf)

- [`2020-C-C20102860127/README.md`](2020-C-C20102860127/README.md)：完整精读
- [`2020-C-C20102860127/MODEL_RECONSTRUCTION.md`](2020-C-C20102860127/MODEL_RECONSTRUCTION.md)：resource-efficient EEG pipeline
- [`2020-C-C20102860127/REVIEWER_REPORT.md`](2020-C-C20102860127/REVIEWER_REPORT.md)：评审审计
- [`2020-C-C20102860127/SIGNAL_VALIDATION_AUDIT.md`](2020-C-C20102860127/SIGNAL_VALIDATION_AUDIT.md)：epoch 独立性、泄漏与资源曲线
- [`2020-C-C20102860127/COMPETITION_PLAYBOOK.md`](2020-C-C20102860127/COMPETITION_PLAYBOOK.md)：信号学习速查
- [`2020-C-C20102860127/UESTC_METHOD_COMPARISON.md`](2020-C-C20102860127/UESTC_METHOD_COMPARISON.md)：目标 UESTC 团队官方方法对照

## 8. 2024 F｜F24104860143

原论文：[`../2024/fulltext/F/F24104860143.pdf`](../2024/fulltext/F/F24104860143.pdf)

- [`2024-F-F24104860143/README.md`](2024-F-F24104860143/README.md)：完整精读；轨道、参考系/时间尺度、相对论小项、NHPP 与论文/代码交叉审计
- [`2024-F-F24104860143/MODEL_RECONSTRUCTION.md`](2024-F-F24104860143/MODEL_RECONSTRUCTION.md)：统一 Orbit → Timing → Phase → NHPP 重构
- [`2024-F-F24104860143/REVIEWER_REPORT.md`](2024-F-F24104860143/REVIEWER_REPORT.md)：指导老师/评审老师视角与 12 个模拟答辩问题
- [`2024-F-F24104860143/TIME_AND_SIMULATION_AUDIT.md`](2024-F-F24104860143/TIME_AND_SIMULATION_AUDIT.md)：TT/TDB、GCRS/BCRS、m/km、相对论量纲、NHPP sampler/evaluator 专项审计
- [`2024-F-F24104860143/COMPETITION_PLAYBOOK.md`](2024-F-F24104860143/COMPETITION_PLAYBOOK.md)：物理机理 + 随机过程题速查

## 9. 2024 E｜E24102910005

原论文：[`../2024/fulltext/E/E24102910005.pdf`](../2024/fulltext/E/E24102910005.pdf)

- [`2024-E-E24102910005/README.md`](2024-E-E24102910005/README.md)：60 页完整精读；视频提参、交通流、预警、K(t)、控制、量化与布点审计
- [`2024-E-E24102910005/MODEL_RECONSTRUCTION.md`](2024-E-E24102910005/MODEL_RECONSTRUCTION.md)：Observation → Calibration → State → Forecast → Action → Counterfactual → Sensor Design 重构
- [`2024-E-E24102910005/REVIEWER_REPORT.md`](2024-E-E24102910005/REVIEWER_REPORT.md)：指导老师/评审老师视角与 12 个模拟答辩问题
- [`2024-E-E24102910005/VIDEO_TO_CONTROL_AUDIT.md`](2024-E-E24102910005/VIDEO_TO_CONTROL_AUDIT.md)：测量标定、单位、公式复算、时序验证、K(t)、反事实和传感器布点专项审计
- [`2024-E-E24102910005/COMPETITION_PLAYBOOK.md`](2024-E-E24102910005/COMPETITION_PLAYBOOK.md)：视频交通预测/控制题速查
- [`2024-E-E24102910005/GXU_METHOD_COMPARISON.md`](2024-E-E24102910005/GXU_METHOD_COMPARISON.md)：广西大学王家宝队官方方法链同题对照；不冒充全文精读

---

# 当前能力矩阵

| 样本 | 核心能力 |
|---|---|
| 2022 C | 复杂工程约束 → 状态仿真 → 启发式调度 |
| 2020 F | 物理机理 → 动态系统 → minimax 控制优化 |
| 2021 A | 矩阵结构 → 计算/存储复杂度 → 低秩与算法工程 |
| 2024 B | 通信机理 → 特征工程 → 数据建模 → 严格验证 |
| 2023 B | 结构化矩阵 → 稀疏/量化 → 硬件代价 → Pareto |
| 2022 B | NP-hard 组合优化 → 结构降维 → heuristic → lower bound |
| 2020 C | 事件信号 → group-aware validation → 资源压缩 |
| 2024 F | 轨道/时延机理 → unit/frame/time-scale discipline → NHPP |
| 2024 E | 视频测量 → calibration → 守恒状态 → 时序预测 → hysteresis control → counterfactual |

---

# 统一训练框架

```text
题意 / 最新官方指标
      ↓
结构、机理、状态、工艺或数据生成机制
      ↓
单位 / 参考系 / 数据独立单位 / measurement calibration
      ↓
硬约束与软目标
      ↓
baseline + lower bound / sanity bound
      ↓
可计算模型 / decomposition / algorithm
      ↓
唯一 evaluator
      ↓
独立验证、消融、复杂度、稳健性 / sensitivity
      ↓
单一结果源自动生成论文数字
```

## 使用原则

1. 先复现作者问题链，再抽象可迁移范式；不背模型名。
2. 区分官方题意、赛中更正、论文写法、公开代码和我们的二次判断。
3. 正式比赛以最新官方口径为准。
4. 一等奖论文也做批判性阅读；奖项说明整体优秀，不代表每个公式/附录都无误。
5. 所有题先锁定 evaluator；摘要、正文、表格、附件数字尽量由同一结果源生成。
6. 数据题把 validation protocol 当成模型的一部分。
7. NP-hard 优化同时报告 feasibility 与 lower bound。
8. 算法型题维护 complexity ledger。
9. 物理题额外维护 unit / frame / time-scale ledger，并对每个小修正做 dimension audit。
10. 仿真题把 self-consistency 与 independent validation 分开，不用生成器输入本身冒充独立验证。
11. 视频/传感器题必须维护 measurement calibration 与 uncertainty；像素检测正确不等于物理量正确。
12. 控制题把 counterfactual assumption 与 empirical effect 分开，安全类条件优先写成 hard constraints。


## 11. 2025 D｜ac2d33da18fa 候选（证据级深读）

> **身份边界：**60 页候选《低空湍流监测及最优航路规划研究》与辽宁工程技术大学石彤彤/赵其伟/安雪菱团队国一作品《低空湍流监测与最优航路规划研究》仅“及/与”一字差异，对应国一候选编号 `D25101470116`；但尚未看到候选 PDF 封面队号，所以不计为 exact-match 全文。

- [`2025-D-ac2d33da18fa/README.md`](2025-D-ac2d33da18fa/README.md)：a→b→c→d/e→route 证据级深读
- [`2025-D-ac2d33da18fa/MODEL_RECONSTRUCTION.md`](2025-D-ac2d33da18fa/MODEL_RECONSTRUCTION.md)：probabilistic turbulence state → forecast → chance/CVaR route 重构
- [`2025-D-ac2d33da18fa/TURBULENCE_TO_ROUTE_AUDIT.md`](2025-D-ac2d33da18fa/TURBULENCE_TO_ROUTE_AUDIT.md)：量纲、伪分辨率、验证、NWP、路径最优性专项审计
- [`2025-D-ac2d33da18fa/REVIEWER_REPORT.md`](2025-D-ac2d33da18fa/REVIEWER_REPORT.md)：模拟评审与 16 个答辩问题
- [`2025-D-ac2d33da18fa/COMPETITION_PLAYBOOK.md`](2025-D-ac2d33da18fa/COMPETITION_PLAYBOOK.md)：多源监测→三维场→短临→风险航路速查
- [`2025-D-ac2d33da18fa/SOURCE_PROVENANCE.md`](2025-D-ac2d33da18fa/SOURCE_PROVENANCE.md)：候选身份、SHA 与全文恢复核查


## 10. 2025 C｜eaf6375148b2 候选（证据级深读）

> **身份边界：**91 页候选《基于Frangi滤波的钻孔裂隙识别与三维概率重构》与中国矿业大学数模之星冠军论文题名/方法链高度吻合，但尚未看到 PDF 封面队号，不能绑定 `C25102900037`。

- [`2025-C-eaf6375148b2/README.md`](2025-C-eaf6375148b2/README.md)：像素→几何→JRC→3D→不确定性→补钻证据级深读
- [`2025-C-eaf6375148b2/MODEL_RECONSTRUCTION.md`](2025-C-eaf6375148b2/MODEL_RECONSTRUCTION.md)：统一 fracture posterior 重构
- [`2025-C-eaf6375148b2/IMAGE_TO_3D_UNCERTAINTY_AUDIT.md`](2025-C-eaf6375148b2/IMAGE_TO_3D_UNCERTAINTY_AUDIT.md)：采样测度、JRC、球面方向、连通概率、补钻专项审计
- [`2025-C-eaf6375148b2/REVIEWER_REPORT.md`](2025-C-eaf6375148b2/REVIEWER_REPORT.md)：模拟评审与答辩问题
- [`2025-C-eaf6375148b2/COMPETITION_PLAYBOOK.md`](2025-C-eaf6375148b2/COMPETITION_PLAYBOOK.md)：图像→三维不确定性题速查
- [`2025-C-eaf6375148b2/SOURCE_PROVENANCE.md`](2025-C-eaf6375148b2/SOURCE_PROVENANCE.md)：候选身份与来源边界


## 12. 2025 D｜95743f6ef8d6 候选（同题证据级深读）

> **身份边界：**110 页候选《基于多源数据融合的低空湍流监测与航路优化》是 2025 D 同题优秀论文，但与关昊岩/谢卓毅/杨骞队官方题名《多源观测融合与数值预报校正的低空湍流监测及航路规划》不同，当前不能绑定 `D25101470007`。本目录用于同题异解训练。

- [`2025-D-95743f6ef8d6/README.md`](2025-D-95743f6ef8d6/README.md)：多源融合→NWP校正→风险航路证据级深读
- [`2025-D-95743f6ef8d6/MODEL_RECONSTRUCTION.md`](2025-D-95743f6ef8d6/MODEL_RECONSTRUCTION.md)：probabilistic state → forecast distribution → CVaR/chance route 重构
- [`2025-D-95743f6ef8d6/MULTISOURCE_NWP_ROUTE_AUDIT.md`](2025-D-95743f6ef8d6/MULTISOURCE_NWP_ROUTE_AUDIT.md)：量纲、验证、分辨率、NWP与A*专项审计
- [`2025-D-95743f6ef8d6/SAME_PROBLEM_COMPARISON.md`](2025-D-95743f6ef8d6/SAME_PROBLEM_COMPARISON.md)：与 `ac2d33da18fa` 的逐问同题异解
- [`2025-D-95743f6ef8d6/REVIEWER_REPORT.md`](2025-D-95743f6ef8d6/REVIEWER_REPORT.md)：模拟评审与16个答辩问题
- [`2025-D-95743f6ef8d6/COMPETITION_PLAYBOOK.md`](2025-D-95743f6ef8d6/COMPETITION_PLAYBOOK.md)：多源融合+NWP校正+风险航路速查
- [`2025-D-95743f6ef8d6/SOURCE_PROVENANCE.md`](2025-D-95743f6ef8d6/SOURCE_PROVENANCE.md)：目标队与候选身份边界


## 13. 2025 F｜77892f7dcdfe 主候选（证据级深读 + 实战综合）

> **身份边界：**目标国一作品为湖州师范学院周萌团队 `F25100130044`《江南古典园林的游园路线规划及美学特征建模》；当前四份 2025 F 优秀论文候选题名均不同，不能绑定目标队。本目录以 182 页 `F题-1-江南古典园林的美学特征建模`（evidence `77892f7dcdfe`）为主证据，并横向吸收其余 F 题候选中可迁移的实战技巧。

- [`2025-F-77892f7dcdfe/README.md`](2025-F-77892f7dcdfe/README.md)：主观概念→机制→路径/评分/相似度证据级深读
- [`2025-F-77892f7dcdfe/MODEL_RECONSTRUCTION.md`](2025-F-77892f7dcdfe/MODEL_RECONSTRUCTION.md)：统一 subjective concept → observable state → decision → validation 重构
- [`2025-F-77892f7dcdfe/PRACTICAL_MODELING_TOOLKIT.md`](2025-F-77892f7dcdfe/PRACTICAL_MODELING_TOOLKIT.md)：四份 F 题优秀论文横向提炼的赛场实战工具箱
- [`2025-F-77892f7dcdfe/REVIEWER_REPORT.md`](2025-F-77892f7dcdfe/REVIEWER_REPORT.md)：模拟评审与 16 个答辩追问
- [`2025-F-77892f7dcdfe/TARGET_TEAM_COMPARISON.md`](2025-F-77892f7dcdfe/TARGET_TEAM_COMPARISON.md)：湖州师范目标国一公开方法链对照
- [`2025-F-77892f7dcdfe/COMPETITION_PLAYBOOK.md`](2025-F-77892f7dcdfe/COMPETITION_PLAYBOOK.md)：主观评价/空间体验题速查
- [`2025-F-77892f7dcdfe/SOURCE_PROVENANCE.md`](2025-F-77892f7dcdfe/SOURCE_PROVENANCE.md)：候选全文、目标队与证据边界
