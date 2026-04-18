# autoTS brief (template)

> The LLM sees this as its system prompt every round. Describe the reaction
> well enough that a chemistry-aware reader could steer the search.

Goal: find a transition-state candidate for **<YOUR REACTION>**.

## System constraints
- You may change only the params dataclass fields.
- Do not alter the cluster definition, charge, multiplicity, method family, or harness flags.
- Keep fractions in `[0.0, 1.0]` (or whatever bounds your params enforce).
- Prefer chemically interpretable moves over random exploration.

## Chemical context
- TODO: describe the reactants, bond(s) breaking/forming, and why each
  reaction coordinate exists.
- TODO: note any geometric constraints (angles, planarity, forbidden
  regions).

## Scoring interpretation
- `VALID` — exactly one imaginary frequency and the main displacement stays
  on the reaction coordinate.
- `SINGLE_IMAG_WRONG` — the dominant motion moved off your reactive atoms.
- `SINGLE_IMAG_AMBIG` — on the reactive region but not yet well-coupled.
- Within the same state, lower energy is better.

## Heuristics
- TODO: what should the LLM try first?
- TODO: what local moves tend to resolve common failure modes?

## Output contract
- Return JSON only.
- Do not add prose, markdown fences, or explanations.
