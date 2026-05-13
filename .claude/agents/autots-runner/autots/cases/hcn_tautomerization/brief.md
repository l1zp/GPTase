# HCN Tautomerization Reaction Brief

You are searching for the transition state of the gas-phase 1,2-hydrogen migration between HCN (hydrocyanic acid) and HNC (hydrogen isocyanide):
- **Reactant**: Linear H-C≡N, where H is covalently bonded to C (H-C distance ~1.07 Å, C≡N ~1.16 Å)
- **Product**: Linear C≡N-H, where H is covalently bonded to N (N-H distance ~1.00 Å, C≡N ~1.17 Å)
- **Transition state**: Triangular non-linear geometry, where the H atom is partially bonded to both C and N, off the C-N axis. Ideal TS geometry has H-C ~1.18 Å, H-N ~1.40 Å, and angle H-C-N ~73 degrees.

## Reaction coordinate guide
The parameter `h_migration_frac` ranges from 0.0 (H fully bonded to C, pure HCN) to 1.0 (H fully bonded to N, pure HNC). The correct transition state lies near `h_migration_frac=0.5`, but the H atom will have a perpendicular offset from the C-N axis, not just be linearly interpolated between the two linear endpoints.

## Success criteria
A valid transition state will have:
1. A single imaginary frequency > 500 cm⁻¹
2. The dominant motion in the imaginary frequency mode involves the migrating H atom moving between C and N
3. The H atom is not collinear with C and N (triangular geometry)

## Common failure modes to avoid
- Proposing linear geometries (all three atoms collinear) — these will not have the correct TS mode
- Proposing H positions too close to either C or N (these are just the reactant or product minima, not TS)
