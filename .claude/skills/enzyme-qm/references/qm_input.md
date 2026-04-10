# QM Input Preparation Reference

Covers charge/multiplicity determination, coordinate conversion, software input templates,
and TS search setup.

**Primary tool: GPU4PySCF** (GPU-accelerated PySCF, Python API)
Fallback: ORCA or Gaussian (file-based)

## Table of Contents
1. [Charge & Multiplicity](#charge--multiplicity)
2. [PDB → PySCF Molecule](#pdb--pyscf-molecule)
3. [GPU4PySCF Templates](#gpu4pyscf-templates)
4. [TS Search with GPU4PySCF](#ts-search-with-gpu4pyscf)
5. [ORCA Input Template](#orca-input-template)
6. [Gaussian Input Template](#gaussian-input-template)

---

## Charge & Multiplicity

### Per-residue standard charges at physiological pH

| Residue | Charge | Notes |
|---------|--------|-------|
| ASP, GLU | −1 | Deprotonated (pKa ~4) |
| LYS, ARG | +1 | Protonated (pKa > 10) |
| HIS | 0 or +1 | Neutral (HIE/HID) if H-bond donor; +1 (HIP) if metal-coordinating |
| CYS | 0 or −1 | −1 if deprotonated or metal-coordinated; 0 if disulfide |
| TYR, SER, THR | 0 | Neutral unless deprotonated by nearby strong base |
| Ligand/TS-analogue | Varies | Determine from protonation state at simulation pH |
| Cap H atoms (CAP) | 0 | No charge contribution |

**Total cluster charge = Σ(residue charges) + ligand charge**

Multiplicity: `2S+1` — use 1 (singlet) for closed-shell; 2 (doublet) if odd-electron metal present.

### Protonation state tips
- For Kemp elimination: catalytic base (GLU/ASP) is deprotonated (charge −1) in reactant state
- At TS: base is partially protonated — model as deprotonated for reactant-state opt (relax at TS step)
- Use PROPKA or NMR pKa data if available to resolve ambiguous HIS/CYS states

---

## PDB → PySCF Molecule

GPU4PySCF takes a PySCF `Mole` object built from element symbols + Angstrom coordinates.
Extract directly from the capped cluster PDB — no intermediate XYZ file needed:

```python
def pdb_to_atoms(pdb_path: str) -> list[tuple[str, tuple]]:
    """Return [(element, (x, y, z)), ...] in Angstrom for mol.atom."""
    atoms = []
    with open(pdb_path) as f:
        for line in f:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            # PDB columns 77-78 hold the element symbol (most reliable)
            elem = line[76:78].strip()
            if not elem:
                # fallback: strip leading digits from atom name
                name = line[12:16].strip()
                elem = name.lstrip("0123456789")[0]
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
            atoms.append((elem, (x, y, z)))
    return atoms
```

---

## GPU4PySCF Templates

### Installation check
```bash
python -c "import gpu4pyscf; print(gpu4pyscf.__version__)"
# If missing:
pip install gpu4pyscf
pip install geometric   # needed for geometry optimization
```

### Single Point Energy
```python
from pyscf import gto
from gpu4pyscf.dft import rks

atoms = pdb_to_atoms("data/structures/7VUU_cluster_chainB_capped.pdb")

mol = gto.Mole()
mol.atom   = atoms
mol.basis  = "def2-TZVP"
mol.charge = <total_charge>   # see Charge & Multiplicity
mol.spin   = 0                # 2S; 0 = singlet
mol.build()

mf = rks.RKS(mol).density_fit()
mf.xc         = "B3LYP"
mf.disp       = "d3bj"        # DFT-D3(BJ) dispersion correction
mf.grids.level = 4
e = mf.kernel()
print(f"Energy: {e:.8f} Hartree")
```

### Geometry Optimization (reactant state)
```python
from pyscf.geomopt.geometric_solver import optimize

# Identify 0-based indices of cap H atoms to freeze
# (they represent fixed protein environment, not freely optimizable DOF)
cap_indices = [i for i, (elem, _) in enumerate(atoms) if elem == "H"
               # refine: check residue name == "CAP" from PDB parse if needed
               ]

params = {
    "constraints": {
        "freeze": [[i] for i in cap_indices],
    }
}

mf = rks.RKS(mol).density_fit()
mf.xc   = "B3LYP"
mf.disp = "d3bj"
mf.kernel()

mol_opt = optimize(mf, params=params)
# save optimized geometry
with open("cluster_opt.xyz", "w") as f:
    coords = mol_opt.atom_coords() * 0.529177   # Bohr → Angstrom
    f.write(f"{mol_opt.natm}\nOptimized reactant state\n")
    for i, (elem, _) in enumerate(atoms):
        f.write(f"{elem}  {coords[i,0]:.5f}  {coords[i,1]:.5f}  {coords[i,2]:.5f}\n")
```

---

## TS Search with GPU4PySCF

GPU4PySCF uses the `geometric` library for TS optimization.

### Step 1: Optimize reactant state (see above)
Verify: GLU O···H–C distance ~2.5–3.5 Å before proceeding.

### Step 2: TS guess via relaxed scan
Stretch the breaking C–H bond in 0.1 Å steps; find the energy maximum:

```python
import numpy as np

# Indices of the breaking C–H bond (0-based, identify by inspecting cluster PDB)
IDX_C = <carbon_index>
IDX_H = <hydrogen_index>

energies = []
for r_CH in np.arange(1.1, 1.85, 0.1):
    params_scan = {
        "constraints": {
            "distance": [[IDX_C, IDX_H, float(r_CH)]],
            "freeze":   [[i] for i in cap_indices],
        }
    }
    mol_scan = optimize(mf, params=params_scan)
    energies.append((r_CH, mf.e_tot))
    print(f"r(C-H)={r_CH:.1f}  E={mf.e_tot:.6f} Ha")

# Pick geometry at energy maximum as TS guess
```

### Step 3: TS Optimization
```python
params_ts = {
    "transition": True,    # geometric saddle-point search
    "constraints": {
        "freeze": [[i] for i in cap_indices],
    },
}
mol_ts = optimize(mf, params=params_ts)
```

### Step 4: Frequency Analysis — verify one imaginary mode
```python
from gpu4pyscf.prop.freq import harmonic_analysis

mf_ts = rks.RKS(mol_ts).density_fit()
mf_ts.xc = "B3LYP"
mf_ts.disp = "d3bj"
mf_ts.kernel()

freq, modes, _ = harmonic_analysis(mf_ts)
print("Lowest frequencies (cm⁻¹):", freq[:5])
# Valid TS: exactly ONE negative frequency, motion along C-H / O-H coordinate
```

### Step 5: IRC
`geometric` does not support IRC natively. Options:
- **Manual displacement**: displace geometry ±0.1 along imaginary mode vector, re-optimize each side
- **ORCA/Gaussian IRC**: use TS geometry as input for `! IRC` / `IRC=(CalcFC)`

### Kemp elimination geometry targets at TS

| Parameter | Typical value |
|-----------|--------------|
| C–H (breaking) | 1.3–1.5 Å |
| O···H (base–substrate) | 1.2–1.4 Å |
| C–O–N angle | ~150–165° |
| Imaginary frequency | −400 to −1200 cm⁻¹ |

---

## ORCA Input Template (fallback)

```
! B3LYP D3BJ def2-TZVP RIJCOSX def2/J TightSCF Opt

%pal
  nprocs 8
end

%geom
  MaxIter 500
end

* xyzfile <charge> <mult> cluster_capped.xyz
```

| Task | Keywords to add |
|------|----------------|
| TS optimization | `OptTS NumFreq`, add `%geom TS_Mode { B idx1 idx2 } Calc_Hess true end` |
| IRC | `! IRC` (use def2-SVP for speed) |
| Frequency only | `Freq` |

---

## Gaussian Input Template (fallback)

```
%nprocshared=8
%mem=16GB
%chk=cluster.chk
#P B3LYP/6-311+G(d,p) Opt=(MaxCycles=100) EmpiricalDispersion=GD3BJ

Cluster model — <enzyme> active site

<charge> <mult>
<xyz coordinates>

```
*(blank line required at end)*

For TS: `Opt=(TS,CalcFC,NoEigentest)` + `Freq`
For IRC: `IRC=(MaxPoints=30,StepSize=10,CalcFC)`
For frozen caps: `Opt=ModRedundant`, then append `X <serial>  F` lines.
