# 过渡态计算流程

这份文档把当前 Kemp eliminase / 5-NBI 过渡态计算路线从结构准备之后继续往下接。

当前基线输入已经准备好：

- `design/prepared/7VUS/prepared_complex.pdb`
- `design/prepared/7VUS/prepared_complex_minimized.pdb`
- `design/prepared/7VUU/prepared_complex.pdb`
- `design/prepared/7VUU/prepared_complex_minimized.pdb`

注意：这些结构里的 ligand 仍然是 `3NY` / 5-NBT，即过渡态类似物，不是真实反应底物。
因此这些文件不能直接作为真实 TS 计算的反应物输入。它们的作用是提供实验级 pocket
pose 和活性位点几何模板。

## 1. 计算工具选择

当前主线不走 ORCA / Gaussian，而是参考 `../theozyme-mcp` 里的 CLI：

```bash
theozyme pysisyphus_ts_opt ...
```

对应工具：

- `pysisyphus_ts_opt`
- 后端：Pysisyphus + GPU4PySCF
- 量化方法：PySCF / GPU4PySCF 的 SCF 或 DFT
- 优化算法：`rsprfo` / `rsirfo` / `trim`

选择理由：

- `theozyme-mcp` 已经把 Pysisyphus TS optimization 封装成 CLI / MCP tool
- CLI 支持用 `@file` 读取 XYZ 输入，适合从当前 prepared PDB 生成 TS guess 后直接提交
- GPU4PySCF 后端适合对中等大小 QM cluster 做 DFT 梯度 / Hessian 加速
- 这条路线能和后续 enzyme design MCP 工具链保持一致

当前角色分工：

| 工具 | 当前角色 |
|---|---|
| `prep_structure.py` | 准备完整 protein-ligand complex |
| `extract_cluster.py` / `cap_cluster.py` | 从 complex 截 QM cluster 并加边界 H |
| 自定义转换脚本 | 把 capped cluster / TS guess 转成 XYZ |
| `theozyme pysisyphus_ts_opt` | TS optimization |
| ORCA / Gaussian | 后续可作为交叉验证或生产级单点能备选 |

## 2. 当前需要先区分的三种几何

### 2.1 TS analogue complex

来源：

- `7VUS`
- `7VUU`
- ligand = `3NY` / 5-NBT

作用：

- 提供实验结合姿态
- 提供活性位点几何模板
- 不是最终真实反应物

### 2.2 Reactant complex

需要从 TS analogue complex 构建。

核心动作：

- 用真实底物 `5-NBI` 替换 `3NY`
- 尽量保留 5-NBT 提供的 pocket pose 信息
- 保留 protein / water / metal 环境

这是 TS 计算的 reactant endpoint。

### 2.3 Product-like complex

需要从 reactant complex 或 TS analogue pose 手工构建近似产物几何。

作用：

- 给反应坐标另一端
- 辅助构造 TS guess
- 后续可以用于 IRC / forward-backward displacement 验证

## 3. 推荐总流程

当前推荐分成两条并行线：

- `7VUS` 线
- `7VUU` 线

不要一开始就只选一个结构。先让两条线都跑到 cheap TS / first TS guess，再根据收敛性和化学合理性筛选。

### Step 1：从 prepared complex 建底物版 complex

输入：

```text
design/prepared/7VUS/prepared_complex_minimized.pdb
design/prepared/7VUU/prepared_complex_minimized.pdb
```

输出目标：

```text
design/ts/7VUS/reactant_complex.pdb
design/ts/7VUU/reactant_complex.pdb
```

关键动作：

1. 删除或替换 `3NY`
2. 放入真实底物 `5-NBI`
3. 用 `3NY` 的共晶 pose 约束底物初始姿态
4. 保持 catalytic residues 和环境不变

注意：

- 这一步目前还没有自动脚本
- 不建议直接把 `3NY` 当作真实底物
- 需要明确 5-NBI 的 SMILES / charge / protonation / atom mapping

### Step 2：建立 product-like complex

输出目标：

```text
design/ts/7VUS/product_like_complex.pdb
design/ts/7VUU/product_like_complex.pdb
```

