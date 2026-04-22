"""Tests for the design protein preparation workflow."""

from importlib import util
import json
from pathlib import Path
import shutil
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PREP_SCRIPT = ROOT / "design" / "scripts" / "prep_structure.py"


def load_module():
    """Load the prep_structure script as a module."""
    spec = util.spec_from_file_location("prep_structure", PREP_SCRIPT)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestManifestValidation:
    """Tests for manifest validation."""

    def test_load_manifest_requires_chains(self, tmp_path):
        """Manifest must contain chains."""
        module = load_module()
        config_path = tmp_path / "missing_chains.yaml"
        config_path.write_text("ligands: []\n")

        with pytest.raises(module.ManifestValidationError, match="chains"):
            module.load_manifest(config_path)

    def test_load_manifest_requires_ligands(self, tmp_path):
        """Manifest must contain ligands."""
        module = load_module()
        config_path = tmp_path / "missing_ligands.yaml"
        config_path.write_text("chains:\n  - B\n")

        with pytest.raises(module.ManifestValidationError, match="ligands"):
            module.load_manifest(config_path)


class TestNormalization:
    """Tests for normalization and reporting."""

    def test_filter_structure_strips_existing_hydrogens_from_7vus(self):
        """Existing hydrogens are removed before rebuilding."""
        module = load_module()
        manifest = module.load_manifest(ROOT / "design" / "config" / "7VUS.yaml")
        atoms = module.parse_pdb(ROOT / "design" / "structures" / "7VUS.pdb")

        filtered_atoms, report = module.filter_structure(atoms, manifest)

        assert report["stripped_hydrogens"] > 0
        assert all(atom.element != "H" for atom in filtered_atoms)

    def test_filter_structure_handles_altloc_mse_water_and_metal(self, tmp_path):
        """Normalization resolves altlocs and converts MSE while retaining policy hits."""
        module = load_module()
        pdb_path = tmp_path / "synthetic.pdb"
        pdb_path.write_text("\n".join([
            "ATOM      1  N   GLY B   1      10.000  10.000  10.000  1.00 20.00           N  ",
            "ATOM      2  CA AGLY B   1      11.000  10.000  10.000  0.40 20.00           C  ",
            "ATOM      3  CA BGLY B   1      11.100  10.000  10.000  0.60 20.00           C  ",
            "ATOM      4  C   GLY B   1      12.000  10.000  10.000  1.00 20.00           C  ",
            "ATOM      5  O   GLY B   1      13.000  10.000  10.000  1.00 20.00           O  ",
            "ATOM      6  N   MSE B   2      12.100  11.300  10.000  1.00 20.00           N  ",
            "ATOM      7  CA  MSE B   2      13.200  12.000  10.000  1.00 20.00           C  ",
            "ATOM      8  C   MSE B   2      14.400  11.200  10.000  1.00 20.00           C  ",
            "ATOM      9  O   MSE B   2      15.400  11.700  10.000  1.00 20.00           O  ",
            "ATOM     10 SE   MSE B   2      13.100  13.800  10.000  1.00 20.00          SE  ",
            "HETATM   11  C1  3NY B 101      10.500  11.500  12.000  1.00 20.00           C  ",
            "HETATM   12  N1  3NY B 101      10.500  12.700  12.000  1.00 20.00           N  ",
            "HETATM   13  O   HOH B 201      10.400  11.700  13.900  1.00 20.00           O  ",
            "HETATM   14 CA   CA  B 301      10.500  10.900  14.200  1.00 20.00          CA  ",
            "END",
            "",
        ]))
        config_path = tmp_path / "synthetic.yaml"
        config_path.write_text(
            yaml.safe_dump({
                "chains": ["B"],
                "ligands": [{
                    "chain": "B",
                    "resseq": 101,
                    "resname": "3NY"
                }],
                "water_policy": {
                    "keep": ["B:201:HOH"]
                },
                "metal_policy": {
                    "keep_resnames": ["CA"]
                },
                "ligand_states": {
                    "B:101:3NY": {
                        "smiles": "C",
                        "formal_charge": 0
                    }
                },
            }))

        manifest = module.load_manifest(config_path)
        atoms = module.parse_pdb(pdb_path)
        filtered_atoms, report = module.filter_structure(atoms, manifest)

        residue_names = {atom.resname for atom in filtered_atoms}
        atom_names = {atom.name for atom in filtered_atoms}

        assert residue_names >= {"GLY", "MET", "3NY", "HOH", "CA"}
        assert "MSE" not in residue_names
        assert "SD" in atom_names
        assert "SE" not in atom_names
        assert report["altloc_choices"][0]["selected_altloc"] == "B"
        assert any(entry["kept"] for entry in report["water_report"])
        assert any(entry["kept"] for entry in report["metal_report"])

    def test_detect_disulfides_and_backbone_breaks(self, tmp_path):
        """Connectivity reporting finds broken peptide bonds and disulfides."""
        module = load_module()
        pdb_path = tmp_path / "connectivity.pdb"
        pdb_path.write_text("\n".join([
            "ATOM      1  N   CYS B   1       0.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      2  CA  CYS B   1       1.300   0.000   0.000  1.00 20.00           C  ",
            "ATOM      3  C   CYS B   1       2.600   0.000   0.000  1.00 20.00           C  ",
            "ATOM      4  O   CYS B   1       3.600   0.000   0.000  1.00 20.00           O  ",
            "ATOM      5  SG  CYS B   1       1.200   1.800   0.000  1.00 20.00           S  ",
            "ATOM      6  N   CYS B   2       5.500   0.000   0.000  1.00 20.00           N  ",
            "ATOM      7  CA  CYS B   2       6.700   0.000   0.000  1.00 20.00           C  ",
            "ATOM      8  C   CYS B   2       8.000   0.000   0.000  1.00 20.00           C  ",
            "ATOM      9  O   CYS B   2       9.000   0.000   0.000  1.00 20.00           O  ",
            "ATOM     10  SG  CYS B   2       1.300   3.900   0.000  1.00 20.00           S  ",
            "END",
            "",
        ]))

        atoms = module.parse_pdb(pdb_path)

        breaks = module.detect_backbone_breaks(atoms)
        disulfides = module.detect_disulfides(atoms)

        assert breaks
        assert breaks[0]["reason"] == "broken_peptide_bond"
        assert disulfides


