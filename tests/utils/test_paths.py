"""Unit tests for gptase.utils.paths — active-in-core surface only.

Scoped to the ProjectPaths API actually used by gptase/ core: just
`get_paths()` and `.project_root`, consumed by `gptase/main.py` to
resolve `config/plans/<plan_id>.md` for `chat -p`. The dead methods
(get_document_*, get_extraction_*, get_vision_*, resolve_output_path,
get_cache_path, get_log_path, get_plan_output_dir, reset_paths) and the
examples-only methods (resolve_input_path, get_document_path,
output_dir, input_dir) are intentionally not covered — see
project_utils_consolidation_pending.md for the deletion plan.
"""
from pathlib import Path

import pytest

from gptase.utils.paths import get_paths
from gptase.utils.paths import ProjectPaths


@pytest.fixture(autouse=True)
def _reset_paths_singleton():
    """Clear the module-level singleton before and after every test.

    Manipulates `_global_paths` directly so this fixture survives the
    planned deletion of the public `reset_paths()` helper.
    """
    import gptase.utils.paths as _paths_mod
    _paths_mod._global_paths = None
    yield
    _paths_mod._global_paths = None


class TestProjectRootDetection:
    """ProjectPaths(None) -> _find_project_root walks up the cwd chain."""

    def test_finds_pyproject_toml_marker_in_parent(self, tmp_path, monkeypatch):
        proj = tmp_path / "myproj"
        work = proj / "deeply" / "nested"
        work.mkdir(parents=True)
        (proj / "pyproject.toml").write_text("[project]\nname = 'x'\n")

        monkeypatch.chdir(work)
        paths = ProjectPaths()

        assert paths.project_root == proj.resolve()

    def test_finds_git_dir_marker_in_parent(self, tmp_path, monkeypatch):
        proj = tmp_path / "myproj"
        work = proj / "src"
        work.mkdir(parents=True)
        (proj / ".git").mkdir()

        monkeypatch.chdir(work)
        paths = ProjectPaths()

        assert paths.project_root == proj.resolve()


class TestExplicitProjectRoot:
    """ProjectPaths(some_path) bypasses detection and resolves to absolute."""

    def test_explicit_project_root_resolved_to_absolute(self, tmp_path):
        paths = ProjectPaths(project_root=tmp_path)

        assert paths.project_root == tmp_path.resolve()
        assert paths.project_root.is_absolute()


class TestGetPathsSingleton:
    """get_paths() must return the same ProjectPaths instance across calls."""

    def test_returns_same_instance_on_repeat_calls(self, tmp_path):
        first = get_paths(tmp_path)
        second = get_paths()

        assert first is second

    def test_subsequent_call_ignores_project_root_arg(self, tmp_path):
        first = get_paths(tmp_path)
        other = tmp_path / "elsewhere"
        other.mkdir()
        second = get_paths(other)

        assert first is second
        assert second.project_root == tmp_path.resolve()


class TestCoreContract:
    """Pin the contract gptase/main.py depends on:
    `get_paths().project_root / <subdir_str>` must produce a Path.
    """

    def test_project_root_supports_path_division(self, tmp_path):
        paths = get_paths(tmp_path)

        result = paths.project_root / "config" / "plans"

        assert isinstance(result, Path)
        assert result == tmp_path.resolve() / "config" / "plans"