目的：

- 不是一次性得到完美产物
- 而是构造一个能定义反应方向的 product-like endpoint

至少要能体现：

- 被 `GLU17` 抽走的 H 已经转移
- 环开裂相关键已经断裂或显著拉长
- 产物 `2-cyano-4-nitrophenoxide` 的关键几何大体合理

### Step 3：从 complex 截 QM cluster

对 reactant 和 product-like 都截 cluster。

示例命令：

```bash
python .claude/skills/enzyme-qm/scripts/extract_cluster.py \
  design/ts/7VUU/reactant_complex.pdb B 5NI 6.0

python .claude/skills/enzyme-qm/scripts/cap_cluster.py \
  design/ts/7VUU/reactant_complex_cluster_chainB.pdb B
```

说明：

- 上面 `5NI` 只是占位 ligand code，实际要按底物 PDB residue name 调整
- cutoff 先用 `6.0 Å`
- 后续可对 `5.0 / 6.0 / 7.0 Å` 做敏感性测试

输出目标：

```text
design/ts/7VUU/reactant_cluster_chainB_capped.pdb
design/ts/7VUU/product_like_cluster_chainB_capped.pdb
```

### Step 4：生成 TS guess XYZ

`theozyme pysisyphus_ts_opt` 需要的是 XYZ，不是 PDB。

输出目标：

```text
design/ts/7VUU/ts_guess.xyz
```

TS guess 的生成方式建议：

1. 以 reactant cluster 为主体
2. 手工或脚本调整反应坐标到接近 TS
3. 生成 XYZ

对 Kemp elimination，初始 TS guess 至少要沿两个方向变形：

- 底物 C-H 键拉长，H 靠近 `GLU17` carboxylate O
- 环开裂相关键拉长 / 弯曲到 product-like 方向

`3NY` / 5-NBT 的价值就在这里：它可以作为 TS-like pocket pose 参考，但不能直接代替真实 TS。

### Step 5：用 theozyme CLI 做 TS optimization

本地 GPU 容器内运行时：

```bash
theozyme pysisyphus_ts_opt \
  --xyz-content @design/ts/7VUU/ts_guess.xyz \
  --method dft \
  --basis def2-svp \
  --xc b3lyp \
  --algo rsprfo \
  --hessian-init lindh \
  --hessian-recalc 5 \
  --coord-type redund \
  --charge 0 \
  --mult 1 \
  --use-gpu \
  --pal 8 \
  > design/ts/7VUU/ts_opt_result.json
```

远程 GPU worker 模式：

```bash
theozyme --server http://gpu-worker:8080/sse pysisyphus_ts_opt \
  --xyz-content @design/ts/7VUU/ts_guess.xyz \
  --method dft \
  --basis def2-svp \
  --xc b3lyp \
  --algo rsprfo \
  --hessian-init lindh \
  --hessian-recalc 5 \
  --coord-type redund \
  --charge 0 \
  --mult 1 \
  --use-gpu \
  --pal 8 \
  > design/ts/7VUU/ts_opt_result.json
```

当前本仓库的 `llm` 环境没有安装：

- `theozyme`
- `pysisyphus`
- `pyscf`
- `gpu4pyscf`

因此 TS optimization 应该在 `../theozyme-mcp` 的 Docker GPU 容器或远程 SSE 服务里跑。

### Step 5a：先做远程 smoke test

不要直接把 300+ 原子的完整 capped cluster 当作第一轮 smoke test。

真实测试显示：

- `theozyme-mcp` remote CLI 可以正常连接
- `pysisyphus_ts_opt` 在远端可以正常调用
- HCN 三原子 TS smoke test 可以收敛
- 304 原子的 `7VUU/ts_guess.xyz` 使用 `SCF/STO-3G + use_gpu=True` 能进入
  GPU4PySCF 路径，但准备第一轮循环就需要约 87 秒，不适合作为快速 smoke test

因此推荐顺序是：

1. HCN 或同等小体系验证远程 TS tool 可用
2. 只包含 ligand + catalytic base 的核心反应区验证 GPU4PySCF 路径
3. 小 cutoff cluster
4. 完整 capped cluster

