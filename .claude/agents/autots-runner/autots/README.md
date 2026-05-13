# autoTS

> 中文版：[`README_zh.md`](README_zh.md)

Automated transition-state search loop inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch):
**thin harness + YAML-described reactions + bounded round budget**, with an
LLM driving the proposer.

A case is now a single ``reaction.yaml`` file (plus ``profiles.yaml`` for
per-system variants and ``brief.md`` for the LLM system prompt). No Python
code per case — the harness's ``reaction_spec.py`` interpreter compiles
YAML into live ``mutate`` / ``compute_metrics`` / ``classify_single_imag``
functions at load time.

## Architecture

```
.claude/agents/autots-runner/autots/
├── autots_types.py      # dataclasses (TSState, AutoTSProfile, AutoTSParamsBase, ...)
├── profiles.py          # load_profile(profile_id, profiles_path, params_cls)
├── theozyme.py          # submit_theozyme + XYZ / imag-freq parsing
├── diagnostics.py       # diagnose(result, guess, profile, ...) + write_ts_guess
├── reporting.py         # checkpoint_record + write_summary
├── propose.py           # propose_via_llm (dataclass-schema-driven prompt + ±step fallback)
├── builder.py           # apply_residue_overrides + format_ts_guess (XYZ plumbing)
├── pdb_io.py            # generic PDB record parsing / edit
├── geometry.py          # pure 3D math helpers
├── reaction_spec.py     # YAML -> Reaction (dynamic params class + mutate / metrics / classify)
├── run.py               # `python run.py --reaction <path> --profile <id>` — generic driver
└── cases/
    ├── _template/           # copy-paste starting point
    │   ├── reaction.yaml    # DSL skeleton with TODOs
    │   ├── profiles.yaml    # per-system profile stub
    │   ├── brief.md         # LLM prompt stub
    │   └── README.md        # bootstrap recipe
    └── kemp/                # worked example — no Python, just YAML + Markdown
        ├── reaction.yaml    # Kemp elimination declaration
        ├── profiles.yaml    # 7VUU profiles
        ├── brief.md         # LLM prompt for Kemp
        └── README.md        # Kemp background + references
```

## Quickstart

```bash
conda activate llm
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/kemp/reaction.yaml \
    --profile 7VUU_core \
    --max-rounds 20 \
    --cheap-only
```

