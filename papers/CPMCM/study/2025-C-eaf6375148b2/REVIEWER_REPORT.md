# 2025 C｜指导老师 / 评审老师报告（证据重构版）

> 本报告不是赛事官方评语。当前尚未取得候选 PDF 本体，评审依据为官方题面、矿大冠军官方报道、第三方 91 页全文人工深读记录和我们的数学二次审计。身份边界见 [`SOURCE_PROVENANCE.md`](SOURCE_PROVENANCE.md)。

---

# 一、评审老师第一印象

如果只看方法链，我会愿意继续读，因为它不是“图像识别题做到二值化就结束”，而是一路推进：

```text
Frangi crack mask
→ sine fracture parameters
→ detrended roughness / JRC
→ 3D fracture planes
→ Monte Carlo uncertainty
→ connectivity
→ uncertainty cloud
→ supplementary drilling
```

这条链的优势是：

> **每一问都把对象升级，而不是换一个模型名。**

而且 Q1 记录机器学习失败和数据泄漏后主动改回传统方法，是非常成熟的竞赛判断。

但如果我是岩体/统计建模方向评委，我很快会抓住三个核心问题：

1. **原题 Barton JRC 是 0–20，为什么你算到 39.36？**
2. **你所谓的“连通概率”为什么由样本 95% 区间线性缩放再平均得到？这真的是概率吗？**
3. **三个“最优补钻点”的目标函数在哪里？如果只是看云图选点，为什么叫最优？**

这三个问题分别对应：

```text
calibration-domain validity
probability semantics
optimization validity
```

---

# 二、指导老师会表扬的 9 点

## 1. 模型选择服从数据规模

10 张无标签图时没有继续硬训深度模型。

## 2. 敢写失败路线

RF/SVM/XGBoost 失败 + leakage 发现不是删掉，而是成为转向传统方法的证据。

## 3. Frangi 有形状机理

利用 Hessian 识别 elongated line/ridge，和裂隙视觉结构匹配。

## 4. Q2 不是一次拟合到底

`closing → DBSCAN → initial fit → reject abnormal blocks → refined fit`，鲁棒性意识好。

## 5. 报告 missing rate

公开深读记录显示 34 条裂隙同时报告拟合误差和缺失比例；这比只给 R² 更透明。

## 6. Q3 主动去趋势

把圆柱展开造成的宏观正弦与局部 roughness 分开，物理意义清楚。

## 7. 不跨 gap 硬插值

分段计算避免把算法补出来的曲线算入真实粗糙度。

## 8. Q4 把不确定性继续传播

不是“拟合一个平面就当真”，而是引入 Monte Carlo orientation uncertainty。

## 9. 最后回到采样设计

知道钻孔不足是根本信息缺口，最后一问不是多画一张三维图，而是回答哪里再测。

---

# 三、A级风险：直接影响主要结论

## A1. JRC 超标准量程未处理

官方题面介绍 Barton JRC：

\[
0\le JRC\le20.
\]

候选结果：

\[
16.28\text{–}39.36.
\]

如果不解释 empirical formula extrapolation / calibration domain，Q3 与 Q4 的物理解释都受影响。

特别是 Q4 又把 JRC 映射为 orientation uncertainty，超域值会进一步进入概率重构。

## A2. 等弧长采样可能改变 Z2 的估计测度

如果原指标是 x 向平均：

