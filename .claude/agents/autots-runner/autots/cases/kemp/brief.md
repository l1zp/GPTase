# autoTS brief

Goal: find a Kemp elimination transition-state candidate for the 7VUU core model.

System constraints:
- You may change only `TSGuessParams`.
- Do not alter the cluster definition, charge, multiplicity, method family, or harness flags.
- Fractions must stay in `[0.0, 1.0]`.
- Prefer chemically interpretable moves over random exploration.
- The `7VUU_core` profile submits only the 31-atom `5NI + GLU17` core, not the full 304-atom capped cluster.

Chemical context:
- The reactive model is the 31-atom `5NI + GLU17` core derived from 7VUU.
- `GLU17:OE1/OE2` is the proton acceptor.
- `5NI:H3` transfers from `C3` toward the chosen glutamate oxygen.
- `proton_bend` bends the transferring `H3` off the idealized `C3···OE` line inside
  the local reactive plane; use it to explore `OE···H···C3` geometry when the
  midpoint search stalls.
- `5NI:O1-C7A` opening should grow as the TS guess approaches product character.
- `5NI:N2-C3` should elongate toward nitrile-like geometry, but not dominate the move.

Important known facts:
- `charge = -1`, `mult = 1` are required for this core model.
- The current hand-built midpoint guess can reach GPU4PySCF and lower the number of imaginary modes, but it still lands in multi-imag territory after 100 cycles.
- The bottleneck is guess quality, not the QM backend.

Scoring interpretation:
- `VALID` means exactly one imaginary frequency and the main displacement remains on the reaction coordinate.
- `SINGLE_IMAG_WRONG` means the dominant motion moved away from `H3/OE1/OE2/C3/O1`.
- `SINGLE_IMAG_AMBIG` means the move stays near the reactive region, but H-transfer and ring opening are not coupled strongly enough.
- Within the same state, lower energy is better.

Heuristics:
- If proton transfer is too early, reduce `h_transfer_frac`.
- If the ring remains too reactant-like, increase `ring_opening_frac`.
- If nitrile formation dominates the motion, back off `n_elongation_frac`.
- If the search stalls in persistent multi-imag states, try small positive or negative
  `proton_bend` values before making large scalar changes elsewhere.
- If OE1 stalls, try OE2, and vice versa.
- Use perturbation sparingly; it is for escaping repeated guesses, not for large geometry edits.

Output contract:
- Return JSON only.
- Do not add prose, markdown fences, or explanations.
