"""Theozyme GPU worker subprocess wrapper.

Owns: building the theozyme CLI command, running it with the right PYTHONPATH,
tolerant JSON parsing from mixed stdout/stderr, and small utilities to parse
the returned XYZ / imaginary frequency data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from autots_types import AutoTSProfile
from autots_types import TheozymeMode
from profiles import REPO_ROOT

_IMAG_FREQ_RE = re.compile(r"Imaginary frequencies:\s*\[([^\]]+)\]\s*cm")


def _load_json_response(stdout: str, stderr: str) -> dict[str, Any]:
    for candidate in (stdout.strip(), stderr.strip()):
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return payload
        decoder = json.JSONDecoder()
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
    raise ValueError("Unable to decode theozyme JSON output")


def submit_theozyme(
    guess_path: Path,
    profile: AutoTSProfile,
    mode: TheozymeMode,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "theozyme_mcp.cli.main",
        "--server",
        profile.theozyme_server,
        "pysisyphus_ts_opt",
        "--xyz-content",
        f"@{guess_path}",
        "--method",
        mode.method,
        "--basis",
        mode.basis,
        "--algo",
        mode.algo,
        "--hessian-init",
        mode.hessian_init,
        "--hessian-recalc",
        str(mode.hessian_recalc),
        "--max-cycles",
        str(mode.max_cycles),
        "--coord-type",
        mode.coord_type,
        "--charge",
        str(profile.charge),
        "--mult",
        str(profile.mult),
        "--pal",
        str(mode.pal),
    ]
    if mode.xc is not None:
        cmd.extend(["--xc", mode.xc])
    if mode.use_gpu:
        cmd.append("--use-gpu")

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{profile.theozyme_pythonpath}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath else str(profile.theozyme_pythonpath))

    try:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=mode.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "success": False,
            "message": f"theozyme {mode.label} timed out",
            "error": f"Timed out after {mode.timeout_seconds}s",
            "data": None,
            "autots_cli": {
                "command": cmd,
                "timeout_seconds": mode.timeout_seconds,
                "stdout": (exc.stdout or "")[-4000:],
                "stderr": (exc.stderr or "")[-4000:],
            },
        }
    except OSError as exc:
        return {
            "success": False,
            "message": "theozyme subprocess failed to start",
            "error": str(exc),
            "data": None,
            "autots_cli": {
                "command": cmd,
                "timeout_seconds": mode.timeout_seconds,
            },
        }

    try:
        payload = _load_json_response(completed.stdout, completed.stderr)
    except ValueError:
        payload = {
            "success": False,
            "message": "theozyme did not return JSON",
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "data": None,
        }
    payload.setdefault("autots_cli", {})
    payload["autots_cli"].update({
        "command": cmd,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    })
    return payload


def parse_xyz_text(xyz_text: str) -> list[tuple[str, float, float, float]]:
    lines = [line.rstrip() for line in xyz_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("XYZ text is incomplete")
    atom_count = int(lines[0].strip())
    atoms: list[tuple[str, float, float, float]] = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        atoms.append((parts[0], float(parts[1]), float(parts[2]), float(parts[3])))
    if len(atoms) != atom_count:
        raise ValueError(
            f"XYZ atom count mismatch: expected {atom_count}, got {len(atoms)}")
    return atoms


def extract_imaginary_freqs(result_payload: dict[str, Any]) -> tuple[float, ...]:
    data = result_payload.get("data")
    if isinstance(data, dict):
        direct = data.get("imaginary_freq_cm1")
        if isinstance(direct, (int, float)):
            return (float(direct), )
        if isinstance(direct, list):
            return tuple(float(value) for value in direct)
        raw_output = data.get("raw_output") or ""
        if raw_output:
            match = _IMAG_FREQ_RE.search(raw_output)
            if match:
                chunk = match.group(1)
                return tuple(
                    float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", chunk))
    return ()
