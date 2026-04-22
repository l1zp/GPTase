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

当前已完成到第 2 步。数值结果和迭代历史见 [ts/README.md](ts/README.md)。

关键经验：

- 31 原子 `5NI + GLU17` 核心区使用 `charge = -1, mult = 1`，与 PySCF 电子数自洽
- 100 轮 GPU 优化后虚频从 8 个降至 4 个，说明方向正确，但未到单一鞍点
- 当前重点是改进 TS 初猜（约束扫描 `C3-H3 / H3···OE2`），而不是扩大 cluster

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

## 5. 脚本实现状态

| Helper | 状态 | 位置 |
|---|---|---|
| `3NY → 5-NBI` 替换 | ✓ 已实现 | `design/scripts/replace_3ny_with_5ni.py` |
| `capped PDB → XYZ` 转换 | ✓ 已实现（集成在 autoTS runner 中）| `.claude/agents/autots-runner/autots/run.py` |
| TS guess builder / constrained scan | ○ 部分实现（纯几何插值） | `.claude/agents/autots-runner/autots/cases/kemp/build_guess.py` |

autoTS runner 的 profile 配置在 `.claude/agents/autots-runner/autots/profiles.yaml`。

**重要**：`7VUU_core` profile（`charge=-1, mult=1`）只适用于 31 原子核心区（`GLU17 + 5NI`），
不能用于 304 原子的完整 capped cluster——电子数/自旋不一致会导致 PySCF 报错。

## 6. 输出文件命名约定

TS 相关文件存放在 `design/ts/7VUS/` 和 `design/ts/7VUU/` 下：

```text
reactant_complex.pdb               # 底物版 complex（5NI 替换后）
product_like_complex.pdb           # 产物侧近似几何
reactant_cluster_chainB_capped.pdb # QM cluster（reactant，封端后）
product_like_cluster_chainB_capped.pdb
ts_guess.xyz                       # TS 初猜（全 cluster）
core_ts_guess.xyz                  # TS 初猜（31 原子核心区）
ts_opt_result.json                 # pysisyphus_ts_opt 输出
ts_final_geometry.xyz              # 收敛后 TS 几何
```

ORCA / Gaussian 不是当前主线，留作后续高精度单点或频率复核的备选。