class TestPipeline:
    """Tests for the prep pipeline entry point."""

    def test_run_pipeline_writes_normalized_complex_before_backend_failure_on_7vuu(
            self, tmp_path, monkeypatch):
        """Normalization completes even when chemistry backends are unavailable."""
        module = load_module()

        def fake_detect_dependencies():
            return {
                "yaml": {
                    "available": True,
                    "path": "yaml"
                },
                "gemmi": {
                    "available": False,
                    "path": None
                },
                "openmm": {
                    "available": False,
                    "path": None
                },
                "pdb2pqr": {
                    "available": False,
                    "path": None
                },
                "propka": {
                    "available": False,
                    "path": None
                },
                "rdkit": {
                    "available": False,
                    "path": None
                },
                "reduce": {
                    "available": False,
                    "path": None
                },
            }

        monkeypatch.setattr(module, "detect_dependencies", fake_detect_dependencies)

        args = module.parse_args([
            "--input",
            str(ROOT / "design" / "structures" / "7VUU.pdb"),
            "--config",
            str(ROOT / "design" / "config" / "7VUU.yaml"),
            "--outdir",
            str(tmp_path),
        ])

        result = module.run_pipeline(args)

        assert result == 1
        assert (tmp_path / "normalized_complex.pdb").exists()
        report = json.loads((tmp_path / "prep_report.json").read_text())
        assert report["status"] == "failed"
        assert "dependency" in report["error"].lower(
        ) or "pdb2pqr" in report["error"].lower()

    def test_run_pipeline_records_manual_review_for_ambiguous_ligand(
            self, tmp_path, monkeypatch):
        """Ambiguous ligand chemistry produces manual_review.json."""
        module = load_module()
        config_path = tmp_path / "ambiguous.yaml"
        config = yaml.safe_load((ROOT / "design" / "config" / "7VUU.yaml").read_text())
        config["ligand_states"] = {}
        config["run_minimization"] = False
        config_path.write_text(yaml.safe_dump(config))

        def fake_run_pdb2pqr_propka(protein_path, outdir, dependencies):
            return {"residue_states": {}}

        def fake_run_reduce(protein_path, outdir, dependencies):
            output_path = outdir / "protein_h.pdb"
            shutil.copyfile(protein_path, output_path)
            return output_path, {"backend": "mock"}

        def fake_prepare_ligands(grouped_ligands, manifest, outdir, dependencies):
            raise module.ManualReviewRequired("ambiguous ligand")

        monkeypatch.setattr(module, "run_pdb2pqr_propka", fake_run_pdb2pqr_propka)
        monkeypatch.setattr(module, "run_reduce", fake_run_reduce)
        monkeypatch.setattr(module, "prepare_ligands", fake_prepare_ligands)

        args = module.parse_args([
            "--input",
            str(ROOT / "design" / "structures" / "7VUU.pdb"),
            "--config",
            str(config_path),
            "--outdir",
            str(tmp_path / "out"),
        ])

        result = module.run_pipeline(args)

        assert result == 1
        manual = json.loads((tmp_path / "out" / "manual_review.json").read_text())
        assert manual
        assert manual[0]["category"] == "ligand_chemistry"

    def test_run_minimization_with_fake_openmm_backend(self, tmp_path, monkeypatch):
        """Restrained minimization writes a minimized PDB and summary."""
        module = load_module()
        prepared_path = tmp_path / "prepared_complex.pdb"
        prepared_path.write_text("\n".join([
            "ATOM      1  N   GLY B   1       0.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      2  H   GLY B   1      -0.600   0.000   0.000  1.00 20.00           H  ",
            "ATOM      3  CA  GLY B   1       1.200   0.000   0.000  1.00 20.00           C  ",
            "ATOM      4  C   GLY B   1       2.400   0.000   0.000  1.00 20.00           C  ",
            "ATOM      5  O   GLY B   1       3.400   0.000   0.000  1.00 20.00           O  ",
            "END",
            "",
        ]))
        manifest = module.Manifest(
            chains=["B"],
            ligands=[module.LigandSelection(chain="B", resseq=101, resname="3NY")],
            water_policy={
                "mode": "within_distance",
                "cutoff": 3.5,
                "keep": [],
                "keep_resnames": []
            },
            metal_policy={
                "mode": "within_distance",
                "cutoff": 4.0,
                "keep": [],
                "keep_resnames": []
            },
            protein_protonation_overrides={},
            ligand_states={},
            run_minimization=True,
        )

        class FakeValue:

            def __init__(self, value):
                self.value = value

            def value_in_unit(self, unit):
                return self.value

        class FakePositions:

            def __init__(self, positions):
                self.positions = positions

            def value_in_unit(self, unit):
                return self.positions

        class FakeState:

            def __init__(self, positions):
                self.positions = positions

            def getPositions(self):
                return FakePositions(self.positions)

            def getPotentialEnergy(self):
                return FakeValue(12.34)

        class FakeContext:

            def __init__(self):
                self.positions = None

            def setPositions(self, positions):
                self.positions = positions

            def getState(self, getPositions=False, getEnergy=False):
                shifted = [(x + 0.1, y, z) for x, y, z in self.positions]
                return FakeState(shifted)

        class FakeSimulation:

            def __init__(self, topology, system, integrator):
                self.topology = topology
                self.system = system
                self.integrator = integrator
                self.context = FakeContext()

            def minimizeEnergy(self, maxIterations=0):
                return None

        class FakeSystem:

            def __init__(self):
                self.forces = []

            def addForce(self, force):
                self.forces.append(force)

        class FakeCustomExternalForce:

            def __init__(self, expression):
                self.expression = expression
                self.particles = []

            def addGlobalParameter(self, name, value):
                return None

            def addPerParticleParameter(self, name):
                return None

            def addParticle(self, index, values):
                self.particles.append((index, values))

        class FakeForceField:

            def __init__(self, *args):
                self.args = args

            def createSystem(self, topology, nonbondedMethod=None, constraints=None):
                return FakeSystem()

        class FakePDBFile:

            def __init__(self, path):
                atoms = module.parse_pdb(Path(path))
                self.topology = object()
                self.positions = [(atom.x, atom.y, atom.z) for atom in atoms]

        class FakeLangevinIntegrator:

            def __init__(self, temperature, friction, step):
                self.temperature = temperature
                self.friction = friction
                self.step = step

        class FakeUnit:

            def __rmul__(self, value):
                return value

            def __rtruediv__(self, value):
                return value

        class FakeOpenMM:
            CustomExternalForce = FakeCustomExternalForce
            LangevinIntegrator = FakeLangevinIntegrator

        class FakeApp:
            PDBFile = FakePDBFile
            ForceField = FakeForceField
            Simulation = FakeSimulation
            NoCutoff = "nocutoff"

        class FakeUnits:
            kelvin = FakeUnit()
            picosecond = FakeUnit()
            picoseconds = FakeUnit()
            angstrom = object()
            kilojoule_per_mole = object()

        original_import = module.importlib.import_module

        def fake_import_module(name):
            if name == "openmm":
                return FakeOpenMM
            if name == "openmm.app":
                return FakeApp
            if name == "openmm.unit":
                return FakeUnits
            return original_import(name)

        monkeypatch.setattr(module.importlib, "import_module", fake_import_module)

        minimized_path, summary = module.run_minimization(
            prepared_path,
            manifest,
            tmp_path,
            {"openmm": {
                "available": True,
                "path": "openmm"
            }},
            None,
        )

        assert minimized_path.exists()
        assert summary["status"] == "completed"
        assert summary["restrained_atom_count"] > 0
        assert summary["rmsd"] > 0.0


