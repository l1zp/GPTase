# Structure Selection Reference

How to find and validate the right PDB structure before extracting a QM cluster.

## Decision Tree

```
Does a holo structure exist (ligand/substrate/TS-analogue bound)?
  YES → Use it directly. Best geometry, no docking needed.
  NO  → Is the active site pocket large enough to dock into?
          YES → Run AutoDock Vina, then extract cluster from docked pose.
          NO  → Search for a mutant or related enzyme with holo structure.
                If nothing: use apo + manual placement as last resort.
```

## Finding Holo Structures on RCSB

### Full-text search
```
https://search.rcsb.org/rcsbsearch/v2/query?json={"query":{"type":"terminal","service":"full_text","parameters":{"value":"<enzyme name> <substrate>"}},"return_type":"entry","request_options":{"paginate":{"start":0,"rows":10}}}
```

### Inspect entry for ligands
```
https://data.rcsb.org/rest/v1/core/entry/{PDB_ID}
```
Check `nonpolymer_entities` — if absent or only crystallization agents, it is apo.

### Identify ligand type from HETATM records
```bash
grep "^HETATM" structure.pdb | awk '{print $4}' | sort -u
```

**Crystallization agents to ignore** (not substrate):
`HOH`, `SO4`, `PO4`, `GOL`, `MPD`, `PEG`, `EDO`, `ACT`, `CL`, `NA`, `MG`, `CA`, `ZN`

**Worth investigating**: anything else — especially 3-4 letter codes that look like small organics.

## Selecting the Best Chain

When the asymmetric unit has multiple copies (chains A, B, C, D…):

```bash
grep "^HETATM" structure.pdb | grep " <LIG> " | awk '{
  chain=$5; bf=substr($0,61,6)+0
  sum[chain]+=bf; cnt[chain]++
} END {for(c in sum) printf "chain %s avg_bfactor=%.1f\n", c, sum[c]/cnt[c]}' | sort -t= -k2 -n
```

Pick the chain with the **lowest average B-factor** for the ligand — lower = more ordered = more reliable geometry for QM.

## Verifying Structure Quality

```bash
# Resolution
grep "RESOLUTION" structure.pdb | head -2

# R-factors
grep "R VALUE" structure.pdb | head -5
```

Typical thresholds for QM cluster work:
- Resolution < 2.5 Å: good
- Resolution < 2.0 Å: excellent, H-atom positions more reliable
- R_work < 0.22, R_free < 0.27: acceptable

## Special Cases

### Metalloenzymes
If the active site contains Fe, Zn, Cu, Mn: the ligand often coordinates the metal.
- Check for metal-coordinating residues (HIS, CYS, ASP, GLU within 2.5 Å of metal)
- Include the metal and its first coordination shell in the cluster
- For Mb variants: heme Fe is structural background; Kemp catalysis is by protein residues, not Fe

### No holo structure available — docking fallback
If using AutoDock Vina:
1. Remove crystallographic waters and non-substrate HETATM records
2. Remove any metal-coordinated small molecules that block the pocket (e.g., imidazole in 7VUC)
3. Define search box centered on the known/predicted binding pocket
4. Use flexible docking if key catalytic residues need to adjust
5. Validate docked pose against known catalytic geometry (distance to base, orientation of leaving group)

## Worked Case: Kemp Eliminase (Bhattacharya 2022, Nature 610)

| PDB | Type | Verdict |
|-----|------|---------|
| `6CF0` | Mb(H64V) apo | Pocket too small — cannot dock 5-NBI |
| `7VUC` | FerrElCat apo | Docking feasible (paper-validated); remove imidazole first |
| `7VUS` | AlleyCat9 + 5-NBT | **Holo — use directly** |
| `7VUU` | AlleyCat10 + 5-NBT | **Holo — use directly** (chain B, B-factor 12.9 Å²) |

5-NBT (PDB code `3NY`) is the transition-state analogue for Kemp elimination.
