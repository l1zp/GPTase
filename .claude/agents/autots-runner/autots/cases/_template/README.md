# Template case

A copy-paste skeleton for a YAML-only autoTS reaction. **No Python code** —
the harness interpreter (`.claude/agents/autots-runner/autots/reaction_spec.py`) reads the YAML
and drives the search.

## Files

| file               | purpose                                                   |
| ------------------ | --------------------------------------------------------- |
| `reaction.yaml`    | params + atom roles + mutation recipes + scoring          |
| `profiles.yaml`    | one profile per system (cluster PDB, QM settings, seed)   |
| `brief.md`         | LLM system prompt describing the reaction                 |

## Bootstrapping your own case

```bash
cp -r .claude/agents/autots-runner/autots/cases/_template .claude/agents/autots-runner/autots/cases/mycase
```

Then edit:

1. **`reaction.yaml`** — the heart of the case. Declare your reaction
   coordinates under `params`, your residue roles under `residues`, the
   atoms you need to reference under `atoms`, and the mutation recipes
   under `mutations`. `metrics` and `classify_single_imag` are optional
   but strongly recommended.
2. **`profiles.yaml`** — point `cluster_path` at your capped cluster PDB,
   set `charge` / `mult`, seed `initial_guess` with values matching your
   params dataclass, and fill in the residue knobs (e.g.
   `ligand_resname`, `base_resname`) that your `reaction.yaml`
   references as `$vars`.
3. **`brief.md`** — reaction background + "what makes a good TS" rules.
   The LLM sees this as its system prompt every round.

## Running

```bash
python .claude/agents/autots-runner/autots/run.py \
    --reaction .claude/agents/autots-runner/autots/cases/mycase/reaction.yaml \
    --profile example --max-rounds 10
```

When `--profiles` and `--brief` are omitted, the harness looks for them
next to your `reaction.yaml`.

## Letting an LLM write `reaction.yaml`

The DSL is intentionally narrow so an LLM can generate it reliably from a
short natural-language description plus a cluster PDB snippet. Feed:

- Your reaction description (bonds forming/breaking, residues involved,
  product-like geometry targets with approximate bond lengths).
- The schema documentation (this directory plus `cases/kemp/reaction.yaml`
  as a full worked example).

Ask the LLM to produce a single `reaction.yaml`. Validate by running
`python .claude/agents/autots-runner/autots/run.py --reaction ... --profile ... --max-rounds 1
--cheap-only` — any schema errors surface immediately.

## Reference

See `cases/kemp/reaction.yaml` for a real, tested example (Kemp
elimination on the 7VUU core).