class TestLigandPreparation:
    """Tests for ligand-specific preparation helpers."""

    def test_prepare_ligands_adds_hydrogens_and_bonds_for_real_3ny(self, tmp_path):
        """Prepared ligands preserve observed heavy-atom geometry and include bonds."""
        module = load_module()
        manifest = module.load_manifest(ROOT / "design" / "config" / "7VUU.yaml")
        atoms = module.parse_pdb(ROOT / "design" / "structures" / "7VUU.pdb")
        filtered_atoms, _ = module.filter_structure(atoms, manifest)
        grouped_ligands = module.select_ligand_atoms(filtered_atoms, manifest)

        prepared_ligands, sdf_path = module.prepare_ligands(
            grouped_ligands,
            manifest,
            tmp_path,
            {"rdkit": {
                "available": True,
                "path": "rdkit"
            }},
        )

        prepared = prepared_ligands[0]
        original_heavy = {
            atom.name: (atom.x, atom.y, atom.z)
            for atom in grouped_ligands[prepared.selection.key]
        }
        prepared_heavy = {
            atom.name: (atom.x, atom.y, atom.z)
            for atom in prepared.atoms if atom.element != "H"
        }

        assert sdf_path.exists()
        assert len(prepared.bond_pairs) == 17
        assert sum(1 for atom in prepared.atoms if atom.element == "H") == 4
        assert set(prepared_heavy) == set(original_heavy)
        assert prepared_heavy["N1"] == pytest.approx(original_heavy["N1"])
        assert {"H1", "H2", "H3", "H4"} <= {atom.name for atom in prepared.atoms}
        assert prepared.chemistry_source == "rcsb_ccd"
        assert prepared.formal_charge == 0
        assert prepared.explicit_hydrogens == 4


