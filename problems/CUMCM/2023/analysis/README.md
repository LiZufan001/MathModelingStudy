# 2023 CUMCM 学习入口

> 2023 年目前已完成 A、B 两题的教学式分析。这里作为年度入口，不把不同题型混在一起。

## A题｜定日镜场的优化设计

**核心训练：**空间布局、几何光学、黑箱仿真评价、结构化降维与优化。

推荐顺序：

1. [A｜01 从题目到模型：自己重新做一遍](01-problem-from-scratch.md)
2. [A｜02 国一论文深度拆解](02-national-first-paper-deep-dive.md)
3. [A｜03 迁移手册](03-transferable-playbook.md)

原始材料：

- [官方 A题与附件](../official/A题/)
- [中山大学国一论文](../papers/national_first/2023-A-中山大学-定日镜场优化设计模型-国一.pdf)
- [A题官方文本抽取](source_text/problem_A_official.txt)
- [A题论文文本抽取](source_text/paper_SYSU_national_first.txt)

**一句话记忆：**先造出可靠的“布局 → 年均性能”评价器，再把成千上万个镜子的自由变量压缩成少数结构参数，最后围绕评价器做优化。

---

## B题｜多波束测线问题

**核心训练：**斜坡几何、3D→2D 截面降维、一维区间覆盖、贪心递推、复杂地形局部线性化与自适应分区。

推荐顺序：

1. [B题学习入口](2023-B/README.md)
2. [B｜01 从题目到模型：不看国一，自己重新做一遍](2023-B/01-problem-from-scratch.md)
3. [B｜02 国一 / 北太天元数模之星论文深度拆解](2023-B/02-national-first-paper-deep-dive.md)
4. [B｜03 迁移手册：覆盖规划、局部线性化与自适应分区](2023-B/03-transferable-playbook.md)

原始材料：

- [官方 B题与附件](../official/B题/)
- [南京邮电大学获奖队伍论文（赛后发表版）](../papers/national_first/2023-B-南京邮电大学-基于区域划分的多波束测线布设-国一-赛后发表版.pdf)
- [B题官方文本抽取](source_text/problem_B_official.txt)
- [B题论文文本抽取](source_text/paper_NJUPT_national_first_B_published.txt)
- [B题附件表格文本抽取](source_text/problem_B_attachment.txt)

**版本说明：**当前 B题论文为获奖队伍赛后正式发表的期刊版，不冒充赛时原始提交稿。

**一句话记忆：**先建立“位置 / 航向 → 覆盖条带”的几何评价器；规则坡面把二维布线降成一维区间覆盖，复杂地形则局部平面化，最后必须回原始深度场做全局验收。