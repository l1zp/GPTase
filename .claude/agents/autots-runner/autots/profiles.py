"""Profile YAML loader.

No case concept here — caller passes the ``profiles.yaml`` path and the
``params_cls`` used to parse ``initial_guess``. Unknown top-level keys become
``case_config`` entries so cases can stash reaction-specific knobs in YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autots_types import AutoTSProfile
from autots_types import TheozymeMode
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_THEOZYME_PYTHONPATH = (REPO_ROOT.parent / "theozyme-mcp" / "src").resolve()
DEFAULT_THEOZYME_SERVER = "http://47.107.143.123:8080/sse"

_HARNESS_PROFILE_KEYS = {
    "cluster_path",
    "output_root",
    "chain",
    "charge",
    "mult",
    "cheap_mode",
    "full_mode",
    "initial_guess",
    "theozyme_server",
    "theozyme_pythonpath",
    "include_residues",
    "fallback_step",
    "proposal_model_name",
    "case_config",
}


def _resolve_path(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _parse_include_residues(
        data: list[dict[str, Any]] | None) -> tuple[tuple[str, str, int], ...]:
    if not data:
        return ()
    return tuple((str(item["chain"]), str(item["resname"]), int(item["resseq"]))
                 for item in data)


def load_profile(
    profile_id: str,
    profiles_path: str | Path,
    params_cls: type,
) -> AutoTSProfile:
    """Parse one profile out of ``profiles.yaml``.

    ``params_cls`` must expose a ``from_mapping(dict)`` classmethod (the
    :class:`AutoTSParamsBase` mixin provides one).
    """

    profiles_file = Path(profiles_path).resolve()
    raw = yaml.safe_load(profiles_file.read_text()) or {}
    profiles = raw.get("profiles", {})
    if profile_id not in profiles:
        raise KeyError(f"Profile {profile_id!r} not found in {profiles_file}")
    data = profiles[profile_id]
    case_config = dict(data.get("case_config") or {})
    for key, value in data.items():
        if key in _HARNESS_PROFILE_KEYS:
            continue
        case_config.setdefault(key, value)
    return AutoTSProfile(
        profile_id=profile_id,
        cluster_path=_resolve_path(data["cluster_path"], REPO_ROOT),
        output_root=_resolve_path(data["output_root"], REPO_ROOT),
        chain=str(data.get("chain", "B")),
        charge=int(data["charge"]),
        mult=int(data["mult"]),
        cheap_mode=TheozymeMode.from_mapping("cheap", data["cheap_mode"]),
        full_mode=TheozymeMode.from_mapping("full", data["full_mode"]),
        initial_guess=params_cls.from_mapping(data["initial_guess"]),
        theozyme_server=str(data.get("theozyme_server", DEFAULT_THEOZYME_SERVER)),
        theozyme_pythonpath=_resolve_path(
            data.get("theozyme_pythonpath", str(DEFAULT_THEOZYME_PYTHONPATH)),
            REPO_ROOT,
        ),
        include_residues=_parse_include_residues(data.get("include_residues")),
        fallback_step=float(data.get("fallback_step", 0.10)),
        proposal_model_name=data.get("proposal_model_name"),
        case_config=case_config,
    )
