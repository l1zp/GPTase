# Enzyme Design: Kemp Eliminase Theozyme Calculation

## 目标

从已统计的酶动力学数据出发，基于 6CF0 结构，计算各单点突变变体对应的 theozyme，
分析突变如何改变活性位点的几何/静电环境，为酶设计提供结构依据。

## 数据来源

- **论文**: Bhattacharya et al. 2022 (NMR-guided directed evolution)
- **PDF**: `papers/bhattacharya_2022_nmr_guided_directed_evolution.pdf`
- **提取结果**: `output/kemp/bhattacharya_2022_nmr_guided_directed_evolution/enzyme-variant-normalizer/3/`

## 结构输入分析

论文（Bhattacharya et al., *Nature* 2022, Vol.610）存了 5 个 PDB 结构：

| PDB ID | 结构 | 说明 |
|--------|------|------|
| `6CF0` | Mb(H64V) apo | 口袋太小，连 docking 都做不进去，不用 |
| `7VUC` | FerrElCat apo | Mb(L29I/H64G/V68A)，最活跃 Mb 变体，无底物 |
| `7VUR` | AlleyCat9 apo | — |
| **`7VUS`** | **AlleyCat9 + 5-NBT** | **holo，TS 类似物共晶，主线起点** |
| **`7VUU`** | **AlleyCat10 + 5-NBT** | **holo，TS 类似物共晶，主线起点** |

**策略**：直接从 7VUS/7VUU 出发。
- 两者均为 holo 结构（PDB 关键词：BIOSYNTHETIC PROTEIN-INHIBITOR COMPLEX）
- 5-NBT（5-nitrobenzotriazole）是 Kemp 消去的过渡态类似物，结合姿态即实验级 TS 几何
- 跳过 docking 步骤，直接截取活性位点 cluster 进入 QM

## 当前输入

| 数据 | 状态 | 说明 |
|------|------|------|
| holo 结构 | **已有** | `7VUS` / `7VUU`（AlleyCat9/10 + 5-NBT，RCSB PDB） |
| TS 类似物 | **已有** | 5-NBT 坐标直接来自共晶，无需 docking |
| 动力学参数 | **已有** | kcat、Km、kcat/Km（Mb 变体），来自 normalizer 输出 |
| 底物/反应 | **已有** | Kemp 消去：5-NBI → 2-cyano-4-nitrophenoxide |
| QM cluster | **缺失** | 从 7VUS/7VUU 截取活性位点残基 + 5-NBT |
| 计算工具链 | **待确认** | 候选：ORCA / Gaussian |

**暂跳过**: Mb 变体 docking（无 holo 结构）；AF3 结构预测；Rosetta。

## TODO

- [ ] **下载结构**：从 PDB 获取 7VUS 和 7VUU
- [ ] **确认工具链**：QM 用 ORCA 还是 Gaussian？
- [ ] **截取 QM cluster**：从 7VUS/7VUU 提取活性位点残基 + 5-NBT（以催化 Glu 为中心 ~6 Å），末端加 H 封端
- [ ] **运行 QM**：计算活性位点几何与电子结构（过渡态能垒、H 键几何等）
- [ ] **扩展到 Mb 变体**（后续）：待确认是否需要补 Mb holo 结构或转而做 docking
