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
- 跳过 docking 步骤，但在截取活性位点 cluster 之前，先对完整 protein-ligand complex 做预处理

## 当前推荐流程

面向 QM cluster 的结构准备顺序现在是：

1. 从原始 holo 结构中选择目标 chain、配体、必要水分子和金属/离子
2. 对完整 complex 做标准化与预处理
   - 统一 altloc
   - 去掉原始 H，后续统一重建
   - `MSE -> MET`
   - 检查 peptide connectivity、二硫键和活性位点缺失原子
   - 用外部后端处理蛋白质子化、蛋白补 H、配体化学态、可选 restrained minimization
3. 从 `prepared_complex.pdb` 截取 QM cluster
4. 只在 cluster 边界添加 `CAP` H，保留已准备好的蛋白/配体 H
5. 将 capped cluster 转成 TS guess XYZ，送入 `theozyme pysisyphus_ts_opt`

对应命令：

```bash
python design/scripts/prep_structure.py \
  --input design/structures/7VUU.pdb \
  --config design/config/7VUU.yaml \
  --outdir design/prepared/7VUU

python .claude/skills/enzyme-qm/scripts/extract_cluster.py \
  design/prepared/7VUU/prepared_complex.pdb B 3NY 6.0

python .claude/skills/enzyme-qm/scripts/cap_cluster.py \
  design/prepared/7VUU/prepared_complex_cluster_chainB.pdb B
```

过渡态计算路线详见 `design/transition_state_workflow.md`。当前主线参考
`../theozyme-mcp` 的 CLI：使用 `theozyme pysisyphus_ts_opt`，后端为
Pysisyphus + GPU4PySCF。

## 当前输入

| 数据 | 状态 | 说明 |
|------|------|------|
| holo 结构 | **已有** | `7VUS` / `7VUU`（AlleyCat9/10 + 5-NBT，RCSB PDB） |
| TS 类似物 | **已有** | 5-NBT 坐标直接来自共晶，无需 docking |
| 动力学参数 | **已有** | kcat、Km、kcat/Km（Mb 变体），来自 normalizer 输出 |
| 底物/反应 | **已有** | Kemp 消去：5-NBI → 2-cyano-4-nitrophenoxide |
| protein prep workflow | **已有脚本** | `design/scripts/prep_structure.py` + `design/config/7VUS.yaml` / `7VUU.yaml` |
| QM cluster | **可重建** | 从 `prepared_complex.pdb` 截取活性位点残基 + 5-NBT |
| 计算工具链 | **主线已定** | `theozyme pysisyphus_ts_opt`（Pysisyphus + GPU4PySCF）；ORCA / Gaussian 作为后续复核备选 |

**暂跳过**: Mb 变体 docking（无 holo 结构）；AF3 结构预测；Rosetta。

## TODO

- [x] **结构输入已就位**：`design/structures/` 中已有 `7VUS` 和 `7VUU`
- [x] **protein prep workflow 已实现**：`design/scripts/prep_structure.py`、manifest、下游 cluster/cap 脚本已更新
- [x] **安装真实化学后端**：`llm` 环境已装 `pdb2pqr`、`propka`、`reduce`、`rdkit`、`openmm`、`openmmforcefields`、`gemmi`
- [x] **运行完整结构预处理**：`7VUS/7VUU` 现已真实产出 `prepared_complex.pdb`、`prepared_complex_minimized.pdb`、`prep_report.json`、`manual_review.json`
- [ ] **人工确认关键化学假设**：重点审查 `3NY`、`GLU17`、`HIS50`、`ASP54` 以及保留水/金属
- [x] **修通真实 OpenMM 最小化**：real backend 已在 `7VUS/7VUU` 上跑通，当前脚本会处理链首缺失 backbone H、链尾 `OXT`、protein/ligand `TER`/`CONECT`
- [ ] **截取 QM cluster**：从 `prepared_complex.pdb` 提取活性位点残基 + 5-NBT（以催化 Glu 为中心 ~6 Å），末端加 `CAP` H 封端
- [x] **确认 QM 工具链**：主线使用 `theozyme pysisyphus_ts_opt`（Pysisyphus + GPU4PySCF）
- [ ] **构建底物版 complex**：用真实 5-NBI 替换 `3NY`，保留 TS 类似物提供的 pocket pose 约束
- [ ] **构建 reactant/product-like cluster**：从底物版 complex 截取并封端
- [ ] **运行第一轮 TS optimization**：先生成 TS guess XYZ，再用 `theozyme pysisyphus_ts_opt` 做 cheap TS 搜索
- [ ] **扩展到 Mb 变体**（后续）：待确认是否需要补 Mb holo 结构或转而做 docking

## 注意事项

- 催化残基质子化、金属配位、配体互变异构/电荷态不能完全依赖自动程序，需通过 manifest override 或 `manual_review.json` 显式审查。
- `7VUS` 原始结构带有 H，`7VUU` 原始结构不带 H；预处理阶段会统一 strip 后再重建，避免混用不同来源的氢坐标。
