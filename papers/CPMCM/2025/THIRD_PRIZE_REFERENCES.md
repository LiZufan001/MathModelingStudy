# 2025 全国三等奖公开参考材料

> 本页与全国一等奖正式全文统计严格分离。这里记录的是对 2025 赛题学习有价值、且能完成公开身份核验的全国三等奖材料。  
> **本页任何条目都不计入 `M`。**

## A题 · A25100550012 · 南开大学

### 官方身份

2025 官方获奖表记录：

- 题号：A
- 参赛编号：`A25100550012`
- 姜政旭 · 南开大学
- 于雪婧 · 南开大学
- 徐志骏 · 南开大学
- 奖项：全国三等奖

官方奖项数据的公开镜像：

- `lcpmgh/CPMCM-Awards` → `awardlist/2025.csv`
- <https://github.com/lcpmgh/CPMCM-Awards/blob/master/awardlist/2025.csv>

### 公开代码与原提交材料

公开仓库：

- <https://github.com/Zysishuiyears/2025Huaweicup_Cachenpuscheduling>

仓库明确说明项目来源于 2025 年“华为杯”中国研究生数学建模竞赛 A 题，并保留六个官方 SIMD/NPU case。

赛后工程化整理文档 `docs/RECONSTRUCTION_NOTES.md` 明确记录正式竞赛提交基线来自原始目录中的：

- `A25100550012.pdf`
- `A25100550012/A25100550012/Attachment/Problem1`
- `A25100550012/A25100550012/Attachment/Problem2`
- `A25100550012/A25100550012/Attachment/Problem3`
- `A25100550012/A25100550012/代码/问题一代码.py`
- `A25100550012/A25100550012/代码/问题二三代码.py`

整理后论文位于：

- `docs/paper/submission_paper_A25100550012.pdf`
- Git blob SHA：`7883cb87f9a93faff7379826c7f07090ef613110`
- GitHub API 文件大小：`4,308,463 B`

仓库还保留：

- `archive/submission_packages/A25100550012_2025-09-25.rar`
- 解压后的原提交树；
- 原始赛题附件；
- 比赛期 legacy scripts / outputs。

### 原比赛代码时间痕迹

原提交代码 `问题二三代码.py` 文件头保留：

- `Created on Thu Sep 25 11:07:38 2025`
- `@author: JZX`

仓库 Git 提交作者邮箱为：

- `jiangzhengxuoucstu@163.com`

与仓库 owner `Zysishuiyears` 的公开个人学术页面中的姜政旭身份可以交叉对应；但本页的奖项身份最终以官方队号行作为权威基准。

### 方法概览

该队公开代码与 A1/A2 匿名优秀论文方法明显不同：

- Q1：缓存压力感知的贪心拓扑调度，优先释放 UB/L1，并显式限制 L0A/L0B/L0C 活跃分配；
- Q2：多级缓存连续地址 Best-Fit 分配，缓存不足时按 victim 代价执行 SPILL；
- Q3：基于已有 schedule 的保守左移 / ASAP-style 流水压缩。

因此目前没有证据把该材料与匿名 A1/A2 联系起来。

### 证据边界

当前自动环境能够确认：

1. 官方获奖行 exact match：`A25100550012` ↔ 姜政旭 / 于雪婧 / 徐志骏 / 南开大学 / 全国三等奖；
2. 公开仓库保留同一队号的原提交包、代码与论文 PDF 文件；
3. `RECONSTRUCTION_NOTES.md` 明确说明上述文件属于 canonical competition submission baseline。

但 GitHub 对该 PDF 使用二进制/octet-stream 方式提供，本轮自动工具无法独立渲染并读取其封面，因此**不额外声称已在当前自动环境中视觉复核 PDF 首页**。

这不影响它作为全国三等奖公开学习材料使用，但也不改变项目的全国一等奖 `M` 验真规则。

## 当前结论

`A25100550012` 是目前新发现的一套高价值 2025 A题公开对照材料：

> **官方队伍身份 + 原竞赛提交包 + 原代码 + 提交论文 PDF 文件 + 历史输出**

用途建议：纳入“国一 / 国二 / 国三真实赛期方案”横向算法比较，但与正式国一全文库严格分开管理。
