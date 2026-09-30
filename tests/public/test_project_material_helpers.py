from __future__ import annotations

from calm.public.project import Project
from calm.public.inputs.materials import Material


def test_project_material_resolves_workspace_object(monkeypatch, tmp_path):
    # Simulate a workspace with query.get_bulk that returns a bulk-like object
    class FakeAtoms:
        def __len__(self):
            return 2

        def get_positions(self):
            return [[0, 0, 0], [0.5, 0.5, 0.5]]

        def get_cell(self):
            return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        def get_chemical_formula(self, **kwargs):
            del kwargs
            return "LiF"

    class FakeBulk:
        def __init__(self):
            self.uid_full = "bulk:b_test"
            self.id_short = "b_test"
            self.label = "LiF_opt"
            self.atoms = FakeAtoms()
            self.formula = "LiF"

    class FakeWorkspace:
        def list_bulks(self, *, limit=None):
            return [{"uid_full": "bulk:b_test", "id_short": "b_test", "label": "LiF_opt"}]

        def get_bulk(self, uid_or_short: str):
            if uid_or_short in ("b_test", "bulk:b_test"):
                return FakeBulk()
            raise KeyError

    fake_ws = FakeWorkspace()

    proj = Project(workspace=fake_ws, path=tmp_path)
    mat = proj.material("LiF_opt")
    assert isinstance(mat, Material)
    # atoms should be populated via workspace lookup
    atoms = mat.to_ase()
    assert atoms is not None
    assert mat.uid_full == "bulk:b_test"
    assert mat.id_short == "b_test"
