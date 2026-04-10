---
name: enzyme-qm
description: |
  QM-based computational enzyme analysis: structure selection, active-site cluster
  extraction, H-capping, and QM input preparation (ORCA/Gaussian), including TS search.
  ALWAYS use this skill when the user wants to: extract a QM cluster from a protein
  structure, cap truncated residues with link atoms, prepare ORCA or Gaussian input files,
  run a transition state search on an enzyme active site, or do theozyme / QM/MM analysis.

  Trigger on: QM cluster, theozyme, active site extraction, capping, link atom, H-cap,
  TS search, transition state, imaginary frequency, IRC, ORCA, Gaussian, QM/MM boundary,
  enzyme QM, cluster model, PDB to QM, active site QM.
---

# Enzyme QM Workflow

End-to-end pipeline: PDB structure → active-site cluster → capped QM model → QM input.

## Before Starting: Structure Selection

Always verify that the structure contains the substrate or a TS analogue (holo).
Read [references/structure_selection.md](references/structure_selection.md) for:
- holo vs. apo decision tree
- RCSB search and entry inspection commands
- chain B-factor selection
- docking fallback (AutoDock Vina) when no holo exists

## Step 1: Download PDB

```bash
mkdir -p data/structures
curl -s -o data/structures/{PDB_ID}.pdb "https://files.rcsb.org/download/{PDB_ID}.pdb"

# Quick sanity check
grep "^HETATM" data/structures/{PDB_ID}.pdb | awk '{print $4}' | sort -u
grep "RESOLUTION" data/structures/{PDB_ID}.pdb | head -1
```

## Step 2: Select Best Chain

When multiple chains are present, pick the one with the lowest ligand B-factor:

```bash
grep "^HETATM" {PDB}.pdb | grep " {LIG} " | awk '{
  chain=$5; bf=substr($0,61,6)+0
  sum[chain]+=bf; cnt[chain]++
} END {for(c in sum) printf "chain %s avg_bfactor=%.1f\n", c, sum[c]/cnt[c]}' | sort -t= -k2 -n
```

## Step 3: Extract Active-Site Cluster

Run the bundled script — no biopython required:

```bash
python .claude/skills/enzyme-qm/scripts/extract_cluster.py \
    data/structures/{PDB_ID}.pdb \
    {CHAIN} \
    {LIGAND_CODE} \
    6.0          # cutoff in Å (5=minimal, 6=standard, 8=extended)
```

Output: `data/structures/{PDB_ID}_cluster_chain{CHAIN}.pdb`

**Cutoff guidance:**
| Å | When to use |
|---|-------------|
| 5 | Only direct contacts — minimal model |
| 6 | First shell — **default** |
| 8 | Include second-shell polar residues |

## Step 4: H-Capping

Cap all truncated backbone bonds with H link atoms:

```bash
python .claude/skills/enzyme-qm/scripts/cap_cluster.py \
    data/structures/{PDB_ID}_cluster_chain{CHAIN}.pdb \
    {CHAIN}
```

Output: `data/structures/{PDB_ID}_cluster_chain{CHAIN}_capped.pdb`

The script adds:
- **N-cap H**: at each N where the previous residue is absent
- **C-cap H**: at each C where the next residue is absent (sp2-aware geometry)

Cap positions are approximate initial guesses; QM geometry optimization relaxes them.

## Step 5: QM Input Preparation & TS Search

**Primary tool: GPU4PySCF** (GPU-accelerated PySCF, Python API + `geometric` optimizer)
Fallback: ORCA or Gaussian

Read [references/qm_input.md](references/qm_input.md) for:
- Charge/multiplicity determination (residue charge table, protonation tips)
- `pdb_to_atoms()` helper — load capped PDB directly into PySCF `Mole`
- GPU4PySCF single point, geometry optimization, and TS search templates
- TS workflow: reactant opt → relaxed C–H scan → `transition=True` OptTS → frequency check → IRC
- ORCA/Gaussian templates as fallback

## Worked Example: AlleyCat10 (7VUU, Kemp Eliminase)

```
Reaction  : 5-nitrobenzisoxazole → 2-cyano-4-nitrophenoxide
TS analogue: 5-NBT (PDB code 3NY), chain B (B-factor 12.9 Å²)
Cutoff    : 6 Å → 17 residues, 160 atoms
Capping   : 24 H atoms added → 184 atoms total
Output    : data/structures/7VUU_cluster_chainB_capped.pdb
```

Key active-site residues:
| Residue | Role |
|---------|------|
| GLU17 | Catalytic base (proton acceptor) |
| ARG37, ARG51, ARG69 | Stabilize TS negative charge |
| PHE66 | Hydrophobic / π-stacking |
| HIS50 | H-bond network |