class TestCcdChemistryResolution:
    """Tests for the CCD-first ligand chemistry resolution path."""

    def test_fetch_ccd_chemistry_uses_cache(self, tmp_path):
        """Existing cache entries short-circuit the network call."""
        module = load_module()
        cache_dir = tmp_path / "ccd_cache"
        cache_dir.mkdir()
        payload = {
            "smiles": "c1cc2c(cc1[N+](=O)[O-])nn[nH]2",
            "formal_charge": 0,
            "name": "5-nitro-1H-benzotriazole",
            "formula": "C6 H4 N4 O2",
            "source": "rcsb_ccd",
            "fetched_at": "2026-04-21T00:00:00+00:00",
        }
        (cache_dir / "3NY.json").write_text(json.dumps(payload))

        def _must_not_open(url, timeout=None):
            raise AssertionError(f"opener should not be called; url={url}")

        result = module.fetch_ccd_chemistry("3ny",
                                            cache_dir=cache_dir,
                                            opener=_must_not_open)
        assert result["smiles"] == payload["smiles"]
        assert result["source"] == "rcsb_ccd"

    def test_fetch_ccd_chemistry_falls_back_to_network(self, tmp_path):
        """Cache miss triggers the RCSB REST call and persists a cached entry."""
        module = load_module()
        cache_dir = tmp_path / "ccd_cache"
        rcsb_payload = {
            "chem_comp": {
                "name": "5-nitro-1H-benzotriazole",
                "formula": "C6 H4 N4 O2",
                "pdbx_formal_charge": 0,
            },
            "rcsb_chem_comp_descriptor": {
                "SMILES": "c1cc2c(cc1[N+](=O)[O-])nn[nH]2",
            },
        }

        class _FakeResponse:

            def __init__(self, body):
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return self._body

        calls = []

        def _opener(url, timeout=None):
            calls.append(url)
            return _FakeResponse(json.dumps(rcsb_payload).encode("utf-8"))

        result = module.fetch_ccd_chemistry("3NY", cache_dir=cache_dir, opener=_opener)

        assert calls == [module.CCD_RCSB_ENDPOINT.format(resname="3NY")]
        assert result["smiles"] == rcsb_payload["rcsb_chem_comp_descriptor"]["SMILES"]
        assert (cache_dir / "3NY.json").exists()

    def test_fetch_ccd_chemistry_raises_manual_review_on_missing_smiles(self, tmp_path):
        """A payload without any SMILES surfaces as manual review."""
        module = load_module()
        cache_dir = tmp_path / "ccd_cache"

        class _FakeResponse:

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"chem_comp": {}}).encode("utf-8")

        def _opener(url, timeout=None):
            return _FakeResponse()

        with pytest.raises(module.ManualReviewRequired, match="SMILES"):
            module.fetch_ccd_chemistry("XXX", cache_dir=cache_dir, opener=_opener)

    def test_resolve_ligand_chemistry_manifest_override_wins(self):
        """An explicit manifest SMILES short-circuits the CCD lookup."""
        module = load_module()
        selection = module.LigandSelection(chain="B", resseq=101, resname="3NY")
        manifest = module.Manifest(
            chains=["B"],
            ligands=[selection],
            water_policy={
                "mode": "within_distance",
                "cutoff": 3.5,
                "keep": [],
                "keep_resnames": []
            },
            metal_policy={
                "mode": "within_distance",
                "cutoff": 4.0,
                "keep": [],
                "keep_resnames": ["CA"]
            },
            protein_protonation_overrides={},
            ligand_states={selection.key: {
                "smiles": "O=C(O)C",
                "formal_charge": 0
            }},
        )

        def _must_not_call(resname):
            raise AssertionError("CCD fetcher should not be called")

        chemistry, source = module.resolve_ligand_chemistry(selection,
                                                            manifest,
                                                            fetcher=_must_not_call)
        assert source == "manifest"
        assert chemistry["smiles"] == "O=C(O)C"

    def test_resolve_ligand_chemistry_falls_back_to_ccd(self):
        """Empty manifest state triggers the CCD fetcher."""
        module = load_module()
        selection = module.LigandSelection(chain="B", resseq=101, resname="3NY")
        manifest = module.Manifest(
            chains=["B"],
            ligands=[selection],
            water_policy={
                "mode": "within_distance",
                "cutoff": 3.5,
                "keep": [],
                "keep_resnames": []
            },
            metal_policy={
                "mode": "within_distance",
                "cutoff": 4.0,
                "keep": [],
                "keep_resnames": ["CA"]
            },
            protein_protonation_overrides={},
            ligand_states={},
        )

        def _fetcher(resname):
            assert resname == "3NY"
            return {
                "smiles": "c1cc2c(cc1[N+](=O)[O-])nn[nH]2",
                "formal_charge": 0,
                "name": "5-nitro-1H-benzotriazole",
                "formula": "C6 H4 N4 O2",
                "source": "rcsb_ccd",
                "fetched_at": "2026-04-21T00:00:00+00:00",
            }

        chemistry, source = module.resolve_ligand_chemistry(selection,
                                                            manifest,
                                                            fetcher=_fetcher)
        assert source == "rcsb_ccd"
        assert chemistry["smiles"].startswith("c1cc2c(cc1[N+](=O)[O-])")
        assert chemistry["formal_charge"] == 0


