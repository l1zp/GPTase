# TS Workflow Smoke Test

This directory contains the current transition-state workflow smoke-test
artifacts derived from the prepared `7VUS` / `7VUU` complexes.

## What Was Tested

The full production TS workflow in `design/transition_state_workflow.md` starts
from a real-substrate (`5-NBI`) reactant complex. That replacement step has now
been automated at a first-pass level by
`design/scripts/replace_3ny_with_5ni.py`, so the smoke test currently validates
two stages of the pipeline:

1. TS-analogue path
   - start from `prepared_complex_minimized.pdb`
   - extract a QM cluster around ligand `3NY`
   - add boundary `CAP` hydrogens
   - convert the capped cluster to XYZ suitable for
     `theozyme pysisyphus_ts_opt --xyz-content @file.xyz`
2. Reactant-like path
   - replace `3NY` with a first-pass `5NI` / 5-NBI-like ligand in the same
     pocket pose
   - verify that the replaced complex can still be clustered and capped with
     the existing enzyme-QM helper scripts

This is still a workflow plumbing test, not a chemically final TS calculation.

## Generated Artifacts

### 7VUS

- `7VUS/ts_analogue_complex.pdb`
- `7VUS/ts_analogue_complex_cluster_chainB.pdb`
- `7VUS/ts_analogue_complex_cluster_chainB_capped.pdb`
- `7VUS/ts_analogue_cluster.xyz`
- `7VUS/reactant_complex.pdb`
- `7VUS/reactant_complex_cluster_chainB.pdb`
- `7VUS/reactant_complex_cluster_chainB_capped.pdb`
- `7VUS/product_like_complex.pdb`
- `7VUS/product_like_complex_cluster_chainB.pdb`
- `7VUS/ts_guess.xyz`

Cluster summary:

- ligand atoms: 12
- nearby protein residues: 15
- capped cluster atoms: 309

### 7VUU

- `7VUU/ts_analogue_complex.pdb`
- `7VUU/ts_analogue_complex_cluster_chainB.pdb`
- `7VUU/ts_analogue_complex_cluster_chainB_capped.pdb`
- `7VUU/ts_analogue_cluster.xyz`
- `7VUU/reactant_complex.pdb`
- `7VUU/reactant_complex_cluster_chainB.pdb`
- `7VUU/reactant_complex_cluster_chainB_capped.pdb`
- `7VUU/product_like_complex.pdb`
- `7VUU/product_like_complex_cluster_chainB.pdb`
- `7VUU/ts_guess.xyz`

Cluster summary:

- ligand atoms: 12
- nearby protein residues: 15
- capped cluster atoms: 304

## First-Pass 3NY -> 5NI Replacement

The helper script:

- `design/scripts/replace_3ny_with_5ni.py`

currently performs a geometry-preserving, best-effort replacement:

1. identify residue `3NY B 101`
2. map its heavy-atom coordinates onto a `5-NBI` graph
3. preserve the benzo-fused scaffold and nitro group orientation
4. regenerate reactant hydrogens (`H3`, `H4`, `H6`, `H7`)
5. write a new ligand residue as `5NI`

Important limitations:

- this is a pose-preserving reactant builder, not a chemically validated
  reactant optimization
- it does not yet validate that the resulting `5NI` donor-acceptor geometry is
  the best TS-search starting point

## Product-Like and TS Guess Builder

The helper script:

- `.claude/agents/autots-runner/autots/cases/kemp/build_guess.py`

currently performs a first-pass, geometry-only construction of:

- `product_like_complex.pdb`
- `ts_guess.xyz`

Current behavior:

1. find ligand proton `5NI:H3`
2. choose the nearest carboxylate oxygen on `GLU17` (currently `OE2` in both
   `7VUS` and `7VUU`)
3. build a product-like proton on the acceptor oxygen at ~1.00 Å
4. remove `H3` from the ligand in the product-like complex
5. place the TS-guess proton midway between reactant `H3` and product-like
   proton positions

This is sufficient for a TS-search input guess, but it is not yet a chemically
 validated product structure.

## Local Environment Status

The current GPTase `llm` environment can produce the PDB and XYZ inputs, but it
cannot run the final TS optimization locally.

Available locally:

- `rdkit`
- `prep_structure.py`
- `extract_cluster.py`
- `cap_cluster.py`

Missing locally:

- `theozyme`
- `gpu4pyscf`
- `docker`

