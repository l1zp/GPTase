"""Tests for ligand alignment / replacement helpers under design/."""

from collections import Counter
from importlib import util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "design" / "scripts"
WRAPPER = SCRIPTS_DIR / "replace_3ny_with_5ni.py"
ALIGN_SCRIPT = SCRIPTS_DIR / "align_ligand.py"


def _load_module(path: Path, name: str):
    # Ensure sibling imports (e.g. align_ligand from the wrapper) resolve.
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = util.spec_from_file_location(name, path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _element_from_line(line: str) -> str:
    return line[76:78].strip()


class TestReactantReplacement:
    """Tests for replacing 3NY with a reactant-like 5NI ligand via the wrapper."""

    def test_replace_ligand_produces_chemically_correct_5nbi(self, tmp_path):
        module = _load_module(WRAPPER, "replace_3ny_with_5ni")
        input_path = ROOT / "design" / "prepared" / "7VUU" / "prepared_complex_minimized.pdb"
        output_path = tmp_path / "reactant_complex.pdb"

        module.replace_ligand(
            input_path=input_path,
            out_path=output_path,
            chain="B",
            resseq=101,
            source_resname="3NY",
            target_resname="5NI",
        )

        text = output_path.read_text().splitlines()
        ligand_lines = [
            line for line in text
            if line.startswith(("ATOM  ", "HETATM")) and line[17:20].strip() == "5NI"
        ]

        assert output_path.exists()
        assert not any(" 3NY " in line for line in text)

        # 5-NBI = C7H4N2O3: 12 heavy atoms + 4 hydrogens = 16 atoms.
        assert len(ligand_lines) == 16
        element_counts = Counter(_element_from_line(line) for line in ligand_lines)
        assert element_counts == {"C": 7, "H": 4, "N": 2, "O": 3}

        # CONECT records describing bonds are present.
        assert any(line.startswith("CONECT") for line in text)

    def test_wrapper_preserves_template_heavy_atom_names_on_shared_scaffold(
            self, tmp_path):
        """MCS atoms with matching elements should inherit the template name."""
        module = _load_module(WRAPPER, "replace_3ny_with_5ni")
        input_path = ROOT / "design" / "prepared" / "7VUU" / "prepared_complex_minimized.pdb"
        output_path = tmp_path / "reactant_complex.pdb"
        module.replace_ligand(input_path=input_path, out_path=output_path)

        ligand_lines = [
            line for line in output_path.read_text().splitlines()
            if line.startswith(("ATOM  ", "HETATM")) and line[17:20].strip() == "5NI"
        ]
        names = {line[12:16].strip() for line in ligand_lines}
        # Benzo-ring carbons and the nitro group share element identity between
        # 3NY and 5-NBI, so their template names must survive the swap.
        for inherited in ("C4", "C5", "C6", "C7", "C3A", "C7A", "NO1", "O11", "O21"):
            assert inherited in names, f"expected inherited name {inherited} in {names}"


class TestGenericAlignLigand:
    """Direct tests of the generic align_ligand driver."""

    def test_align_ligand_with_explicit_smiles_roundtrip(self, tmp_path):
        module = _load_module(ALIGN_SCRIPT, "align_ligand")
        input_path = ROOT / "design" / "prepared" / "7VUU" / "prepared_complex_minimized.pdb"
        output_path = tmp_path / "aligned.pdb"

        report = module.align_ligand(
            input_pdb=input_path,
            output_pdb=output_path,
            template_resname="3NY",
            template_chain="B",
            template_resseq=101,
            template_smiles="[O-][N+](=O)c1ccc2[nH]nnc2c1",
            target_smiles="C1=CC2=C(C=C1[N+](=O)[O-])C=NO2",
            target_resname="5NI",
        )

        assert output_path.exists()
        assert report["template_heavy_atoms"] == 12
        assert report["target_total_atoms"] == 16  # 12 heavy + 4 H
        # MCS between 3NY (benzotriazole) and 5-NBI (benzisoxazole) covers the
        # full 12-atom bicyclic skeleton when element compare is permissive.
        assert report["mcs_pairs"] == 12
        assert report["serial_shift_downstream"] == 0  # same heavy count

    def test_align_ligand_handles_different_atom_count(self, tmp_path):
        """Replacement with a molecule of different size shifts downstream serials."""
        module = _load_module(ALIGN_SCRIPT, "align_ligand")
        input_path = ROOT / "design" / "prepared" / "7VUU" / "prepared_complex_minimized.pdb"
        output_path = tmp_path / "aligned_larger.pdb"

        # Place a product-like phenolate (2-hydroxy-5-nitrobenzonitrile, neutral
        # phenol form; also C7H4N2O3 = 12 heavy atoms so serials don't shift).
        report = module.align_ligand(
            input_pdb=input_path,
            output_pdb=output_path,
            template_resname="3NY",
            template_chain="B",
            template_resseq=101,
            template_smiles="[O-][N+](=O)c1ccc2[nH]nnc2c1",
            target_smiles="C1=CC(=C(C=C1[N+](=O)[O-])C#N)O",
            target_resname="PRD",
        )

        ligand_lines = [
            line for line in output_path.read_text().splitlines()
            if line.startswith(("ATOM  ", "HETATM")) and line[17:20].strip() == "PRD"
        ]
        element_counts = Counter(_element_from_line(line) for line in ligand_lines)
        assert element_counts == {"C": 7, "H": 4, "N": 2, "O": 3}
        assert report["target_total_atoms"] == 16