class TestProteinFallbacks:
    """Tests for protein hydrogen and terminal fallback logic."""

    def test_ensure_chain_start_backbone_hydrogens_adds_nterm_hydrogens_and_oxt(
            self, tmp_path):
        """Fallback writes chain-start H atoms, a terminal OXT, and a TER record."""
        module = load_module()
        protein_path = tmp_path / "protein_h.pdb"
        protein_path.write_text("\n".join([
            "ATOM      1  N   GLY B   1       0.000   0.000   0.000  1.00 20.00           N  ",
            "ATOM      2  CA  GLY B   1       1.450   0.000   0.000  1.00 20.00           C  ",
            "ATOM      3  C   GLY B   1       2.050   1.330   0.000  1.00 20.00           C  ",
            "ATOM      4  O   GLY B   1       1.410   2.340   0.000  1.00 20.00           O  ",
            "ATOM      5  N   ALA B   2       3.340   1.350   0.000  1.00 20.00           N  ",
            "ATOM      6  CA  ALA B   2       4.050   2.610   0.000  1.00 20.00           C  ",
            "ATOM      7  C   ALA B   2       5.550   2.420   0.000  1.00 20.00           C  ",
            "ATOM      8  O   ALA B   2       6.090   1.320   0.000  1.00 20.00           O  ",
            "ATOM      9  CB  ALA B   2       3.520   3.410   1.200  1.00 20.00           C  ",
            "END",
            "",
        ]))

        report = module.ensure_chain_start_backbone_hydrogens(protein_path)
        atoms = module.parse_pdb(protein_path)
        residue1 = {
            atom.name
            for atom in atoms if atom.chain == "B" and atom.resseq == 1
        }
        residue2 = {
            atom.name
            for atom in atoms if atom.chain == "B" and atom.resseq == 2
        }
        text = protein_path.read_text()

        assert report["status"] == "completed"
        assert {"H", "H2", "H3"} <= residue1
        assert "OXT" in residue2
        assert "TER" in text
