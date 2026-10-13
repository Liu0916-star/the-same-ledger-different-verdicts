# v1 → v2: key numbers side by side

v1 = arXiv 2609.24176v1 (results_v1/); v2 = end-of-window balance snapshot + zero-value and airdrop cleaning (results/). Seeds and hyperparameters unchanged. Third scale: v1 = 6.4×10^5-node graph, v2 = full cleaned graph.


### LINK · data

| statistic | v1 | v2 |
|---|---|---|
| raw transfers | 1,233,497 | 1,233,497 |
| active addresses | 642,126 | 132,059 |
| zero-value / airdrop transfers removed | — | 26,311 / 549,598 |
| holders with positive balance | 885,011 | 885,012 |

### UNI · data

| statistic | v1 | v2 |
|---|---|---|
| raw transfers | 433,856 | 433,856 |
| active addresses | 38,667 | 37,153 |
| zero-value / airdrop transfers removed | — | 2,376 / 0 |
| holders with positive balance | 386,029 | 382,972 |

### LINK · C1 · 1w → 1w

| statistic | v1 | v2 |
|---|---|---|
| nodes | 9,876 | 9,656 |
| is_core anchors | 74 | 74 |
| AUC centrality | 0.600 | 0.609 |
| AUC structural (7) | 0.896 | 0.913 |
| AUC GNN mean | 0.912 | 0.930 |
| AUC GNN seed sd | 0.021 | 0.014 |
| AUC GNN constant input | 0.461 | 0.565 |
| AUC node2vec | 0.914 | 0.905 |
| AUC top-5% balance, centrality | 0.770 | 0.813 |
| AUC top-5% balance, structural | 0.767 | 0.811 |
| AUC top-5% balance, GNN | 0.913 | 0.811 |
| purity centrality | 0.0149 | 0.0149 |
| purity structural | 0.0959 | 0.0973 |
| purity GNN | 0.2578 | 0.3200 |
| random baseline | 0.00749 | 0.00766 |
| purity ratio GNN/structural | 2.69 | 3.29 |

### LINK · C1 · 5w → 5w

| statistic | v1 | v2 |
|---|---|---|
| nodes | 49,587 | 48,840 |
| is_core anchors | 86 | 87 |
| AUC centrality | 0.657 | 0.636 |
| AUC structural (7) | 0.914 | 0.921 |
| AUC GNN mean | 0.921 | 0.930 |
| AUC GNN seed sd | 0.011 | 0.026 |
| AUC GNN constant input | 0.491 | 0.548 |
| AUC node2vec | — | — |
| AUC top-5% balance, centrality | 0.792 | 0.814 |
| AUC top-5% balance, structural | 0.812 | 0.823 |
| AUC top-5% balance, GNN | 0.870 | 0.769 |
| purity centrality | 0.0081 | 0.0115 |
| purity structural | 0.0988 | 0.1046 |
| purity GNN | 0.2607 | 0.2726 |
| random baseline | 0.00173 | 0.00178 |
| purity ratio GNN/structural | 2.64 | 2.61 |

### LINK · C1 · 64w → full

| statistic | v1 | v2 |
|---|---|---|
| nodes | 641,276 | 126,445 |
| is_core anchors | 161 | 102 |
| AUC centrality | 0.656 | 0.577 |
| AUC structural (7) | 0.759 | 0.893 |
| AUC GNN mean | 0.757 | 0.900 |
| AUC GNN seed sd | 0.026 | 0.004 |
| AUC GNN constant input | 0.438 | 0.488 |
| AUC node2vec | — | — |
| AUC top-5% balance, centrality | 0.845 | 0.811 |
| AUC top-5% balance, structural | 0.883 | 0.857 |
| AUC top-5% balance, GNN | 0.928 | 0.778 |
| purity centrality | 0.0031 | 0.0020 |
| purity structural | 0.0516 | 0.0853 |
| purity GNN | 0.1282 | 0.2304 |
| random baseline | 0.00025 | 0.00081 |
| purity ratio GNN/structural | 2.48 | 2.70 |

### UNI · C1 · 1w → 1w

| statistic | v1 | v2 |
|---|---|---|
| nodes | 9,765 | 9,803 |
| is_core anchors | 57 | 58 |
| AUC centrality | 0.612 | 0.597 |
| AUC structural (7) | 0.830 | 0.807 |
| AUC GNN mean | 0.846 | 0.834 |
| AUC GNN seed sd | 0.029 | 0.019 |
| AUC GNN constant input | 0.523 | 0.471 |
| AUC node2vec | 0.800 | 0.774 |
| AUC top-5% balance, centrality | 0.805 | 0.839 |
| AUC top-5% balance, structural | 0.836 | 0.850 |
| AUC top-5% balance, GNN | 0.828 | 0.828 |
| purity centrality | 0.0158 | 0.0207 |
| purity structural | 0.0509 | 0.0448 |
| purity GNN | 0.1107 | 0.1102 |
| random baseline | 0.00584 | 0.00592 |
| purity ratio GNN/structural | 2.17 | 2.46 |

### LINK · weekly flows (sender side; v1 mean without outlier week)

| statistic | v1 | v2 |
|---|---|---|
| flow Gini mean | 0.979 | 0.979 |
| top-1% share | 0.811 | 0.811 |
| top-50 share | 0.711 | 0.708 |
| top-50 weekly retention | 0.56 | 0.55 |
| flow HHI mean | 421 | 421 |
| flow HHI min | 158 | 158 |
| flow HHI max | 1147 | 1147 |
| betweenness Gini | 0.877 | 0.879 |
| median weekly nodes | 16,204 | 14,906 |
| Procrustes aligned | 11/11 | 12/12 |
| fewest anchors | 2,027 | 2,018 |
| persistent elite | 157 | 149 |
| elite drift mean | 1.370 | 1.369 |

