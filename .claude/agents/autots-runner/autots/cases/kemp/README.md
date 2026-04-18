# Kemp 消除酶 autoTS 案例

本目录是 `.claude/agents/autots-runner/autots/` 下 Kemp 消除酶（Kemp elimination）的专用案例（`cases/kemp/`）。

## 案例背景

| 项目 | 内容 |
|---|---|
| 反应 | 5-硝基苯并异噁唑（5-NBI / 5NI）被 GLU17 去质子化开环 |
| PDB | 7VUU（主）、7VUS（对照） |
| 配体 | `5NI`（5-NBI 模拟物） |
| 碱性残基 | GLU17 carboxylate（OE1 / OE2） |
| 目标 | 自动找到 C-H 断裂 + 环开裂耦合的过渡态 |

## 目录结构

| 文件 | 作用 |
|---|---|
| [`brief.md`](brief.md) | LLM proposer 系统提示：反应背景 + 约束 |
| [`profiles.yaml`](profiles.yaml) | Profile 配置（cluster 路径、QM 参数、初始 guess） |
| [`runs/`](runs/) | 各轮次输出（每条 profile 一个子目录） |

## 可用 Profile

```bash
# 31 原子 core 模型（主搜索空间）
python .claude/agents/autots-runner/autots/run.py --case kemp --profile 7VUU_core --max-rounds 20 --cheap-only

# 基于 round 11 最优几何的精细化搜索
python .claude/agents/autots-runner/autots/run.py --case kemp --profile 7VUU_core_refine_round11 --max-rounds 10

# P0 诊断 reactant 端点（固定在 reactant 几何）
python .claude/agents/autots-runner/autots/run.py --case kemp --profile 7VUU_core_p0_reactant --max-rounds 5 --cheap-only
```

## TS Guess 可变参数

| 参数 | 范围 | 含义 |
|---|---|---|
| `h_transfer_frac` | 0.0 ~ 1.0 | H3 从 C3 移向 GLU17 的进度；0.5 = 中点 |
| `acceptor_choice` | `OE1` / `OE2` | 选用 GLU17 的哪个羧基氧 |
| `ring_opening_frac` | 0.0 ~ 1.0 | O1-C7A 键拉伸进度 |
| `n_elongation_frac` | 0.0 ~ 1.0 | N2-C3 键向 nitrile 双键变化进度 |
| `proton_bend` | -30° ~ +30° | 质子转移方向横向偏移（垂直于反应坐标） |
| `perturb_sigma` | 0.0 ~ 0.2 Å | 其他原子 Gaussian 噪声幅度 |

## TSState 分级

| 状态 | 值 | 含义 |
|---|---|---|
| `CRASHED` | 0 | 计算崩溃 |
| `NOT_CONVERGED` | 1 | 未收敛，≥3 虚频 |
| `MULTI_IMAG` | 2 | ≥2 虚频 |
| `SINGLE_IMAG_WRONG` | 3 | 单虚频但位移不在反应区 |
| `SINGLE_IMAG_AMBIG` | 4 | 单虚频且在反应区，但 C-H/环开裂耦合弱 |
| `VALID` | 5 | 单虚频 + C-H ≥0.3 + O1-C7A 耦合 ≥0.15 |

## P0 诊断结论

- **Reactant 端点**：9 个虚频（全部 <200 cm⁻¹），对应柔性口袋软模式 → Lindh Hessian 隐藏了真实谱
- **calc Hessian**：揭示 -385.76 cm⁻¹ 主导虚频，H3 位移 2.119 Å（是第二原子 0.091 Å 的 23 倍）→ 确认 C-H 断裂 TS 特征
- **环开裂耦合**：-385 模式中 O1/C7A 贡献极弱 → 机理可能是 E1cb（分步）而非协同 Kemp TS
- **后续建议**：需要加入 `ring_opening_frac` > 0 的 guess 来激活环开裂坐标

## 依赖

- `.claude/agents/autots-runner/autots/run.py`（主 harness）
- `../theozyme-mcp` GPU worker 可达（`http://47.107.143.123:8080/sse`）
- `conda activate llm` 环境
- `gptase.models.Model`（LLM proposer）
