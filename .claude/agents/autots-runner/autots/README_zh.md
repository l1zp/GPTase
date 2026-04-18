# autoTS（中文版）

> English version: [`README.md`](README.md)

受 [karpathy/autoresearch](https://github.com/karpathy/autoresearch) 启发的自动化过渡态（TS）搜索循环：
**瘦 harness + YAML 描述的反应 + 有界轮次预算**，由 LLM 驱动参数提议。

现在一个 case 就是一个 `reaction.yaml`（加上 `profiles.yaml` 配置每个系统、`brief.md`
做 LLM 提示）。**每个 case 不再需要任何 Python 代码** —— harness 的
`reaction_spec.py` 解释器在加载时把 YAML 编译成运行时的
`mutate` / `compute_metrics` / `classify_single_imag` 函数。

## 架构

```
.claude/agents/autots-runner/autots/
├── autots_types.py      # 数据类（TSState、AutoTSProfile、AutoTSParamsBase ...）
├── profiles.py          # load_profile(profile_id, profiles_path, params_cls)
├── theozyme.py          # submit_theozyme + XYZ / 虚频解析
├── diagnostics.py       # diagnose(result, guess, profile, ...) + write_ts_guess
├── reporting.py         # checkpoint_record + write_summary
├── propose.py           # propose_via_llm（从 dataclass schema 生成 prompt + ±step 兜底）
├── builder.py           # apply_residue_overrides + format_ts_guess（XYZ 组装）
├── pdb_io.py            # 通用 PDB 记录解析与行编辑
├── geometry.py          # 纯 3D 数学工具
├── reaction_spec.py     # YAML -> Reaction（动态 params + mutate / metrics / classify）
├── run.py               # `python run.py --reaction <path> --profile <id>` —— 通用驱动
└── cases/
    ├── _template/           # 复制起点
    │   ├── reaction.yaml    # DSL 骨架，内含 TODO
    │   ├── profiles.yaml    # 每个系统的 profile 占位
    │   ├── brief.md         # LLM 提示占位
    │   └── README.md        # 引导步骤
    └── kemp/                # 完整示例 —— 无 Python，只有 YAML + Markdown
        ├── reaction.yaml    # Kemp 消除反应声明
        ├── profiles.yaml    # 7VUU profiles
        ├── brief.md         # Kemp 反应的 LLM 提示
        └── README.md        # Kemp 背景与引用
```

## 快速开始

```bash
conda activate llm
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/kemp/reaction.yaml \
    --profile 7VUU_core \
    --max-rounds 20 \
    --cheap-only
```

CLI 参数（全部由 harness 的 `run.py` 拥有）：

- `--reaction <path>` —— 定义 case 的 YAML 文件路径
- `--profile <id>` —— 相邻 `profiles.yaml` 中的 profile
- `--profiles <path>` —— 覆盖 profiles 路径（默认找 reaction 同目录）
- `--brief <path>` —— 覆盖 brief 路径（默认找 reaction 同目录）
- `--max-rounds N` —— 轮次预算（默认 20）
- `--cheap-only` —— 跳过 full-QM 确认
- `--run-dir <path>` —— 覆盖本次运行的输出目录

## 反应 DSL

一个 `reaction.yaml` 有六大块：

| 块                         | 作用                                                  |
| -------------------------- | ----------------------------------------------------- |
| `name` + `description`     | 人类可读标识                                           |
| `params`                   | 反应坐标 → 生成的 dataclass 字段                       |
| `residues`                 | 命名残基角色，从 `profile.case_config` 解析             |
| `atoms`                    | 命名原子引用（角色 + PDB 名，或 `$param`）              |
| `mutations`                | 每个原子的变换配方：`interpolate(...)` + 可选 `perpendicular_bend` |
| `metrics`                  | 加权位移分数（可选）                                   |
| `classify_single_imag`     | hotspot + 阈值判定 WRONG/AMBIG/VALID（可选）           |

支持的变换原语：

- `place_along_bond` —— `anchor + 单位向量(direction[0] → direction[1]) * distance`
- `atom: <key>` —— 目标是另一个已解析原子的 xyz
- `interpolate` —— 反应物原子与目标点之间的线性插值，由 fraction 字段参数化
- `perpendicular_bend` —— 垂直于反应坐标轴的额外位移（质子转移 bend 模式用）

参见 [`cases/kemp/reaction.yaml`](cases/kemp/reaction.yaml) —— 它能按位复现
31 原子的 7VUU Kemp TS guess。

## 新增一个酶（按步骤）

目标：拿到一对酶+底物，产出一个可用的 `reaction.yaml`，开跑搜索 ——
全程不写 Python。

### 1. 准备 capped cluster PDB

用上游 `design/transition_state_workflow.md` 流水线生成 reactant-like
capped cluster，包含所有要冻结的残基 + 底物 + 催化残基。存到稳定位置，
例如 `design/ts/<SYSTEM_ID>/reactant_cluster.pdb`。

### 2. 复制模板

```bash
cp -r .claude/agents/autots-runner/autots/cases/_template .claude/agents/autots-runner/autots/cases/<enzyme_id>
```

拿到四个待填文件。

### 3. 写 `reaction.yaml`（让 LLM 帮忙）

喂给 LLM：
- 一段反应化学描述（"谷氨酸拔苯并异噁唑质子，协同 C–O 断裂与 C≡N 生成"）。
- 你的 cluster PDB 里反应原子名清单（grep `HETATM` + 底物残基行）。
- `.claude/agents/autots-runner/autots/cases/kemp/reaction.yaml` 做参考。
- `cases/_template/reaction.yaml` 注释里的 DSL 原语列表。

让它输出一个完整的 `reaction.yaml`（含 `params` / `residues` / `atoms` /
`mutations` / `metrics` / `classify_single_imag`）。跑一轮 cheap-only
（第 5 步）验证 schema 错误。

### 4. 写 `profiles.yaml`

用 Kemp 的某个 profile 做骨架，然后：
- `cluster_path` 指向第 1 步的 PDB。
- 设 `charge` 和 `mult`（用外部工具核算）。
- 设 `chain` + `reaction.yaml` 引用的残基字段（如
  `ligand_resname: XXX, ligand_resseq: 101`）。
- `initial_guess` 里为 `params` 块声明的每个字段填合理初值。
- `cheap_mode` / `full_mode` 保持 Kemp 默认，除非你的体系需要不同 QM 设置。

### 5. 单轮烟测

```bash
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/<enzyme_id>/reaction.yaml \
    --profile <profile_id> \
    --max-rounds 1 --cheap-only \
    --run-dir /tmp/autots_smoke
```

用 PyMOL / VMD 打开 `/tmp/autots_smoke/round_00/ts_guess.xyz` 确认变换
的确动了你想动的原子。看 `ts_opt_result_cheap.json` 确认 QM worker 能
吃这个几何（`success: true` 且 `data` 非空）。

### 6. 写 `brief.md`

描述反应、评分规则、启发式。参考 `cases/kemp/brief.md` —— **评分解读**
章节要和你的 `classify_single_imag` 保持一致；**启发式**告诉 LLM 遇到
某种失败模式时该扰动哪个参数。

### 7. 跑完整搜索

```bash
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/<enzyme_id>/reaction.yaml \
    --profile <profile_id> \
    --max-rounds 20
```

每次运行写入 `<profile.output_root>/run_<timestamp>/`。

## 运行结果与归档

新的运行结果写到每个 profile 的 `output_root` 下 —— 按约定是
`.claude/agents/autots-runner/autots/cases/<enzyme_id>/runs/<system_id>/run_<ts>/`。

YAML-DSL 重构之前的历史运行已归档到
[`cases/kemp/runs/archive/`](cases/kemp/runs/archive/README.md)。因为
YAML 驱动的 mutator 与老版 Python 逐字节一致（由回归测试保证），那些
QM 输出仍可与今天产生的结果做跨轮对比，不需要重跑。

当一个 case 积累了你不希望和新结果混在一起的"实验性"运行，把它们挪到
同级的 `archive/` 目录并写一个 `README.md` 说明为什么搁置（可参考 Kemp
archive 的写法）。

## Harness 不可破坏的不变量

1. **Cluster 不可变** —— 每轮非反应原子来自同一个 cluster 模板；只有
   `mutations` 里列出的原子是自由的。
2. **QM harness 不可变** —— theozyme CLI 参数（除 `--xyz-content` 与
   cheap/full 切换外）不得被 LLM 修改。
3. **Checkpoint 原子性** —— jsonl 追加写在子进程返回之后、`propose_via_llm`
   之前，保证 Ctrl-C 时历史状态一致。

## 测试

```bash
pytest tests/test_design/test_autots.py -v
```

三条 golden 断言全部走 `reaction_spec` + Kemp YAML：`mutate_ts_guess`
复现 31 原子参考几何、`proton_bend` 只扰动 H3、`diagnose` 重放 golden
MULTI_IMAG 输出。这是回归门禁。

## 依赖

- `../theozyme-mcp` GPU worker，通过每个 profile 的 `theozyme_server` URL 访问
- `gptase.models.Model`（在 `llm` conda 环境中通过 `pip install -e .` 安装）
- `config/llm_config.json` 中配置好 `claude-sonnet-4-6`（提议器使用）

## 相关文档

- [`cases/kemp/README.md`](cases/kemp/README.md) —— Kemp 专属背景