当前已完成到第 2 步，并得到以下经验：

- 31 原子的 `5NI + GLU17` 核心反应区可以在远程 `theozyme-mcp` GPU worker
  上稳定运行
- `charge = -1, mult = 1` 对当前核心区是自洽的
- 5-cycle 测试能跑完 Hessian，但会得到多个虚频
- 100-cycle GPU 测试可以把虚频数从 8 降到 4，说明几何已经在朝目标 TS
  方向移动
- 但当前仍未到单一一阶鞍点，因此下一步重点应是改进 TS 初猜或加入约束扫描，
  而不是盲目继续放大 cluster

2026-04-17 的 `autoTS` 31 原子 smoke 结果：

- `python .claude/agents/autots-runner/autots/run.py --profile 7VUU_core --max-rounds 1 --cheap-only`
  会生成 31 原子 XYZ，而不是 304 原子 capped cluster
- 远程 PySCF 不再报 `Electron number 1109 and spin 0 are not consistent`
- 1 轮 cheap 结果为 `MULTI_IMAG`，虚频为 `[-575.30, -81.60, -70.62, -39.09] cm⁻¹`
- 这说明 `7VUU_core` profile 当前适合做核心区初猜搜索；完整 capped cluster
  需要单独 profile 和重新确定 charge/mult
- 20 轮 `7VUU_core` 完整 autoTS 仍未得到单虚频；较好的局部起点是
  `h=0.60, acceptor=OE2, ring=0.70, n=0.60`，因此新增
  `7VUU_core_refine_round11` profile 继续围绕该区域搜索
- refinement profile 使用 `fallback_step=0.05` 做局部正负方向扫描；在
  `MULTI_IMAG` 内部排序时优先避免很大的虚频曲率，再比较虚频数量
- 12 轮 `7VUU_core_refine_round11` 局部扫描仍未得到单虚频；当前较好的
  后续起点是 `h=0.60, acceptor=OE2, ring=0.65, n=0.60`，对应 4 个较低
  曲率虚频 `[-102.48, -80.48, -73.40, -44.96] cm⁻¹`
- 进一步用 `fallback_step=0.02` 做 12 轮细粒度扫描后，出现第二个稳定局部点
  `h=0.62, acceptor=OE2, ring=0.65, n=0.60`，对应 5 个虚频但最大虚频更低：
  `[-98.62, -80.94, -72.94, -40.59, -16.16] cm⁻¹`
- 因此当前 31 原子 core 上至少有两个值得继续的 cheap 区域：
  一个是 `4 imag / max 102.48`，另一个是 `5 imag / max 98.62`
- 方案 A 再用 `fallback_step=0.01` 围绕 `4 imag` 区域细化 12 轮后，
  最优 `4 imag` 候选更新为
  `h=0.61, acceptor=OE2, ring=0.65, n=0.60`
  ，虚频为 `[-99.77, -80.49, -72.02, -42.38] cm⁻¹`
- 同一条 `4 imag` 脊线上的相邻点
  `h=0.62, acceptor=OE2, ring=0.65, n=0.59`
  也较稳定，对应 `[-100.24, -81.03, -71.88, -41.53] cm⁻¹`
- 继续在这条脊线上做更窄扫描后，当前 best cheap 点进一步更新为
  `h=0.6125, acceptor=OE2, ring=0.65, n=0.60`
  ，对应 `4 imag` 和
  `[-99.24, -80.59, -71.63, -41.85] cm⁻¹`
- 对这个 best cheap 点直接做更高质量 `dft/def2-svp` 长步 TS opt 的单点验证后，
  结果退化成 `NOT_CONVERGED`，说明当前问题不只是 cheap cycle 太短
- 因此 autoTS 现已进入“扩 guess 自由度”阶段：新增了 `proton_bend`
  参数，用来显式弯折 `OE···H···C3` 几何
- 三点 `proton_bend` 测试结果：
  - `bend = -0.05` → `4 imag`, max `100.97`
  - `bend = 0.00` → `4 imag`, max `99.24`
  - `bend = +0.05` → `5 imag`, max `97.47`
