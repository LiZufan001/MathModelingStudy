# B23104860044｜指导老师 / 评审老师报告

> 这不是赛事官方评语，而是基于原题、2023-09-24 官方目标函数修改通知、论文正文、103 页附录与 MATLAB 代码进行的二次评审训练。

---

# 一、如果我是评审老师：第一页后的 60 秒判断

第一印象会比较强：

> **作者没有把 DFT 类矩阵当成一般整数优化题，而是从 FFT/蝶形结构出发设计近似计算图；五问之间也有明确的结构递进。**

值得继续读的原因：

1. 抓住 DFT 的 butterfly structure；
2. 将稀疏和有限整数取值分别建模；
3. 比较 S-Q 与 Q-S 非交换操作顺序；
4. Q4 真正利用 Kronecker；
5. Q5 不重新推翻前面模型，而是追加 residual correction factor；
6. 附录给出了大量 MATLAB 实现；
7. 最终获全国一等奖、华为专项二等奖。

这类作品的优势是：**方法明显针对题目，而不是算法名的拼盘。**

---

# 二、指导老师最值得表扬的 8 点

## 1. 结构优先

先写：

\[
F_N=WRP
\]

再决定优化哪些 factor。

这比直接搜索任意：

\[
A_1\cdots A_K
\]

成熟得多。

## 2. 能把硬件条件变成矩阵约束

```text
每行最多两个非零
有限整数实/虚部
```

都不是抽象数学装饰，而是直接对应低复杂度实现。

## 3. 比较两个投影顺序

S-Q / Q-S 是一个很好的实验意识：

> 两个离散变换不交换，就应该实测顺序影响。

## 4. Q4 利用 Kronecker，而不是暴力处理 32×32

这是结构型矩阵题里非常正确的判断。

## 5. Q5 的 pseudoinverse correction 有创造性

连续域先求一个最优右修正，再投影回硬件可实现集合，是很值得发展的思路。

## 6. 贯穿五问的故事线统一

```text
结构分解
→ 稀疏
→ 量化
→ 联合约束
→ 特殊结构
→ 精度补偿
```

论文不是五套不相干模型。

## 7. 有硬件意识

虽然复杂度 estimator 存在问题，但作者至少没有只看 Frobenius error，而是持续考虑 C。

## 8. 对 Q5 失败有诚实说明

作者明确承认当前结果很难满足 `RMSE<0.1`，这一点比掩盖约束失败更值得肯定。

---

# 三、A级评审风险

这些问题会直接影响“结果是否满足题意”。

## A1. 公开代码 evaluator 少了平方

官方：

\[
J=\frac1N\|F-\beta H\|_F^2.
\]

代码：

\[
d=\frac1N\|F-\beta H\|_F.
\]

这会改变：

- 所有误差表；
- 跨 N 比较；
- Q5 `0.1` 门槛。

**评审结论：高风险。**

## A2. 硬件复杂度统计与官方 C=qL 不一致

主要问题：

- 普通实系数 ±2、±4 被当成免费；
- 使用 `nnz(Boolean matrix product)` 代替 scalar multiplication count。

**评审结论：高风险。**

## A3. Q5 没达到精度门槛

论文自己承认未达到。

因此 Q5 只能评价为：

> 提出改善方法，但未完成核心 feasibility requirement。

## A4. Q3 结果数字自相矛盾

摘要、表 7.4/7.5、正文结果分析存在至少三套不同数字。

这会让评审无法判断到底哪组结果是真正提交版本。

---

# 四、B级评审风险

这些问题不一定让答案无效，但会削弱方法解释和“最优性”。

## B1. β 没有解析最优化

范数比不是最小二乘最优 β。

这是一个完全可以消掉的自由变量，却被经验处理。

## B2. “ADMM”与代码实现不对应

没有完整 dual update / residual。

更像贪心 hard sparsification。

算法命名过强。

## B3. SVD 的“重要性解释”不成立

DFT block singular spectrum 完全平坦。

所以不存在根据较大奇异值判断重要方向的问题。

## B4. SVD basis 不唯一，稀疏结果鲁棒性不足

重复奇异值意味着默认 SVD basis 可能随数值实现变化。

论文没有报告这种 basis sensitivity。

## B5. 多处使用“最小误差/最小复杂度”措辞，但没有全局最优证明

算法固定结构、固定 K、贪心投影，应该说：

> best solution found by proposed method

而不是 global minimum。

## B6. exact FFT baseline 不够完整

Q1 的精确 radix-2 FFT 本身天然满足稀疏结构。

真正应该展示的是：

\[
(J,C,K)
\]

Pareto frontier。

---

# 五、C级写作/复现风险

1. 算法伪代码与 MATLAB 若干更新式不一致；
2. `myLogicalize()` 在不同复制版本里免费系数判断不完全一致；
3. Q2 量化器部分实现存在对零误差候选的特殊排除；
4. Q5 complexity recurrence 的伪代码和程序不完全对应；
5. 某些选择步骤使用 `sqrt(norm())` 等非官方指标，但由于单调性可能不改变局部排序——仍应统一。

这些都说明：**代码和论文缺少 single source of truth。**

---

# 六、如果我是评委，我会给这篇什么总体评价

## 创新性：高

- butterfly + sparse/quantized factor design；
- projection-order comparison；
- Kronecker；
- pseudoinverse correction。

## 题目理解：较高

作者理解题目真正考的是“低复杂度硬件近似”，而不是普通矩阵逼近。

## 数学严谨性：中上，但有明显缺口

