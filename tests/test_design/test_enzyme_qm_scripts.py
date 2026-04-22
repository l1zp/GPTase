"""Tests for the enzyme QM helper scripts."""

from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTRACT_SCRIPT = ROOT / ".claude" / "skills" / "enzyme-qm" / "scripts" / "extract_cluster.py"
CAP_SCRIPT = ROOT / ".claude" / "skills" / "enzyme-qm" / "scripts" / "cap_cluster.py"


def load_module(path: Path, name: str):
    """Load a script from disk."""
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestExtractCluster:
    """Tests for cluster extraction."""

    def test_extract_cluster_uses_heavy_atoms_for_cutoff_and_keeps_hydrogens(
            self, tmp_path):
        """Selected residues keep their prepared hydrogens."""
        module = load_module(EXTRACT_SCRIPT, "extract_cluster")
        pdb_path = tmp_path / "prepared_complex.pdb"
        pdb_path.write_text("\n".join([
            "ATOM      1  N   GLY B   1       0.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      2  H   GLY B   1      -0.600   0.000   0.000  1.00 20.00           H  ",
            "ATOM      3  CA  GLY B   1       1.200   0.000   0.000  1.00 20.00           C  ",
            "ATOM      4  C   GLY B   1       2.400   0.000   0.000  1.00 20.00           C  ",
            "ATOM      5  O   GLY B   1       3.400   0.000   0.000  1.00 20.00           O  ",
            "ATOM      6  N   ALA B   5      30.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      7  H   ALA B   5      29.400   0.000   0.000  1.00 20.00           H  ",
            "ATOM      8  CA  ALA B   5      31.200   0.000   0.000  1.00 20.00           C  ",
            "ATOM      9  C   ALA B   5      32.400   0.000   0.000  1.00 20.00           C  ",
            "ATOM     10  O   ALA B   5      33.400   0.000   0.000  1.00 20.00           O  ",
            "HETATM   11  C1  3NY B 101       1.400   1.300   0.000  1.00 20.00           C  ",
            "HETATM   12  H1  3NY B 101       1.400   2.300   0.000  1.00 20.00           H  ",
            "END",
            "",
        ]))

        out = Path(module.extract_cluster(str(pdb_path), "B", "3NY", 3.0))
        contents = out.read_text()

        assert " H   GLY B   1" in contents
        assert "ALA B   5" not in contents


class TestCapCluster:
    """Tests for cluster capping."""

    def test_cap_cluster_preserves_existing_hydrogens_and_avoids_duplicate_caps(
            self, tmp_path):
        """Re-running capping should not duplicate CAP hydrogens."""
        module = load_module(CAP_SCRIPT, "cap_cluster")
        cluster_path = tmp_path / "cluster.pdb"
        cluster_path.write_text("\n".join([
            "ATOM      1  N   GLY B   1       0.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      2  H   GLY B   1      -0.600   0.000   0.000  1.00 20.00           H  ",
            "ATOM      3  CA  GLY B   1       1.200   0.000   0.000  1.00 20.00           C  ",
            "ATOM      4  C   GLY B   1       2.400   0.000   0.000  1.00 20.00           C  ",
            "ATOM      5  O   GLY B   1       3.400   0.000   0.000  1.00 20.00           O  ",
            "HETATM    6  C1  3NY B 101       1.400   1.300   0.000  1.00 20.00           C  ",
            "END",
            "",
        ]))

        first = Path(module.cap_cluster(str(cluster_path), "B"))
        second = Path(module.cap_cluster(str(first), "B"))
        contents = second.read_text().splitlines()

        assert any(" H   GLY B   1" in line for line in contents)
        assert sum(" CAP B   1" in line and " HN " in line for line in contents) == 1
        assert sum(" CAP B   1" in line and " HC " in line for line in contents) == 1