The `theozyme-mcp` CLI schema for `pysisyphus_ts_opt` was verified by running
the source tree through `PYTHONPATH=../theozyme-mcp/src python -m theozyme_mcp.cli.main ... --schema`.

## Remote Pysisyphus Status

Remote CLI mode is available through:

```bash
PYTHONPATH=../theozyme-mcp/src \
python -m theozyme_mcp.cli.main \
  --server http://47.107.143.123:8080/sse \
  ...
```

Verified:

- remote `list` works
- remote `pysisyphus_ts_opt --schema` works
- remote HCN TS smoke test converged
- remote `7VUU/ts_guess.xyz` with `--use-gpu` entered the GPU4PySCF path
- remote `7VUU/core_ts_guess.xyz` can run through GPU4PySCF with a chemically
  consistent `charge=-1, mult=1`

Observed limitation:

- the full 304-atom capped cluster is too large for quick smoke testing; the
  first GPU run spent about 87 seconds preparing cycle 0 and was stopped before
  useful convergence

## Current Status

The TS workflow is now past the “connectivity / deployment” stage and into
“initial guess quality” work.

What is already working:

1. `3NY -> 5NI` replacement works and preserves the pocket pose well enough for
   downstream clustering.
2. `product_like_complex.pdb` and `ts_guess.xyz` are generated automatically.
3. Remote `theozyme-mcp` CLI submission works.
4. Remote GPU4PySCF-backed `pysisyphus_ts_opt` runs on the generated TS guess.

What has been observed numerically on the `7VUU` core reaction-region model
(`5NI + GLU17`, 31 atoms):

- Early proton-only TS guess:
  - `charge = -1`
  - `max_cycles = 5`
  - reached Hessian evaluation
  - ended with 8 imaginary frequencies
  - leading imaginary frequency about `-1208 cm^-1`
- Longer 100-cycle GPU run:
  - file: `7VUU/core_ts_opt_result_charge_m1_100cycles.json`
  - `success = false`
  - `cycles = 99`
  - `energy_hartree = -1058.63226187`
  - imaginary frequencies reduced to 4:
    - `-59.93`
    - `-29.02`
    - `-15.89`
    - `-10.90 cm^-1`

Interpretation:

- the remote GPU TS toolchain is working
- `charge = -1, mult = 1` is a chemically consistent starting point for the
  current core model
- the optimization is no longer stuck in a grossly wrong region of the PES
- but the current TS guess is still landing in a higher-order saddle /
  quasi-flat region rather than a clean first-order saddle

## Current TODO

1. Improve the TS guess rather than only increasing `max_cycles`.
   The 100-cycle run helps, but it does not eliminate the extra imaginary modes.
2. Add a constrained-scan workflow for the core model.
   The most useful coordinates to scan next are:
   - `C3-H3`
   - `H3···OE2`
   - `N2-O1`
   - `C3-N2`
3. Rebuild `core_ts_guess.xyz` from scan-derived high-energy structures instead
   of a purely geometric midpoint interpolation.
4. Once the 31-atom core model reaches a single dominant imaginary mode,
   propagate the same strategy to:
   - a slightly larger ligand + catalytic shell model
   - then the capped QM cluster
5. After obtaining a candidate first-order saddle:
   - verify the mode vector
   - run IRC or forward/backward displacement checks
   - only then consider higher-level single-point calculations

Current testing strategy:

1. validate remote TS tool with HCN
2. validate GPU path with a core reaction-region XYZ
3. improve the core TS guess until the number of imaginary modes drops to one
4. only then try larger clusters

## Current Blockers Before a Real TS Run

1. Improve the TS guess and/or add constrained scans for the core reaction
   region.
2. Validate that the guessed product-like geometry and proton-transfer path are
   chemically sensible before trusting a converged TS.
3. Once the core model shows a single dominant imaginary mode, scale back up to
   a larger cluster.

## Recommended Next Step

Use the generated:

- `design/ts/7VUS/reactant_complex.pdb`
- `design/ts/7VUU/reactant_complex.pdb`
- `design/ts/7VUS/product_like_complex.pdb`
- `design/ts/7VUU/product_like_complex.pdb`
- `design/ts/7VUS/ts_guess.xyz`
- `design/ts/7VUU/ts_guess.xyz`
- `design/ts/7VUU/core_ts_guess.xyz`
- `design/ts/7VUU/core_ts_opt_result_charge_m1_100cycles.json`

to build the next layer:

- improved core-model TS guesses
- scan-driven initial structures
- later mode inspection / imaginary frequency validation / IRC checks
