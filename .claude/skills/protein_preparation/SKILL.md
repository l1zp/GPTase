---
name: protein_preparation
description: |
  Prepare protein-ligand complexes for downstream computation (QM, MD,
  docking). Protonates proteins, fixes ligand chemistry, and optionally
  energy-minimizes. Accepts RCSB PDB IDs, local PDB/CIF files, or
  AF3-predicted mmCIF complexes.

  ALWAYS use this skill when the user wants to prepare, protonate, add
  hydrogens to, or minimize a protein structure -- even if they don't
  say "protein_preparation" explicitly. This includes requests like
  "prepare 7VUU", "protonate this complex", "add hydrogens", "get this
  structure ready for QM", "batch prepare those CIF files", "clean up
  the AF3 output", or Chinese equivalents like "prepare 一下", "加氢",
  "处理一下这个结构", "跑一下 pdb2pqr". Also trigger when the user
  references a structure from earlier in the conversation and asks to
  prepare or protonate it ("把前面那个结构 prepare 一下").

  Also trigger when the user mentions pdb2pqr, propka, reduce (the
  hydrogen-placement tool), CCD ligand lookup, OpenMM minimization,
  or prep_structure.py -- this skill owns the full preparation pipeline.

  DO NOT use for: QM cluster extraction, H-capping, ORCA/Gaussian input,
  TS search, docking, or pure database lookups. Once a prepared complex
  exists and the user wants downstream QM work, route to enzyme-qm.
---

# protein_preparation

Two entry points depending on input type:

| Input | Script | Output |
|-------|--------|--------|
| RCSB PDB ID | `design/scripts/prepare_pdb.py` | `design/prepared/<PDB_ID>/` |
| Local CIF/PDB (e.g. AF3) | `design/scripts/prep_structure.py` + manifest YAML | user-specified `--outdir` |
| Batch AF3 CIF | project-level `batch_prepare.py` | `complex/prepared/<stem>/` |

## One-shot entry

For 90% of requests, run exactly this and report the printed summary:

```bash
conda run -n llm python design/scripts/prepare_pdb.py --pdb-id <PDB_ID>
```

The driver prints one line per ligand and a minimization summary at the
end. If the exit code is 0 and `manual_review.json` is `[]`, the run is
clean — surface the summary to the user; don't re-read every file.

Optional flags (use only when the user signals intent):

| Flag | Use when |
|------|----------|
| `--overwrite-config` | User changed their mind about chain / ligand / protonation and wants the manifest regenerated from scratch. |
| `--overwrite-output` | User wants a clean re-run (e.g. after editing the manifest), or a prior run left a stale `prepared/<PDB_ID>/`. |
| `--outdir <path>` | User wants outputs elsewhere (smoke tests, scratch directory). Rarely needed. |

Why a tiny CLI rather than instructing Claude to compose the sub-steps:
the chain-selection heuristic, CCD resolution, OpenMM minimization, and
manual-review reporting are all interdependent and easy to get subtly
wrong. The script encodes the known-good sequence so each invocation is
reproducible.

## Pre-flight checks the driver already handles

The script is defensive by default. You normally don't need to do these
manually, but they're useful to mention when something looks wrong:

- **Non-existent PDB ID** — RCSB returns HTTP 404; the driver raises a
  `SystemExit` with the code. Ask the user to double-check the ID.
- **Multiple ligands on the picked chain** — all non-water / non-ion
  HETATM residues are prepared. If the user only wants one, they should
  edit the YAML to drop the others and re-run with `--overwrite-output`.
- **No ligand at all** — the driver falls back to the first chain with
  standard amino acids and produces an empty ligand list; the pipeline
  still runs and emits a protonated, minimized apo complex.
- **Multi-chain entries** — the driver selects one chain (lowest mean
  ligand B-factor). For biologically relevant dimers / oligomers the
  user needs to expand `chains:` in the YAML manually, because the
  minimization + normalization pipeline currently operates on the
  chains you list.

## Reporting back to the user

After a run, read `design/prepared/<PDB_ID>/prep_report.json` and surface:

1. **`ligand_preparation.ligands[*]`** — one entry per ligand.
   `chemistry_source` is normally `rcsb_ccd`; `manifest` means the user
   supplied an explicit SMILES override. `formal_charge` /
   `explicit_hydrogens` let you sanity-check the molecule.
2. **`minimization`** — `status`, `rmsd` (should be small, < ~1 Å for a
   good starting structure), `energy_kj_mol` (negative; getting more
   negative when the user reruns after chemistry fixes is a good sign).
3. **`normalization.active_site_residues`** — useful to echo back when
   the downstream task is QM or docking; these are the residues within
   `active_site_cutoff` of the ligand.
4. **`manual_review.json`** — always open it. `[]` is clean; any entry
   is a blocker for downstream work. Typical issues include chain
   breaks inside the active site, missing CCD entries for exotic
   ligands, and pdb2pqr template failures on modified residues.

If the pipeline exits non-zero, `prep_report.json` still exists and has
`status: "failed"` or `status: "manual_review_required"` with a root-cause
message. Quote that message to the user rather than guessing.

