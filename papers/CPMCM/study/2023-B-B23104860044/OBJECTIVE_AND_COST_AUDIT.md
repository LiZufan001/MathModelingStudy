# B23104860044｜目标函数与硬件复杂度审计

> 用途：正式比赛遇到“官方自定义误差 + 离散系数 + 硬件复杂度”时直接照这份核查。此文件只处理两件事：**到底优化什么**，以及**到底怎么算复杂度**。

---

# 1. 官方目标函数的时间线

## 1.1 原始题面

原始 DOCX 数学公式为：

\[
J_{old}(A,\beta)=
\frac1N\|\beta F_N-A_1A_2\cdots A_K\|_F^2.
\]

这个形式存在退化风险：β 和近似矩阵同时缩小时，目标可以人为变小。

## 1.2 2023-09-24 官方修改

竞赛专家委员会正式允许把 β 移到近似矩阵一侧：

\[
\boxed{
J(A,\beta)=
\frac1N\|F_N-\beta A_1A_2\cdots A_K\|_F^2
}
\]

所以本论文采用“β 在 A 前”是符合赛中官方通知的。

**比赛教训：**历史题精读时必须核对赛中更正，不能只读最初题面。

---

# 2. 论文公式与公开代码并不一致

论文公式写的是：

\[
J=\frac1N\|E\|_F^2,
\qquad
E=F-\beta H.
\]

但 MATLAB 多处实际计算：

```matlab
1/n * sqrt(norm(E,'fro').^2)
```

由于：

```matlab
sqrt(norm(E,'fro').^2) = norm(E,'fro')
```

代码实际指标为：

\[
\boxed{d=\frac1N\|E\|_F}.
\]

两者关系：

\[
\boxed{J=N d^2}.
\]

因此论文结果表中的 `d` 不能直接解释成官方 RMSE。

---

# 3. 为什么“差一个平方”很严重

这不是简单的单调变换问题，因为：

1. N 会变化；
2. Q5 有固定阈值 `0.1`；
3. 不同 N 下同一个 d 对应的官方 J 完全不同。

例如：

| N | 论文代码 d | 对应官方 J=`Nd²` |
|---:|---:|---:|
| 8 | 0.7163 | 约 4.105 |
| 16 | 1.0154 | 约 16.50 |
| 32 | 0.1588 | 约 0.807 |
| 32 | 0.97415 | 约 30.37 |

这些数字只用于说明口径差异，不用于重新替代论文全部实验。

---

# 4. Q5 的阈值必须换算正确

官方要求：

\[
J\le0.1.
\]

若继续使用论文代码指标 d：

\[
N d^2\le0.1
\]

即：

\[
\boxed{d\le\sqrt{0.1/N}}.
\]

| N | d 的正确上限 |
|---:|---:|
| 8 | 0.11180 |
| 16 | 0.07906 |
| 32 | 0.05590 |

所以统一写：

```python
J = np.linalg.norm(E, 'fro')**2 / N
feasible = J <= 0.1
```

不要在代码中另维护一个“近似等价”的阈值。

---

# 5. β 的解析最优解

固定：

\[
H=A_1\cdots A_K.
\]

目标：

\[
\min_{\beta\in\mathbb R}
\|F-\beta H\|_F^2.
\]

展开后求导：

\[
\boxed{
\beta^*=
\frac{\Re\operatorname{tr}(H^HF)}
{\|H\|_F^2}
}.
\]

论文代码常采用：

\[
\beta_{norm}=\frac{\|F\|_F}{\|H\|_F}.
\]

它只做能量匹配，一般不是最小二乘最优值。

## 比赛纪律

> 所有一维连续参数都先检查能否解析消元。

解析消元能：

- 缩小搜索维度；
- 提高精度；
- 消除一个超参数；
- 给评委明确理论依据。

---

# 6. 官方硬件复杂度

题面定义：

\[
\boxed{C=qL}
\]

其中：

- q：量化位/幅值参数；
- L：所需非平凡复乘次数。

官方免费系数：

\[
\mathcal E=\{0,\pm1,\pm j,\pm1\pm j\}.
\]

因此不是“非零系数都算乘法”，也不是“实数都免费”。

---

# 7. 论文的 Boolean complexity estimator 为什么有问题

附录 `myLogicalize()` 首先根据：

```matlab
~isreal(A(k,j))
```

识别乘法成本。

这意味着所有实数：

```text
2
-2
4
-4
...
```

都会被标记为“无需复乘”。

但官方只豁免：

```text
0, ±1
```

