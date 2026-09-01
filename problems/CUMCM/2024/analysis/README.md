# 2024 CUMCM A题学习入口

题目：**“板凳龙”闹元宵**  
学习论文：上海交通大学《基于动态搜索的“板凳龙”运动状态及路线研究》  
奖项：全国一等奖、北太天元数模之星。

建议按下面顺序阅读：

1. [`01-problem-from-scratch.md`](01-problem-from-scratch.md)  
   不预设知道国一解法，从题目本身一步步推导：螺线参数化、固定弦长链、速度递推、碰撞临界、最小螺距、S形调头与最大安全速度。

2. [`02-national-first-paper-deep-dive.md`](02-national-first-paper-deep-dive.md)  
   对照国一论文和作者公开代码，分析他们为什么这样建模、算法为什么这样选、哪些地方非常值得学、哪些地方仍可更严谨。

3. [`03-transferable-playbook.md`](03-transferable-playbook.md)  
   把本题提炼成可迁移套路：曲线约束链、隐式约束微分、碰撞 broad/narrow phase、可行性边界、分段路径统一参数化、尺度关系降维。

原始材料：

- [官方 A 题 PDF](../official/CUMCM2024Problems/A题/A题.pdf)
- [官方题目文本](source_text/problem_A_official.txt)
- [上海交通大学国一论文 PDF](../papers/national_first/2024-A-上海交通大学-板凳龙-国一.pdf)
- [论文抽取文本](source_text/paper_SJTU_national_first.txt)
- [国一来源说明](../papers/national_first/SOURCES.md)

## 学完这题后应能回答

- 为什么相邻把手固定的是 2.86m / 1.65m，而不是板长？
- 为什么所有把手可以只用一个路径参数表示？
- 为什么固定杆长约束必须用欧氏弦长而不是沿路径弧长？
- 怎样从杆长约束直接推导速度传播关系？
- 怎样把“首次碰撞”变成安全裕量的零点？
- 为什么最小螺距是“外层设计 + 内层最坏工况”的嵌套问题？
- 为什么问题4在约束保持不变时几乎没有继续缩短圆弧的自由度？
- 为什么问题5只需单位龙头速度仿真一次就能求最大安全速度？

如果这些问题能不用看答案讲清楚，这道题才算真正学会。
