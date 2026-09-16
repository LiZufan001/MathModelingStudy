# manuscript

正式 LaTeX 正文工程工作区。

已选版式基线：

`resources/paper_templates/candidates/04_gmcm_2025_overleaf/`

当前仍**不写正式正文**；先冻结结构、claim boundary 和证据映射。2026 第二十三届官方《竞赛论文标准文档》发布后，再把 2025 模板中需要的版式迁入这里，并逐项核对：封面、摘要、页边距、字体字号、标题层级、页码、图表、参考文献与附录。

## 写作前文件

- `OUTLINE.md`：章节施工图。规定每节的模型、公式、结果、图表与边界；
- `CLAIM_LEDGER.md`：关键结论账本。每个“改善/不变/饱和/验证”绑定正式证据和允许措辞。

正式写作顺序按 `OUTLINE.md`，不要从摘要开始。

## 原则

- 不直接修改第三方 submodule；
- 不把上游 TTF 字体复制进本仓库；
- 正式正文只引用 `../figures/generated/`、`../tables/generated/`、`../diagrams/generated/` 和经核验的参考文献；
- 所有最终数字以 `problems/CPMCM/2025/A/results/` 为唯一可信来源；
- 正式结论必须能在 `CLAIM_LEDGER.md` 找到对应证据；
- `promoted / best-known / locally saturated` 不写成“全局最优”。