普通 ±2、±4 并不在免费集合中。

因此会系统性少算。

---

# 8. `nnz(mask1*mask2)` 也不是乘法次数

论文进一步采用类似：

```matlab
M1 = nnz(B1*B2)
M2 = nnz(B1*B2*B3)
C  = q*(M1+M2)
```

但矩阵积最终有多少非零位置，不等于计算这个矩阵积用了多少 scalar multiplication。

简单例子：

两个一般 `2×2` 矩阵相乘：

\[
C=AB.
\]

每个输出元素需要 2 次 scalar multiplication，共：

\[
8
\]

次。

但：

\[
\operatorname{nnz}(C)\le4.
\]

所以用 `nnz(product)` 计乘法次数在定义上就错了。

---

# 9. 如果按 factor chain 直接作用于向量，复杂度怎么数

若硬件执行：

\[
x_1=A_Kx,
\quad
x_2=A_{K-1}x_1,
\ldots
\]

则最直接的乘法器计数为：

\[
L=\sum_{k=1}^K
\#\{(i,j):A_k[i,j]\notin\mathcal E\}.
\]

从而：

\[
C=qL.
\]

这是**静态系数乘法器数量/操作量的一种直接实现口径**。

若要进一步利用：

- common subexpression elimination；
- shift-add；
- factor fusion；
- pipeline sharing；

就必须明确新的硬件计算图后重新计数，不能仅靠矩阵代数结果推测。

---

# 10. 正确 complexity evaluator 的伪代码

```python
FREE = {
    0,
    1, -1,
    1j, -1j,
    1+1j, 1-1j,
    -1+1j, -1-1j,
}

def is_free(z, tol=1e-12):
    return any(abs(z-c) < tol for c in FREE)

def multiplier_count(factors):
    L = 0
    for A in factors:
        for z in A.ravel():
            if not is_free(z):
                L += 1
    return L

def hardware_complexity(factors, q):
    return q * multiplier_count(factors)
```

如果系数本来就是整数/高斯整数，就不需要浮点 tolerance。

---

# 11. 复杂度报告至少分四本账

算法型比赛不要把这些混成一句“复杂度降低”。

## 11.1 理论运算复杂度

例如：

\[
O(N\log N),\ O(N^2).
\]

## 11.2 官方硬件指标

\[
C=qL.
\]

## 11.3 wall-clock runtime

```text
CPU / GPU
implementation language
matrix size
mean ± std runtime
```

## 11.4 峰值内存 / 存储

```text
coefficient count
bits
intermediate memory
```

它们解决的是不同问题。

---

# 12. 对“最小复杂度”的措辞要求

除非你能证明：

\[
C=C^*
\]

否则不要写：

> “最小硬件复杂度为……”

更安全：

> “本文算法得到的最低复杂度为……”

或：

> “在所考察的候选方案中，复杂度最低为……”

评审非常在意“heuristic best found”和“global optimum”的区别。

---

# 13. 推荐统一结果文件

所有实验只输出一个机器可读结果：

```json
{
  "N": 32,
  "q": 3,
  "method": "SQ",
  "beta": 0.0,
  "official_loss": 0.0,
  "multiplier_count": 0,
  "hardware_complexity": 0,
  "K": 3,
  "runtime_s": 0.0,
  "feasible": false
}
```

然后：

```text
result.json
   ├─ 自动生成正文表格
   ├─ 自动生成摘要数字
   ├─ 自动生成 Pareto 图
   └─ 自动检查 Q5 feasible
```

这样能避免本论文 Q3 出现的“摘要、表格、结果分析三套数字”。

---

# 14. 提交前 evaluator 单元测试

## Test 1：完美逼近

令：

\[
H=F,\quad\beta=1.
\]

必须：

\[
J=0.
\]

## Test 2：全零逼近

\[
H=0.
\]

未归一化 DFT：

\[
\|F_N\|_F^2=N^2.
\]

所以：

\[
J=N.
\]

## Test 3：尺度一致

令：

\[
H=2F.
\]

解析最优：

\[
\beta^*=1/2,
\]

必须：

\[
J=0.
\]

## Test 4：免费系数

含：

```text
0, ±1, ±j, ±1±j
```

应该贡献 `L=0`。

## Test 5：±2

系数 `2` 必须贡献一次非平凡乘法，不能因为它是实数就免费。

---

# 15. 一句话

> **官方指标不是论文里的装饰性公式，而是算法的唯一裁判；硬件复杂度也必须按实际计算图记账，不能用矩阵非零数代替。**