结构推导有水平，但：

- SVD 解释；
- β 优化；
- ADMM 名称

都可以更严格。

## 结果可信度：中等

最大问题来自 evaluator、复杂度口径和 Q3 数值版本冲突。

## 完整性：较高但 Q5 未闭环

前四问都有完整方案，Q5 有方法但没满足核心门槛。

## 为什么仍是一等奖 + 华为专项二等奖

因为在竞赛评审环境里，**整体方法的针对性、创新性、工程实现量和五问统一程度非常突出**。这些优势足以让它从大量普通解法中脱颖而出。

但若今天以更严格的复现/审计算法标准重新评，必须补强 evaluator 与 complexity ledger。

---

# 七、模拟答辩：12 个评委最可能追问的问题

## Q1. 你们为什么把 β 从 F 前移动到 A 前？

理想回答：

> 这是 2023-09-24 专家委员会正式发布的目标函数修正，我们按修正后的目标求解，并保留原目标用于对照。

不能回答成“我们觉得原题有问题所以自己改了”。

---

## Q2. 你们代码的 RMSE 为什么没有平方？

这是当前论文最难回答的问题。

正确补救：

> 公布附录存在 evaluator 实现错误，应使用 `norm(E,'fro')^2/N`。我们已按官方 evaluator 全部重算。

如果没有重算，不能硬解释成等价。

---

## Q3. 你们的 β 为什么用范数比？这是最优的吗？

理想回答应给出：

\[
\beta^*=\frac{\Re\langle H,F\rangle}{\|H\|^2}.
\]

如果比赛时发现这种问题，应立即替换。

---

## Q4. 你们说使用 ADMM，请指出 dual variable 在哪里更新？

如果没有，就不要硬说 ADMM。

更好的回答：

> 原稿算法名称过强，实际实现是 alternating greedy hard projection；ADMM 只是问题构造启发。

---

## Q5. 为什么 SVD 能判断 DFT 的哪些方向更重要？

理想回答应注意：DFT singular values 全部相等。

所以正确方向是：

> SVD 在这里主要提供可旋转的 unitary factorization，不提供按 singular value 的 importance ranking。

---

## Q6. SVD 不唯一，你们换一个 basis 结果会不会变？

必须做：

```text
不同 SVD basis / unitary rotation
→ 稀疏投影
→ J,C 变化
```

鲁棒性实验。

---

## Q7. 为什么实数 2 不算乘法器？

按照官方规则，**它应该算**。

这会直接暴露 `~isreal()` estimator 的问题。

---

## Q8. `nnz(B1*B2)` 为什么等于复乘次数？

实际上不等于。

必须回到实际 factor graph / circuit 逐个 count。

---

## Q9. 为什么 Q3 摘要、表格和正文的数字不一样？

最好的比赛工程答案只有一个：

> 所有表格从同一结果文件自动生成，禁止手抄。

当前公开论文无法漂亮解释，应承认版本同步问题。

---

## Q10. Q1 的 exact FFT 已经满足稀疏条件，你们为什么还要近似？

正确回答应该落在 Pareto：

> 目的是用一定精度损失换更低 C / 更浅 K / 更简单系数，而不是因为 FFT 不满足稀疏性。

---

## Q11. Q5 你们满足 RMSE≤0.1 了吗？

只能诚实回答：

> 当前方法没有达到，论文提出的是继续降低误差的方向，而不是完成可行解。

---

## Q12. GIG 投影以后误差一定下降吗？

不一定。

连续域 pseudoinverse correction 最优，不代表 sparse/quantized projection 后还最优。

应该增加 accept/reject 或 line search。

---

# 八、如果我是指导老师，比赛 100 小时内怎么管这题

## 0–6 h：只做定义与 baseline

- 官方目标函数；
- 官方更正；
- complexity evaluator；
- exact FFT baseline；
- β analytic solution。

没有通过单元测试，不准开始高级算法。

## 6–20 h：结构分解

- butterfly；
- Kronecker；
- 支持位置；
- factor graph。

目标：得到第一版合法可行结果。

## 20–40 h：稀疏 / 量化投影

- S；
- Q；
- S-Q；
- Q-S；
- alternating projection。

开始画 Pareto。

## 40–60 h：Q4/Q5

Q4 优先利用 Kronecker。

Q5 首要目标不是降低 C，而是：

```text
先找到 J≤0.1 的 feasible solution
```

## 60–75 h：算法增强

- projected LS；
- residual correction；
- beam / local search；
- basis rotation。

## 75–90 h：验证

- evaluator unit tests；
- complexity manual spot check；
- beta analytic check；
- random seeds；
- table/code consistency。

## 90 h 以后：只做论文与验收

禁止最后阶段继续大改核心算法。

---

# 九、我们自己的提交门槛

在论文里出现“最优、最低、满足要求”之前，必须逐条回答：

- [ ] 是官方 evaluator 吗？
- [ ] 是官方 complexity 定义吗？
- [ ] β 已经解析最优吗？
- [ ] baseline 全了吗？
- [ ] hard constraint 全通过吗？
- [ ] “最优”有证明还是 best found？
- [ ] 表格来自同一结果文件吗？
- [ ] Q5 如果 infeasible 是否明确承认？

---

# 十、一句话评语

> **这是一篇结构设计能力很强、创新链很完整的算法型竞赛论文；其最值得学习的是如何把 DFT 的结构转化为离散硬件设计空间，最需要补强的是官方指标、复杂度记账和结果一致性。**
