# HCN ⇌ HNC Tautomerization — autoTS smoke test

## Reaction

Gas-phase 1,2-hydrogen migration in a 3-atom system:

```
  H—C≡N           H···C···N           C≡N—H
  (HCN)           (TS, triangular)    (HNC)
```

- **Reactant (HCN)**: linear, C–H ≈ 1.07 Å, C≡N ≈ 1.16 Å
- **Product (HNC)**: linear, N–H ≈ 1.00 Å, C≡N ≈ 1.17 Å
- **Transition state**: triangular (non-linear), H equidistant-ish from C and N
  - H–C ≈ 1.18 Å
  - H–N ≈ 1.40 Å
  - ∠HCN ≈ 73° (H off the C–N axis)
  - Single imaginary frequency ≈ −1200 cm⁻¹ (b3lyp/6-31g)

## Why this case

This is the textbook smallest-possible TS test:
- 3 atoms total → QM converges in seconds
- 1D reaction coordinate (H migration angle/position) → LLM proposer should
  converge in a few rounds
- TS geometry and imag-freq are well-documented in the literature

## Autots case design — specific guidance for the YAML author

### Participants (single residue, degenerate case)

There is no protein, no catalytic residue, no cluster. The whole molecule IS the "ligand residue". PDB uses placeholders:
- `chain: A`
- `resname: HCN`
- `resseq: 1`
- Atom names: `C`, `N`, `H`

### Reaction coordinate — 1D is sufficient

Recommend a single float parameter:

```yaml
params:
  h_migration_frac: { type: float, range: [0.0, 1.0], default: 0.5 }
  perturb_seed:     { type: int,                       default: null }
  perturb_sigma:    { type: float, range: [0.0, 0.1],  default: 0.0 }
```

Semantics: `h_migration_frac = 0` means H sits near C (HCN); `= 1` means H sits near N (HNC); `= 0.5` is a symmetric midpoint guess.

### Mutation recipe — place H on an arc between C and N

The H atom's position should move along a curved path from "near C, off-axis" to "near N, off-axis". The simplest DSL form:

```yaml
atoms:
  H_mig:     { residue: ligand, name: H }
  C_anchor:  { residue: ligand, name: C }
  N_anchor:  { residue: ligand, name: N }

mutations:
  H:
    interpolate:
      from: H_mig                             # atom key string; H's current PDB position
      to:
        place_along_bond:
          anchor: N_anchor
          direction: [C_anchor, N_anchor]     # unit vec (N - C); past N on the far side
          distance: 1.00                      # HNC-like: H at 1.00 Å past N
      fraction: $h_migration_frac
    perpendicular_bend:
      axis: [C_anchor, N_anchor]
      plane_hint: [C_anchor, H_mig]           # requires H off-axis in PDB (see note below)
      fallback_plane_hint: [N_anchor, H_mig]
      magnitude: $proton_bend
```

**Collinearity note**: HCN's equilibrium geometry is linear (H-C-N). `perpendicular_bend` computes `normal = cross(axis, plane_hint)`; if all three points lie on a line, `normal → 0` and the bend becomes a no-op. The input PDB must give `H` a tiny off-axis offset (e.g. `y = 0.010 Å`) to break collinearity. This has negligible effect on the QM energy (~0.05 kcal/mol) but stabilizes the bend direction. Also add a `proton_bend: { type: float, range: [-1.5, 1.5], default: 0.8 }` parameter in `params:` to drive the bend magnitude — H purely interpolated along the C-N line would pass through C without ever forming a triangle.

### QM settings

- `charge: 0`
- `mult: 1` (closed-shell singlet)
- Recommended: `xc=b3lyp`, `basis=6-31g` for both cheap and full modes
- The molecule is tiny — `max_cycles: 20` cheap / `50` full is plenty

### Success criteria (`classify_single_imag`)

- `primary_hotspot_atom_names: ["H", "C", "N"]` — dominant imaginary mode must move one of these atoms.
- `valid_when`: **each entry's key must be a metric name defined in the `metrics:` block; value is a string comparison expression**. For HCN the simplest `metrics` block defines `reaction_coord_weight` over `[H_mig, C_anchor, N_anchor]`, so:
  ```yaml
  metrics:
    reaction_coord_weight:
      atoms: [H_mig, C_anchor, N_anchor]
      normalize_by: total_displacement
  classify_single_imag:
    primary_hotspot_atom_names: ["H", "C", "N"]
    valid_when:
      reaction_coord_weight: ">= 0.5"
  ```
  Autots already filters CRASHED / NOT_CONVERGED / MULTI_IMAG upstream. `valid_when` only distinguishes SINGLE_IMAG_AMBIG vs VALID. Never write dict forms like `{gt: 500}` — only strings like `">= 0.5"`.

### Profile knobs

```yaml
profiles:
  hcn_tautomerization_core:
    cluster_path: <agent receives as input>
    output_root: <agent decides>
    chain: A
    ligand_resname: HCN
    ligand_resseq: 1
    charge: 0
    mult: 1
    theozyme_server: http://47.107.143.123:8080/sse
    theozyme_pythonpath: /Users/ryanxu/CodeBase/theozyme-mcp/src
    # include_residues is optional; if used, each entry must be a dict with
    # `chain`, `resname`, `resseq` keys — NOT `[A, 1]` list form. For HCN
    # with only one residue, omit the block entirely.
    cheap_mode:
      method: dft         # NOT 'b3lyp' — b3lyp is the xc, not the method
      xc: b3lyp
      basis: 6-31g
      max_cycles: 20
      timeout_seconds: 180
      hessian_init: calc  # required for small molecules (lindh crashes rs-prfo)
      hessian_recalc: 2
    full_mode:
      method: dft
      xc: b3lyp
      basis: 6-31g
      max_cycles: 50
      timeout_seconds: 360
      hessian_init: calc
      hessian_recalc: 2
    initial_guess:
      h_migration_frac: 0.4
      proton_bend: 1.0
      perturb_seed: null
      perturb_sigma: 0.0
```

## Success target for this smoke test

A VALID round within `max_rounds: 3` would be ideal but not required. Even producing:
- A `round_00/ts_guess.xyz` with 3 atoms in a triangular-ish geometry
- A `ts_opt_result_cheap.json` with a parseable imaginary frequency list
- A non-empty `summary.md`

...is enough to confirm the full agent-to-worker pipeline is wired correctly.
