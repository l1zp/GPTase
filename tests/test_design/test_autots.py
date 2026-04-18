"""Regression tests for the autoTS harness + Kemp reaction spec.

Kemp is now defined entirely by ``cases/kemp/reaction.yaml`` (no Python);
the harness interpreter in ``reaction_spec.py`` turns that YAML into
callable mutate / compute_metrics / classify_single_imag hooks.
"""

from importlib import util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
AUTOTS_DIR = ROOT / ".claude" / "agents" / "autots-runner" / "autots"
KEMP_DIR = AUTOTS_DIR / "cases" / "kemp"


def _ensure_paths() -> None:
    for p in (AUTOTS_DIR, ):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def _import(name: str, path: Path):
    spec = util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_harness():
    _ensure_paths()
    autots_types = _import("autots_types", AUTOTS_DIR / "autots_types.py")
    profiles = _import("profiles", AUTOTS_DIR / "profiles.py")
    diagnostics = _import("diagnostics", AUTOTS_DIR / "diagnostics.py")
    reaction_spec = _import("reaction_spec", AUTOTS_DIR / "reaction_spec.py")
    return autots_types, profiles, diagnostics, reaction_spec


def _load_kemp():
    _, profiles, _, reaction_spec = load_harness()
    reaction = reaction_spec.load_reaction(KEMP_DIR / "reaction.yaml")
    profile = profiles.load_profile("7VUU_core", KEMP_DIR / "profiles.yaml",
                                    reaction.params_cls)
    return reaction, profile


def parse_labeled_xyz(path: Path) -> dict[str, tuple[float, float, float]]:
    labels: dict[str, tuple[float, float, float]] = {}
    for line in path.read_text().splitlines()[2:]:
        if "#" not in line:
            continue
        left, right = line.split("#", 1)
        parts = left.split()
        if len(parts) < 4:
            continue
        labels[right.strip()] = (float(parts[1]), float(parts[2]), float(parts[3]))
    return labels


class TestAutoTS:

    def test_mutate_ts_guess_reproduces_core_reference_positions(self):
        reaction, profile = _load_kemp()
        guess = reaction.mutate_ts_guess(profile, profile.initial_guess)
        labels = {atom.label: atom for atom in guess.atom_records}
        reference = parse_labeled_xyz(ROOT / "design" / "ts" / "7VUU"
                                      / "core_ts_guess.xyz")

        assert len(guess.atom_records) == 31
        assert guess.xyz_text.splitlines()[0] == "31"
        for atom_name in ("H3", "N2", "O1"):
            label = f"B:101:5NI:{atom_name}"
            atom = labels[label]
            ref = reference[f"5NI101:{atom_name}"]
            assert abs(atom.x - ref[0]) < 1e-3
            assert abs(atom.y - ref[1]) < 1e-3
            assert abs(atom.z - ref[2]) < 1e-3

    def test_proton_bend_moves_h3_off_midpoint_without_moving_other_reactive_atoms(
            self):
        reaction, profile = _load_kemp()
        bent_params = reaction.params_cls(
            h_transfer_frac=profile.initial_guess.h_transfer_frac,
            acceptor_choice=profile.initial_guess.acceptor_choice,
            ring_opening_frac=profile.initial_guess.ring_opening_frac,
            n_elongation_frac=profile.initial_guess.n_elongation_frac,
            proton_bend=0.10,
        )

        base_guess = reaction.mutate_ts_guess(profile, profile.initial_guess)
        bent_guess = reaction.mutate_ts_guess(profile, bent_params)
        base_labels = {atom.label: atom for atom in base_guess.atom_records}
        bent_labels = {atom.label: atom for atom in bent_guess.atom_records}

        h3_label = "B:101:5NI:H3"
        n2_label = "B:101:5NI:N2"
        o1_label = "B:101:5NI:O1"

        h3_shift = (abs(base_labels[h3_label].x - bent_labels[h3_label].x)
                    + abs(base_labels[h3_label].y - bent_labels[h3_label].y)
                    + abs(base_labels[h3_label].z - bent_labels[h3_label].z))
        n2_shift = (abs(base_labels[n2_label].x - bent_labels[n2_label].x)
                    + abs(base_labels[n2_label].y - bent_labels[n2_label].y)
                    + abs(base_labels[n2_label].z - bent_labels[n2_label].z))
        o1_shift = (abs(base_labels[o1_label].x - bent_labels[o1_label].x)
                    + abs(base_labels[o1_label].y - bent_labels[o1_label].y)
                    + abs(base_labels[o1_label].z - bent_labels[o1_label].z))

        assert h3_shift > 1e-4
        assert n2_shift == 0.0
        assert o1_shift == 0.0

    def test_diagnose_replays_golden_multi_imag(self):
        reaction, profile = _load_kemp()
        types_mod, _, diagnostics, _ = load_harness()
        guess = reaction.mutate_ts_guess(profile, profile.initial_guess)
        payload = json.loads(
            (ROOT / "design" / "ts" / "7VUU"
             / "core_ts_opt_result_charge_m1_100cycles.json").read_text())

        metrics = diagnostics.diagnose(
            payload,
            guess,
            profile,
            compute_case_metrics=reaction.compute_case_metrics,
            classify_single_imag=reaction.classify_single_imag,
        )

        assert metrics.state == types_mod.TSState.MULTI_IMAG
        assert metrics.imag_freqs_cm1 == (-59.93, -29.02, -15.89, -10.9)
        assert metrics.max_abs_imag_cm1 == 59.93
