# Q3 official-oriented zero-traffic baseline

This directory freezes the validated zero-extra-traffic Q3 result where **Appendix-C `official_literal` cycles are the primary objective** and `residency_safe` is retained as a hard physical-safety gate.

## Method

Starting from the promoted Q2 solution, the optimizer alternates:

1. a generic fixed-traffic physical-address portfolio; and
2. critical-bottom-level pipeline rescheduling.

A candidate is accepted only if:

- the independent Q2 replay remains valid;
- SPILL victim identity/order/count and extra traffic are unchanged;
- the `residency_safe` evaluator remains valid; and
- Appendix-C `official_literal` total cycles strictly decrease.

This is intentionally different from the earlier safe-oriented experiment: `residency_safe` is a feasibility constraint, not the competition objective.

## Six-case result

| Case | Baseline official cycles | Optimized official cycles | Improvement | Extra traffic |
|---|---:|---:|---:|---:|
| Matmul_Case0 | 135082 | **133682** | **1.036408%** | 28800 |
| Matmul_Case1 | 1534618 | **1531946** | **0.174115%** | 430208 |
| FlashAttention_Case0 | 197374 | 197374 | 0% | 55188 |
| FlashAttention_Case1 | 962746 | 962746 | 0% | 242552 |
| Conv_Case0 | 631915 | **616478** | **2.442892%** | 178212 |
| Conv_Case1 | 3798753 | **3650628** | **3.899306%** | 724630 |

Across all six cases, official cycles decrease from **7,260,488** to **7,092,854**, a reduction of **167,634 cycles (2.308853%)**, with **zero increase in extra DDR traffic**.

A useful objective-separation example is `Conv_Case0`: its accepted critical reorder improves official cycles from 631915 to 616478 while conservative safe cycles rise from 798190 to 808899. The candidate is still `residency_safe`-valid with zero physical-overlap errors. Therefore the conservative timing view should remain a safety audit rather than replace the official objective.

## Evidence

Validated code commit: `4a794401e1b8e47c5d5988c6657cf8635d0c4108`.

Focused official-objective CI:

- run: `34584707296`
- conclusion: `success`
- focused tests: `12 passed`
- artifact: `10193218781`
- artifact SHA-256: `896da01364419529d9b25503155844c49fb5ee38ae686e1e68b7bbad65f8ee70`

Independent full Q3 integration CI:

- run: `34584652383`
- conclusion: `success`

The exact machine-readable six-case snapshot is stored in `q3_official_zero_traffic_summary.csv`. Full per-step traces remain available in the CI artifact.
