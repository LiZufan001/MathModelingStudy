# 2023 CUMCM 学习入口

> 2023 年目前已完成 A、B、C 三题的教学式分析。这里作为年度入口，不把不同题型混在一起。

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

---

## C题｜蔬菜类商品的自动定价与补货决策

**核心训练：**销量与潜在需求的区分、时间效应与价格效应分离、价格敏感需求、随机补货/报童模型、品类—SKU 层级建模、商品组合混合整数优化与决策回测。

推荐顺序：

1. [C题学习入口](2023-C/README.md)
2. [C｜01 从题目到模型：需求、价格、补货与商品组合](2023-C/01-problem-from-scratch.md)
3. [C｜02 高教社杯论文深度拆解：哪些地方真正强，哪些地方不能照抄](2023-C/02-highest-award-paper-deep-dive.md)
4. [C｜03 迁移手册：从“预测题”升级成“预测—决策一体化”](2023-C/03-transferable-playbook.md)

原始材料：

- [官方 C题与已入库附件](../official/C题/)
- [2023 官方附件清单与大文件说明](../ATTACHMENTS.md)
- [复旦大学高教社杯队伍论文（赛后发表版）](../papers/national_first/2023-C-复旦大学-基于历史数据的蔬菜类商品定价与补货决策模型-高教社杯-赛后发表版.pdf)
- [C题官方文本抽取](source_text/problem_C_official.txt)
- [C题论文文本抽取](source_text/paper_FDU_highest_award_C_published.txt)
- [C题小型附件文本抽取](source_text/problem_C_small_attachments.txt)

**版本说明：**当前 C题论文为复旦获奖队伍赛后正式发表的期刊版，不冒充赛时原始提交稿；期刊版没有完整呈现官方问题1，因此本仓库的问题1自主方案与论文原意严格分开。官方 `附件2.xlsx`（销售流水明细，约 37.3 MiB）按仓库附件策略未直接入库，官方获取方式已记录在 `ATTACHMENTS.md`。

**一句话记忆：**先分清销量与需求，剥离时间效应识别价格作用，再把价格敏感的随机需求放回订货利润模型；品类层解决总量，SKU 层再加入选品、陈列和服务水平约束。