CLI flags (all owned by the harness's `run.py`):

- `--reaction <path>` — path to the reaction YAML that defines the case
- `--profile <id>` — profile from the adjacent `profiles.yaml`
- `--profiles <path>` — override profiles path (defaults to reaction sibling)
- `--brief <path>` — override brief path (defaults to reaction sibling)
- `--max-rounds N` — round budget (default 20)
- `--cheap-only` — skip the full-QM confirmation pass
- `--run-dir <path>` — override the per-run output directory

Each round writes `ts_guess.xyz`, `ts_opt_result_{cheap,full}.json`, and an
append-only `autots_log.jsonl` under `<profile.output_root>/run_<timestamp>/`.

## The reaction DSL

A `reaction.yaml` has six blocks:

| block                     | purpose                                                 |
| ------------------------- | ------------------------------------------------------- |
| `name` + `description`    | human-readable identification                           |
| `params`                  | reaction coordinates → generated dataclass fields       |
| `residues`                | named residue roles, resolved from `profile.case_config`|
| `atoms`                   | named atom references (role + PDB name or `$param`)     |
| `mutations`               | per-atom recipes: `interpolate(...)` + optional `perpendicular_bend` |
| `metrics`                 | weighted-sum displacement scores (optional)             |
| `classify_single_imag`    | hotspot + threshold rules for WRONG/AMBIG/VALID (optional)|

Supported mutation primitives:

- `place_along_bond` — `anchor + unit_vector(direction[0] → direction[1]) * distance`
- `atom: <key>` — target is the xyz of another resolved atom
- `interpolate` — linear interpolation between a reactant atom and a target, parameterized by a fraction field
- `perpendicular_bend` — extra displacement perpendicular to a reaction-coordinate axis (useful for proton-transfer bend modes)

See [`cases/kemp/reaction.yaml`](cases/kemp/reaction.yaml) for a full worked
example that reproduces the 31-atom 7VUU Kemp TS guess byte-for-byte.

## Adding a new enzyme (step-by-step)

Goal: take an enzyme + substrate pair you want to design against, land on
a working `reaction.yaml`, and start searching — all without writing
Python.

### 1. Prepare a capped cluster PDB

Use the upstream `design/transition_state_workflow.md` pipeline to produce
a reactant-like capped cluster containing all residues that should be
frozen plus the substrate/ligand and catalytic residue(s). Save the PDB
somewhere stable, e.g. `design/ts/<SYSTEM_ID>/reactant_cluster.pdb`.

### 2. Copy the template

```bash
cp -r .claude/agents/autots-runner/autots/cases/_template .claude/agents/autots-runner/autots/cases/<enzyme_id>
```

You now have four empty-ish files to fill in.

### 3. Write `reaction.yaml` (LLM-assisted)

Feed an LLM:
- A short chemistry description ("glutamate eliminates the benzisoxazole
  proton; concerted C–O cleavage and C≡N formation").
- The list of reactive atom names from your cluster PDB (grep for
  `HETATM`/substrate residue lines).
- The file `.claude/agents/autots-runner/autots/cases/kemp/reaction.yaml` as a reference.
- The DSL primitives list from `cases/_template/reaction.yaml` comments.

Ask it to produce a single `reaction.yaml` with `params` / `residues` /
`atoms` / `mutations` / `metrics` / `classify_single_imag` blocks.
Validate by running one cheap-only round (see step 5) — schema errors
surface immediately.

### 4. Write `profiles.yaml`

Copy one of the Kemp profiles as a starting skeleton, then:
- Point `cluster_path` at the PDB from step 1.
- Set `charge` and `mult` for your cluster (check with an external tool).
- Set `chain` + the residue knobs your `reaction.yaml` references (e.g.
  `ligand_resname: XXX, ligand_resseq: 101`).
- Fill `initial_guess` with reasonable starting values for every field
  your `params` block declared.
- Leave `cheap_mode` / `full_mode` at the Kemp defaults unless you
  need different QM settings.

### 5. Smoke-test with one round

```bash
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/<enzyme_id>/reaction.yaml \
    --profile <profile_id> \
    --max-rounds 1 --cheap-only \
    --run-dir /tmp/autots_smoke
```

Inspect `/tmp/autots_smoke/round_00/ts_guess.xyz` in PyMOL or VMD to
confirm your mutations actually moved the atoms you expected. Inspect
`ts_opt_result_cheap.json` to confirm the QM worker accepted the
geometry (`success: true` and `data` present).

### 6. Write `brief.md`

Describe the reaction, scoring rules, and heuristics for the LLM
proposer. Base it on `cases/kemp/brief.md` — the **scoring
interpretation** section should match your `classify_single_imag` block,
and the **heuristics** should tell the LLM which parameter to nudge when
each failure mode appears.

### 7. Launch the full search

```bash
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/<enzyme_id>/reaction.yaml \
    --profile <profile_id> \
    --max-rounds 20
```

Each run writes to `<profile.output_root>/run_<timestamp>/`.

## Run results & archive

New runs are written under the `output_root` defined in each profile —
by convention `.claude/agents/autots-runner/autots/cases/<enzyme_id>/runs/<system_id>/run_<ts>/`.

Historical runs from before the YAML-DSL refactor are parked under
[`cases/kemp/runs/archive/`](cases/kemp/runs/archive/README.md). Because
the YAML-driven mutator is byte-equivalent to the old Python version
(asserted by the regression tests), those QM outputs are still
comparable to anything you produce today — no re-run needed for
cross-run analysis.

When a case accumulates "experimental" runs that you no longer want
mixed with fresh sweeps, move them into a sibling `archive/` directory
and drop a `README.md` noting why they were set aside (see the Kemp
archive for an example).

## Harness invariants (do not break)

1. **Cluster immutable** — every round's non-reactive atoms come from the same
   cluster template; only atoms named in `mutations` are free.
2. **QM harness immutable** — the theozyme CLI args (apart from `--xyz-content`
   and cheap/full mode toggles) must not be mutated by the LLM.
3. **Checkpoint atomicity** — jsonl append happens after the subprocess returns
   and before `propose_via_llm`, so history is consistent on Ctrl-C.

## Tests

```bash
pytest tests/test_design/test_autots.py -v
```

Three golden assertions (all driven through `reaction_spec` against
Kemp's YAML): `mutate_ts_guess` reproduces the 31-atom reference geometry,
`proton_bend` only perturbs H3, and `diagnose` replays the golden
MULTI_IMAG payload. These form the regression gate.

## Dependencies

- `../theozyme-mcp` GPU worker reachable at the `theozyme_server` URL in each profile
- `gptase.models.Model` (the `llm` conda env has this via `pip install -e .`)
- `config/llm_config.json` with `claude-sonnet-4-6` available (used by the proposer)

## Related docs

- [`cases/kemp/README.md`](cases/kemp/README.md) — Kemp-specific background
