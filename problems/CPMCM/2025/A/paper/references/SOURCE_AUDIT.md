# Reference Source Audit

核验日期：2026-09-16

本文件只记录元数据核验，不保存受版权保护的论文全文。优先采用出版社、DOI 落地页、IEEE/ACM/SIAM/INFORMS/Springer 页面；arXiv 条目直接使用 arXiv。

| BibTeX key | 核验来源 | 已核字段 |
|---|---|---|
| `graham1969multiprocessing` | SIAM Journal on Applied Mathematics, DOI `10.1137/0117039` | author, title, journal, vol.17(2), 416–429, 1969 |
| `hu1961parallel` | INFORMS Operations Research, DOI `10.1287/opre.9.6.841` | author, title, journal, vol.9(6), 841–848, 1961 |
| `kelley1961critical` | INFORMS Operations Research, DOI `10.1287/opre.9.3.296` | author, title, journal, vol.9(3), 296–320, 1961 |
| `belady1966replacement` | IBM Systems Journal metadata / DOI `10.1147/SJ.52.0078` | author, title, vol.5(2), 78–101, 1966 |
| `sethi1975register` | SIAM Journal on Computing, DOI `10.1137/0204020` | author, title, journal, vol.4(3), 226–248, 1975 |
| `chaitin1981coloring` | Elsevier ScienceDirect, DOI `10.1016/0096-0551(81)90048-5` | six authors, title, Computer Languages 6(1), 47–57, 1981 |
| `chow1990priority` | ACM/Crossref metadata, DOI `10.1145/88616.88621` | authors, title, TOPLAS 12(4), 501–536, 1990 |
| `poletto1999linear` | ACM TOPLAS / DBLP, DOI `10.1145/330249.330250` | authors, title, TOPLAS 21(5), 895–913, 1999 |
| `wilson1995dynamic` | Springer IWMM'95, DOI `10.1007/3-540-60368-9_19` | four authors, title, LNCS 986, 1–116, 1995 |
| `topcuoglu2002heft` | IEEE TPDS metadata, DOI `10.1109/71.993206` | authors, title, TPDS 13(3), 260–274, 2002 |
| `pisarchyk2020memory` | arXiv `2001.03288` | authors, title, year, arXiv identifier |
| `ehrgott2005multicriteria` | Springer book page, DOI `10.1007/3-540-27659-9` | author, title, 2nd edition, publisher, 2005, ISBN |

## 核验注意事项

1. `Belady` 的标题在不同索引中存在是否带冠词 `a` 的轻微差异；BibTeX 采用 IBM/DOI 常见形式 `A Study of Replacement Algorithms for a Virtual-Storage Computer`，DOI、卷期和页码无歧义。
2. `Wilson et al.` 的 Springer proceedings 元数据中编辑者姓名在部分索引存在拼写差异；当前 BibTeX 故意不写 editor 字段，只保留无争议的 chapter / booktitle / LNCS / DOI 元数据。
3. `Pisarchyk & Lee` 当前以 arXiv 版本入库；若正式发表版本在写作阶段确认，再用同行评审版本替换，但 citation key 保持稳定。
4. 所有 DOI 都应解析到对应出版物；CI 只做离线结构校验，不在每次构建时访问 DOI，以避免网络波动导致论文构建失败。