### UNI · weekly flows (sender side; v1 mean without outlier week)

| statistic | v1 | v2 |
|---|---|---|
| flow Gini mean | 0.969 | 0.969 |
| top-1% share | 0.707 | 0.707 |
| top-50 share | 0.774 | 0.774 |
| top-50 weekly retention | 0.63 | 0.63 |
| flow HHI mean | 386 | 386 |
| flow HHI min | 173 | 173 |
| flow HHI max | 593 | 593 |
| betweenness Gini | 0.833 | 0.833 |
| median weekly nodes | 5,004 | 4,812 |
| Procrustes aligned | 12/12 | 12/12 |
| fewest anchors | 809 | 806 |
| persistent elite | 53 | 53 |
| elite drift mean | 1.506 | 1.450 |

### LINK · roles and brokers

| statistic | v1 | v2 |
|---|---|---|
| core cluster size | 169 | 202 |
| core cluster core rate | 0.1006 | 0.0842 |
| core cluster median counterparties | 80 | 65 |
| core cluster median balance | 3,934.45 | 444.12 |
| ρ balance-counterparties (positive) | 0.0809 | -0.0059 |
| ρ balance-betweenness (positive) | -0.0275 | -0.0488 |
| nodes with positive balance | 5970 | 5571 |
| core vs richest cluster | fused | fused |
| brokers (rank ensemble) | 30 | 22 |
| vote >=50% | 23 | 25 |
| both | 22 | 20 |
| overlap with same-size betweenness set | 7 | 5 |
| overlap v1 / v2 | — | 20 / v1 30 / v2 22 |

### UNI · roles and brokers

| statistic | v1 | v2 |
|---|---|---|
| core cluster size | 154 | 155 |
| core cluster core rate | 0.0844 | 0.0839 |
| core cluster median counterparties | 78 | 77 |
| core cluster median balance | 3,404.89 | 3,524.80 |
| ρ balance-counterparties (positive) | 0.0316 | -0.0182 |
| ρ balance-betweenness (positive) | -0.0515 | -0.0967 |
| nodes with positive balance | 4195 | 4672 |
| core vs richest cluster | fused | fused |
| brokers (rank ensemble) | 18 | 9 |
| vote >=50% | 14 | 10 |
| both | 13 | 9 |
| overlap with same-size betweenness set | 8 | 6 |
| overlap v1 / v2 | — | 8 / v1 18 / v2 9 |

### brokers shared by LINK and UNI

| statistic | v1 | v2 |
|---|---|---|
| shared | 12 | 4 |
| of which identified | 6 | 3 |

### LINK · concentration grid

| statistic | v1 | v2 |
|---|---|---|
| balance HHI all_holders|all | 135.0 | 135.0 |
| balance Gini all_holders|all | 0.9898 | 0.9898 |
| balance HHI all_holders|excl_burn | 135.0 | 135.0 |
| balance Gini all_holders|excl_burn | 0.9898 | 0.9898 |
| balance HHI all_holders|excl_burn_issuer | 115.4 | 115.4 |
| balance Gini all_holders|excl_burn_issuer | 0.9871 | 0.9871 |
| balance HHI active|all | 135.0 | 374.9 |
| balance Gini active|all | 0.9841 | 0.9927 |
| balance HHI active|excl_burn_issuer | 115.4 | 374.9 |
| balance Gini active|excl_burn_issuer | 0.9799 | 0.9927 |
| balance HHI entity-merged | 561.7 | 561.7 |
| balance Gini entity-merged | 0.9898 | 0.9898 |
| flow HHI address | 421.2 | 421.2 |
| flow HHI entity | 653.6 | 653.6 |
| largest entity-level week | 1508.8 | 1508.8 |
| burned % | 0.00 | 0.00 |
| issuer % | 21.00 | 21.00 |
| label coverage of outflow | 0.335 | 0.335 |
| largest entity outflow share | 0.183 | 0.183 |

### UNI · concentration grid

| statistic | v1 | v2 |
|---|---|---|
| balance HHI all_holders|all | 871.8 | 895.2 |
| balance Gini all_holders|all | 0.9976 | 0.9977 |
| balance HHI all_holders|excl_burn | 949.4 | 979.3 |
| balance Gini all_holders|excl_burn | 0.9973 | 0.9974 |
| balance HHI all_holders|excl_burn_issuer | 108.7 | 108.0 |
| balance Gini all_holders|excl_burn_issuer | 0.9961 | 0.9962 |
| balance HHI active|all | 2336.0 | 2947.7 |
| balance Gini active|all | 0.9967 | 0.9961 |
| balance HHI active|excl_burn_issuer | 419.9 | 381.1 |
| balance Gini active|excl_burn_issuer | 0.9913 | 0.9914 |
| balance HHI entity-merged | 961.6 | 989.1 |
| balance Gini entity-merged | 0.9976 | 0.9977 |
| flow HHI address | 385.8 | 385.8 |
| flow HHI entity | 667.1 | 667.1 |
| largest entity-level week | 1290.9 | 1290.9 |
| burned % | 10.76 | 10.63 |
| issuer % | 27.97 | 28.47 |
| label coverage of outflow | 0.315 | 0.315 |
| largest entity outflow share | 0.198 | 0.198 |
