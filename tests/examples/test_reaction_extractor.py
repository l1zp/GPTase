from pathlib import Path
import subprocess
import sys


class TestReactionExtractorExample:

    def test_help_runs_without_plan_loader_import(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "examples" / "reaction_extractor.py"),
                "--help",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "GPTase Enzyme Extraction Runner" in result.stdout