## Worked example: 7VUU

Input: `--pdb-id 7VUU` (Kemp eliminase AlleyCat10, holo with 3NY = 5-nitro-1H-benzotriazole).

Driver's printed summary on a clean run:

```
[prepare_pdb] PDB ID: 7VUU
[prepare_pdb] structure: design/structures/7VUU.pdb
[prepare_pdb] manifest written: design/config/7VUU.yaml
[prepare_pdb]   chains=['B'] ligands=['3NY']
[prepare_pdb] ligand B:101:3NY: source=rcsb_ccd formal_charge=0 H=4
[prepare_pdb] minimization: status=completed rmsd=0.366
[prepare_pdb] done. outputs in design/prepared/7VUU
```

Expected artifacts:

- `design/prepared/7VUU/prepared_complex_minimized.pdb` — the minimized
  complex; passes into the enzyme-qm skill.
- `ligands_prepared.sdf` — aromatic benzotriazole, 16 atoms / 17 bonds,
  `M CHG` records on the zwitterionic NO₂ group.
- `ccd_cache/3NY.json` — reusable on subsequent runs and for 7VUS (same
  ligand).

## Overriding the autogenerated manifest

The autogen intentionally writes a minimal YAML. If the user needs any
of the following, edit `design/config/<PDB_ID>.yaml` and re-run with
`--overwrite-output`:

- **Force a chain**: replace the `chains:` list.
- **Drop / keep specific waters or metals**: populate the `keep:` lists
  in `water_policy` / `metal_policy`, or switch `mode: keep` and list
  residue IDs.
- **Fix protonation state**: add entries under
  `protein_protonation_overrides` (`"B:50": {state: HIE}`, etc.). These
  take precedence over pdb2pqr / propka suggestions.
- **Override ligand chemistry**: add an entry under `ligand_states`
  with an explicit `smiles` (e.g. to select a non-default protomer or
  tautomer). Hand-written SMILES always beat the CCD value; leave
  everything else blank to inherit the CCD defaults.
- **Skip the OpenMM minimization**: set `run_minimization: false` for
  fast iteration. The protonation and ligand chemistry steps still
  run, so `prepared_complex.pdb` is still produced.

## Preparing local AF3 complexes

When the input is a local AF3 mmCIF (not an RCSB PDB ID), use
`prep_structure.py` directly with a hand-written manifest.

### Single file

```bash
conda run -n llm python design/scripts/prep_structure.py \
  --input <path/to/complex.cif> \
  --config <path/to/manifest.yaml> \
  --outdir <output_dir>
```

The manifest must provide explicit SMILES via `ligand_states` because
AF3 ligand resnames (e.g. `LIG_B`) are not in the RCSB CCD.

### Batch AF3 complexes

For projects with many AF3 CIF files (e.g. design enzyme variants),
use the project-level `batch_prepare.py`. It handles:

- **Resname overflow**: AF3 uses `LIG_B` (5 chars); PDB format allows 3.
  The script converts CIF -> PDB via gemmi, renaming to `LIG`.
- **Fallback strategy**: tries with OpenMM minimization first; if that
  fails, accepts `prepared_complex.pdb` (protonated, un-minimized) which
  is sufficient for QM cluster extraction.
- **Resume-safe**: skips directories that already have output.

```bash
conda run -n llm python <project_dir>/batch_prepare.py
```

### AF3-specific known issues

| Issue | Cause | Handling |
|-------|-------|----------|
| All residues parsed as HETATM | AF3 CIF sets `het_flag` on standard residues | Fixed in `parse_mmcif_with_gemmi`: forces `ATOM` for standard amino acids |
| reduce exits non-zero | reduce warns on AF3 formatting but still outputs valid PDB | Fixed in `run_reduce`: accepts output if ATOM lines present |
| OpenMM minimization fails on some scaffolds | AF3 geometry edge cases | Fallback to `prepared_complex.pdb` (no minimization) |
| RDKit "More than one matching pattern" | Ligand SMILES has symmetry | Warning only; bond assignment still succeeds |

## Handoff to downstream skills

- **enzyme-qm** — takes `prepared_complex_minimized.pdb` (or
  `prepared_complex.pdb` for un-minimized AF3 cases) as input and
  extracts a capped active-site cluster. Route there for cluster /
  cap / QM input / TS search.
- **ad-hoc inspection** — the prepared complex is a standard PDB with
  ligand CONECT bonds written out; PyMOL / ChimeraX / VMD all load it
  directly.

## Environment and caches

- Conda env: `llm`. Always invoke via `conda run -n llm ...` so the
  script sees the project's rdkit / openmm / pdb2pqr / propka / reduce
  / gemmi installations.
- `design/structures/<PDB_ID>.pdb` is cached; re-runs skip the RCSB
  download.
- `design/ccd_cache/<RESNAME>.json` is cached; CCD lookups for the same
  ligand across different PDB entries are instant after the first hit.
- First-time runs on a ligand not yet in `ccd_cache/` need network
  access to `data.rcsb.org`. Without network, hand-write `smiles` in
  the YAML as the override.
