---
name: protein_preparation
description: |
  Turn a bare PDB ID into a fully prepared, protonated, energy-minimized
  protein-ligand complex via a single driver script
  (design/scripts/prepare_pdb.py). Downloads the PDB from RCSB, auto-picks
  the best chain and its non-water / non-ion ligand(s), resolves ligand
  chemistry from the RCSB PDB CCD (no hand-written SMILES needed), runs
  pdb2pqr + propka + reduce for protein protonation, recombines the
  complex, and performs a restrained OpenMM minimization. Artifacts land
  in design/prepared/<PDB_ID>/.

  ALWAYS trigger this skill whenever a user request names a PDB ID (or
  refers to one from earlier turns, e.g. "that pdb", "前面那个结构",
  "same one as 7VUU") AND expresses intent to prepare / clean / prep /
  protonate / hydrogenate / minimize / "get it ready for" any downstream
  use (QM, docking, MD, cluster extraction, simulation). This is the
  canonical PDB → prepared complex entry point for the repo.

  ALSO trigger when the user says they want to "run the standard pipeline",
  "the same flow we did before", "按那套流程", "按前面那套处理",
  "按我们之前的流程", or references prep_structure.py / PrepWizard-style
  prep. Mentions of ligand chemistry, CCD lookup, pdb2pqr, propka, OpenMM
  minimization, or SMILES resolution *inside a PDB-preparation request*
  do NOT route to a different skill — this one handles all of that
  internally. Route to this skill for the whole request.

  Trigger phrases (non-exhaustive): "prepare 7VUU", "prep this PDB",
  "prepare 3eml like we did 7vuu", "protonate complex for <PDB>",
  "run prep on <PDB>", "generate prepared_complex", "clean up <PDB> for
  QM", "get <PDB> simulation-ready", "hydrogenate <PDB>",
  "minimize this pdb complex", "准备 <PDB>", "处理 <PDB>",
  "对 <PDB> prepare 一下", "给 <PDB> 跑 protein preparation",
  "按前面那套流程处理 <PDB>", "按之前的 prep 流程跑一下 <PDB>".

  Do NOT use this skill for: active-site cluster extraction, QM link-atom
  H-capping, ORCA / Gaussian / PySCF input authoring, TS search,
  IRC, docking (AutoDock Vina), or pure CCD / PubChem / SMILES lookups
  that don't involve preparing a protein-ligand complex. When the user
  already has a prepared complex and asks for downstream QM / cluster /
  TS work, route to the enzyme-qm skill instead.
---

# protein_preparation

Single-entry preparation driver. Input: a PDB ID. Output:
`design/prepared/<PDB_ID>/prepared_complex_minimized.pdb` plus a
machine-readable `prep_report.json`.

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

## Handoff to downstream skills

- **enzyme-qm** — takes `design/prepared/<PDB_ID>/prepared_complex_minimized.pdb`
  as its PDB input and extracts a capped active-site cluster. If the
  user's next ask is "cluster / cap / QM input / TS search", route
  there.
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