- 当前结论是：`proton_bend` 会改变谱形，但在当前测试窗口内最佳点仍然是
  `bend = 0.00`

当前确认过的远程入口：

```bash
PYTHONPATH=../theozyme-mcp/src \
python -m theozyme_mcp.cli.main \
  --server http://47.107.143.123:8080/sse \
  pysisyphus_ts_opt \
  --xyz-content @design/ts/7VUU/core_ts_guess.xyz \
  --method scf \
  --basis sto-3g \
  --algo rsprfo \
  --hessian-init lindh \
  --hessian-recalc 0 \
  --max-cycles 5 \
  --coord-type redund \
  --charge 0 \
  --mult 1 \
  --use-gpu \
  --pal 8
```

### Step 6：检查 TS 是否真的成立

`pysisyphus_ts_opt` 的 JSON 输出里重点看：

- `success`
- `data.converged`
- `data.energy_hartree`
- `data.imaginary_freq_cm1`
- `data.final_geometry_xyz`

一个候选 TS 至少要满足：

- 优化收敛
- 有且只有一个有效虚频
- 虚频模式对应 Kemp elimination 反应坐标
- forward / backward displacement 分别能朝 reactant / product 方向走

当前 `pysisyphus_ts_opt` 工具会返回虚频和最终 XYZ，但完整 IRC / mode visualization 还需要后续工具或脚本补齐。

## 4. 第一轮参数建议

第一轮目标不是最终屏障，而是找到可收敛的 TS。

推荐第一轮：

```text
method = dft
xc = b3lyp
basis = def2-svp
algo = rsprfo
hessian_init = lindh
hessian_recalc = 5
coord_type = redund
use_gpu = true
```

更便宜的摸底：

```text
method = scf
basis = sto-3g 或 3-21g
```

生产前复核：

```text
method = dft
xc = b3lyp / pbe0
basis = def2-svp -> def2-tzvp single point
```

注意：

- `charge` 和 `mult` 必须按实际 QM cluster 决定，不能默认照抄 `0/1`
- 如果 cluster 包含去质子化羧酸、phenoxide 或金属，charge 很可能不是 0
- 如果保留 `CA`，需要确认当前 QM 方法和基组是否覆盖该离子

## 5. 当前还缺的脚本

要让流程完全自动化，当前还缺三类 helper：

1. `3NY -> 5-NBI` ligand replacement / atom mapping helper
2. `capped PDB -> XYZ` converter
3. TS guess builder / constrained scan helper

`.claude/agents/autots-runner/autots/run.py` 已经补上自动 TS guess 迭代闭环；提示词和 profile 分别在
`.claude/agents/autots-runner/autots/brief.md` 与 `.claude/agents/autots-runner/autots/profiles.yaml`。
当前 `7VUU_core` profile 会从 capped cluster template 中只筛选 `GLU17 + 5NI`
这 31 个原子提交给 theozyme；不要把这个 `charge=-1, mult=1` profile 用在
304 原子的完整 capped cluster 上，否则 PySCF 会因为电子数/自旋不一致而失败。

在这些 helper 完成前，过渡态 workflow 仍然需要少量人工建模。

## 6. 推荐落盘目录

建议把 TS 相关输出放在：

```text
design/ts/7VUS/
design/ts/7VUU/
```

建议文件名：

```text
reactant_complex.pdb
product_like_complex.pdb
reactant_cluster_chainB.pdb
reactant_cluster_chainB_capped.pdb
product_like_cluster_chainB.pdb
product_like_cluster_chainB_capped.pdb
ts_guess.xyz
ts_opt_result.json
ts_final_geometry.xyz
```

## 7. 当前结论

基于 `../theozyme-mcp` 的 CLI 设计，当前过渡态主线应该是：

```text
prepared_complex_minimized.pdb
  -> replace 3NY with real 5-NBI reactant
  -> build reactant/product-like clusters
  -> build TS guess XYZ
  -> theozyme pysisyphus_ts_opt
  -> validate imaginary mode / IRC direction
```

ORCA / Gaussian 暂时不是主线，而是后续可用于高精度单点、频率复核或外部交叉验证的备选。
