# REVIEWER_REPORT｜2025 D 同题候选 `95743f6ef8d6`

> 这是对 110 页候选《基于多源数据融合的低空湍流监测与航路优化》的模拟指导/评审报告。候选不能绑定目标国一队 `D25101470007`。

---

# 1. 评审总评

这是一篇**系统设计意识强、技术覆盖面广、但验证证据密度跟不上模型复杂度**的优秀竞赛型论文候选。

最大亮点：

- 多源 reference → 单源 surrogate；
- variational fusion；
- confidence / uncertainty field；
- NWP layer-wise calibration；
- simple forecast ensemble；
- robust / chance route formulation。

最大风险：

- 指标范围与 RMSE 量纲冲突；
- 附录含 synthetic fallback 与不物理的速度拆分；
- 一些评估有 in-sample 风险；
- Q3 后半公式很多但没有实验落地；
- 摘要核心数字找不到正文证据；
- 路径规划缺统一 baseline table；
- A* 最优性论证不足。

一句话评语：

> **架构比上一篇更高级，证据比上一篇更松。**

---

# 2. A 级问题：会直接影响结论可信度

## A1. Ia/Ib 范围与 RMSE 不可能同时成立

若指标：

\[
I\in[0,1],
\]

则：

\[
RMSE\le1.
\]

正文却报告 5–8 量级，需要明确缩放/单位/逆归一化。

## A2. RF 主指标可能包含 in-sample evaluation

公开附录存在 train feature 原地预测路径。

主结果必须证明来自独立 validation/test。

## A3. synthetic fallback 可能让错误输入“正常出图”

`make_default_obs` 随机造数据属于 demo 行为，不能存在于正式结果脚本主路径。

## A4. 径向速度常数比例拆 u/v/w 无物理依据

如果进入主模型，会污染：

```text
wind field
→ shear
→ Ri
→ turbulence
→ route
```

整条链。

## A5. 摘要 `82%` / `35%` 无正文证据回链

关键结果不可审计。

## A6. 路径优化没有统一数值 baseline

没有 straight / shortest / mean-risk / robust 的同表比较，就不足以支撑“暴露量显著下降”。

---

# 3. B 级问题：会限制解释和泛化

## B1. `SW²≈TKE` 需要标成 proxy

谱宽含 beam broadening/shear/noise。

## B2. source weight 与 covariance 可能双重计权

`w_source` 与 `R_s^{-1}` 的职责需要分开。

## B3. error variance 相加假设 independence

应做 ensemble/bootstrap 或给 covariance assumption。

## B4. 100m/50m analysis grid 不是有效分辨率

必须给 observation density / posterior uncertainty。

## B5. NWP 诊断展示网格与目标网格口径并存

500m/400m vs 100m/50m 要解释 compute/display/effective resolution。

## B6. `5-fold CV` 是否 time-aware 不清楚

气象 forecast 不能随机 K-fold。

## B7. forecast 峰值被平滑

实测最大约 0.88，预测约 0.69；需检查 extreme-event recall。

## B8. chance/robust formulation 是否真正进入 solver 不清楚

如果只是公式，不能写成已验证贡献。

---

# 4. C 级问题：写作和工程质量

## C1. problem analysis 重复两次

前文总体思路与第 4 节问题分析高度重复，篇幅效率低。

## C2. Q3 公式堆叠

ST-GCN、attention、wavelet、EMD、spectrum 等未落地，降低主线可信度。

## C3. 交叉引用和编号不干净

出现图号/section 残留，说明赛末版本管理不足。

## C4. 评价章节优点

值得肯定：作者至少能逐模型写失效条件，没有全是模板化“精度高、适应性强”。

---

# 5. 如果我是指导老师，我会要求补的 8 个实验

1. **Range/metric audit**：Ia/Ib、RMSE、R² 单位统一。
2. **blocked-time validation**：替换 random split。
3. **leave-one-site-out**：测试跨站泛化。
4. **fusion ablation**：IDW/OI/3DVAR/+Kalman。
5. **sensor ablation**：去掉 AWS/WPR/DWR 各跑一次。
6. **extreme-event skill**：POD/FAR/CSI。
7. **route baseline table**：straight/shortest/mean/CVaR/chance。
8. **uncertainty calibration**：预测 90% interval 实际 coverage 是否约 90%。

---

# 6. 16 个模拟答辩追问

## Q1 建模

1. **你说 Ia 在 `[0,1]`，为什么 RMSE 可以达到 5.12？**
2. **`exp(-0.5Ri)` 在 Ri<0 时大于 1，你怎么保证归一范围？**
3. **为什么谱宽平方可以叫 TKE？beam broadening 怎么处理？**
4. **模型 a 本身没有真值，你为什么称它基准真值？**
5. **RF 的测试结果是不是在训练数据上预测得到的？**
6. **11 个回归器比较时，超参数搜索是否使用了测试集？**

## Q2 多源融合

7. **source weight 和 R covariance 是否重复表达了传感器可靠性？**
8. **为什么 WPR/DWR/AWS 的固定权重分别是 1.0/0.8/0.6？**
9. **100m 网格的真实有效分辨率是多少？你有什么证据？**
10. **`σ²obs+σ²interp+σ²model` 为什么没有 covariance cross-term？**
11. **leave-one CV 留掉的是一个点、一个站，还是一个完整传感器？**

## Q3 预报

12. **NWP 分层二次校正的 5-fold 是按时间切的吗？**
13. **实测峰值 0.88，预测只有 0.69，强湍流是否被系统性低估？**
14. **摘要的 82% 识别准确率到底对应哪个 evaluator？**

## 航路

15. **A* 的 heuristic 为什么一定 admissible？请给出单位距离代价下界。**
16. **你说湍流暴露量降低 35%，基线是哪条路径、公式是什么、结果表在哪里？**

---

# 7. 高分答辩应该怎么回应

建议统一口径：

- reference 不称 truth；
- proxy 不称 physical TKE；
- grid 不称 effective resolution；
- robust formula 没实验就称 proposed extension；
- A* 最优性只限定在离散图 + 固定 cost；
- 摘要数字只保留能回链结果表的。

评委最怕的是：

> 明明只是工程 proxy，却用绝对物理语言包装。

主动说边界通常不会降分，反而增加可信度。

---

# 8. 我会怎么给这篇定位

**系统架构：A**  
**物理口径：B-**  
**数据融合设计：A-**  
**预报验证：B**  
**航路公式设计：A-**  
**航路实验证据：C+**  
**复现工程：C**  
**写作克制性：C+**

不是正式比赛评分，只是训练用相对评价。

---

# 9. 最终评语

> **如果把没有结果的公式删掉一半，把 Ia/RMSE、真实雷达反演、时间验证、极端风险和路径 baseline 五件事补齐，这条路线会比单纯“LSTM + A*”高出一个完整层级；反过来，如果这些证据缺口不补，复杂的变分、机会约束和图网络只会提高评委追问强度，而不会自动提高可信度。**