\[
\frac1L\int(y')^2dx,
\]

而 equal-arc points 仍等权平均 slope²，实际上高斜率区域被过度采样。

所以“更稳定”不等于“对原定义更无偏”。

必须使用 `Δx` quadrature weight 或连续积分。

## A3. 分段直接平均 JRC 不满足非线性聚合

应先聚合：

\[
L_iZ_{2,i}^2
\]

再由全局 Z2 计算 JRC。

如果直接：

\[
\sum w_iJRC_i,
\]

这是自定义 composite score，需要声明，不应当作原公式自然推论。

## A4. Monte Carlo 输入分布缺少校准

`JRC → sigma(normal)` 的映射有直觉，但不是由观测误差/fit covariance/重复试验得到。

因此大量 Monte Carlo samples 不能自动赋予输出现实概率含义。

## A5. 法向量独立高斯不尊重球面约束

\[
\|n\|=1
\]

以及 `n ≡ -n` 的平面方向等价没有自然进入独立 Cartesian Gaussian。

## A6. “连通概率”更像归一化兼容评分

距离/角度按自身 95% 区间缩放到 0–1，再算：

\[
P=(P_d+P_\theta)/2.
\]

没有现实连通标签/生成事件校准时，最好叫 `connectivity score`。

## A7. 补钻点没有真正优化

第三方全文审读指出 3 个坐标主要从 uncertainty cloud 目视选择：

- 无 objective；
- 无 drilling constraints；
- 无 cost；
- 无 expected uncertainty reduction；
- 无 sequential update。

因此“最优”证据不足。

---

# 四、B级风险：不推翻路线，但削弱说服力

1. Q1 的“光照归一综合最佳”主要是定性图像比较；
2. Frangi 无法天然区分真实裂隙与岩层界面，原题 1 mm + 填充材质判据应更明确进入模型；
3. 水平/垂直先验 mask 可能误删真裂隙；
4. Q2 单纯按 component centroid-y DBSCAN 对交叉/大振幅裂隙不稳；
5. 拟合 error <1 不代表高缺失情况下参数可辨识；
6. Q4 将 232.85 DPI 下采样到 65.73 DPI，但前三问 x/y 像素物理尺度并非完全相同；
7. 候选 Q4 表中周期约 93.9 与理论 94.25 的差异需要解释；
8. IDW uncertainty cloud 是插值可视化，不是严格 posterior field；
9. 两指标简单平均允许一个极差因素被另一个好因素补偿；
10. top-10 分数集中约 0.82–0.84，ranking sensitivity 未讨论。

---

# 五、写作上值得学的地方

## 1. 摘要四问动作句很清楚

每问都写：

```text
任务 → 方法 → 关键结果
```

最后单独列创新点，评委容易抓贡献。

## 2. 问题分析先写“核心挑战”

不是简单复制题面，而是：

```text
挑战1
挑战2
挑战3
→ 技术路线
```

这能给后续每个算法一个存在理由。

## 3. 负结果可成为论证

机器学习失败 → 发现 leakage → 说明小样本不适合 → 选择 traditional CV。

这比“我们比较了多个模型，最终选效果最好者”强很多。

## 4. 中间结果丰富

候选大量展示：

- preprocessing stages；
- clusters；
- initial/refined fit；
- JRC sampling stability；
- 3D plane / uncertainty cloud。

对评委来说，“看见模型在工作”比只看最终表更可信。

### 但反面

第三方深读指出 Q1 六联图在多种预处理和多个图像上重复很多，约 91 页中大量篇幅消耗在相似流程图。

所以我们应该学：

> **展示中间状态，但同一种证据不要重复十次。**

正文放 3 个代表案例 + aggregate table，其余进附件。

---

# 六、如果我是指导老师，赛中设置 8 个 Gate

### Gate 1 — Source / identity

论文、数据、官方更正全部版本锁定。

### Gate 2 — Q1 ground-truth honesty

没有标签就不报伪 accuracy；至少造 micro-label 或 synthetic test。

### Gate 3 — Physical scale

`px→mm` x/y 分开，1 mm fracture criterion 明确实现。

### Gate 4 — Q2 identifiability

缺失率 > 某阈值时必须报告 CI 或 flag，不只报 residual。

### Gate 5 — JRC domain

所有 `JRC>20` 自动标红，先解释再进后问。

### Gate 6 — Sampling definition

等间距/等弧长/自适应必须估计同一个 continuous Z2。

### Gate 7 — Probability semantics

没有概率校准就叫 score；Monte Carlo 输入分布必须有数据来源。

### Gate 8 — “最优”硬门

只要写“最优补钻”，就必须出现：

```text
objective
constraints
candidate/continuous space
solver
baseline
marginal gain
```

否则改词为“推荐”。

---

# 七、模拟答辩 14 问

**Q1. 只有 10 张图、没有像素标签，你凭什么说光照归一最好？**  
应答：只能说定性综合效果最好；正式版补少量人工标注、合成注入和 downstream stability，不能夸成统计最优。

**Q2. 为什么不用 U-Net？**  
应答：数据规模与标签条件不支持；实际尝试传统 ML 还发现 leakage，说明此时结构先验方法更稳健。

**Q3. Frangi 怎么区分岩层界面和裂隙？**  
应答：Frangi 只做 line candidate；需结合 1 mm 张开宽度、填充灰度/纹理、跨界面连续性进一步分类。

**Q4. 为什么 DBSCAN 只用 y 质心不会把两条交叉正弦合并？**  
应答：这是粗聚类；应由后续 model fit/reject 修正，更稳健可用 model-based clustering/RANSAC。

**Q5. 缺失 71% 的裂隙为什么还能可信估 P 和 β？**  
应答：低 residual 不足，需 bootstrap CI / condition number / synthetic missingness，无法辨识时应标 unavailable。

**Q6. 为什么完整裂隙周期不是直接固定 94.25 mm？**  
应答：理论应强约束；偏离可用于诊断非平面、图像畸变或聚类错误。

**Q7. 为什么要去掉正弦趋势再算 JRC？**  
应答：正弦大尺度形态主要是平面与圆柱相交的展开几何，不应冒充局部表面 roughness。

**Q8. 分段后为什么平均 JRC，而不是先合并 Z2？**  
应答：直接平均因非线性一般不等价；更严谨应按段长合并 `Z2²` energy 后统一变换。

**Q9. 等弧长采样为什么不会系统性提高高斜率区域权重？**  
应答：如果等权平均会；需要 `Δx` quadrature weight 或直接连续积分，确保比较的是同一个 Z2。

**Q10. Barton JRC 最大 20，你的 39.36 是什么？**  
应答：raw empirical estimator 超出经典校准域；应报告 extrapolation flag，并用标准轮廓/其他指标校验，不能直接按同尺度解释。

**Q11. 为什么 JRC 大就代表法向量标准差大？**  
应答：只是粗糙度导致平面不稳定的 heuristic；正式概率模型应由 segmentation/fit bootstrap 得 orientation covariance。

**Q12. 法向量三分量独立高斯以后还是单位向量吗？**  
应答：不是；应球面归一化，最好采用 tangent-space/Bingham orientation distribution。

**Q13. 你这个 0.83 为什么叫连通概率？**  
应答：若只是归一化距离角度加权，严格叫 score；真概率应定义 finite-patch intersection event 并由 posterior Monte Carlo 频率估计/校准。

**Q14. 三个补钻点为什么是最优？**  
应答：目视高不确定区只能称推荐；最优需要 expected information gain / uncertainty reduction + drilling cost/feasibility，并序贯选点。

---

# 八、如果今天重交，我认为最值得加的 4 张图

1. **Q1 nuisance-stratified error panel**：泥浆、纹理、钻痕、拼接线分别的 precision/recall；
2. **JRC convergence + domain plot**：采样密度 vs Z2/JRC，并画 20 的校准边界；
3. **orientation posterior plot**：平面法向量在球面/strike-dip 上的 posterior cloud；
4. **supplementary-drilling marginal gain curve**：第 1/2/3 个孔分别减少多少 posterior entropy。

这四张比再加十张二值化过程图更能打动严格评委。

---

# 九、评审式总评

- **题目结构理解：强。** 四问对象递进非常自然。
- **Q1 模型选择：强。** 小样本下不迷信深度学习，失败路线处理成熟。
- **Q2 工程鲁棒性：较强。** 粗聚类 + 拟合提纯，且报告缺失率。
- **Q3 数学严谨性：中等。** 去趋势/分段思路好，但 JRC 量程和采样测度需要补强。
- **Q4 不确定性意识：强。** 但 probability model 本身偏 heuristic。
- **“最优补钻”严格性：偏弱。** uncertainty visualization 强于 optimization。
- **写作展示：强但偏长。** 中间状态充分，部分流程图重复。
- **比赛迁移价值：很高。** 尤其适合训练“二维观测如何升级成三维概率推断”。

---

# 十、一句话

> **这篇最有冠军气质的地方是“模型链会升级对象、也会承认失败”；最需要补强的地方是把 JRC、Monte Carlo、概率和最优这些很强的数学词，逐一对齐它们真正严格的定义。**
