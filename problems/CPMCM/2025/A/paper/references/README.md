# references

论文参考文献与检索证据工作区。

## 当前文件

- `references.bib`：正式 BibTeX；citation key 后续保持稳定。
- `REFERENCE_MAP.md`：每篇文献在论文中的具体用途，以及禁止越界的解释。
- `SOURCE_AUDIT.md`：出版社 / DOI / arXiv 元数据核验记录。
- `validate_references.py`：离线校验核心 key、DOI、arXiv ID 与映射完整性。

## 当前核心文献范围

已经覆盖论文真正需要的理论背景：

- precedence / list scheduling；
- critical path；
- heterogeneous DAG scheduling；
- dynamic storage allocation 与 fragmentation；
- live interval / interference / register spilling；
- Belady offline replacement oracle；
- DNN inference tensor buffer sharing；
- Pareto / multicriteria optimization。

当前不为了“显得方法多”引用未使用的 GA、SA、NSGA-II 等算法文献。

## 引用约束

- 只收入实际查阅并可追溯的论文、标准、官方资料；
- BibTeX 条目必须能回到 DOI、期刊页面、出版社或官方文档；
- 不为了凑参考文献数量加入未读来源；
- 文献只支持其真实覆盖范围，不能用相邻领域的复杂性结论偷证本题；
- 竞赛优秀论文与理论文献分开管理；前者位于 `papers/CPMCM/2025/`，不混入本 BibTeX；
- 2026 官方《竞赛论文标准文档》发布后，以官方资料单独建立格式/规则引用，不与学术方法文献混淆。

## 本地校验

```bash
python problems/CPMCM/2025/A/paper/references/validate_references.py
```
