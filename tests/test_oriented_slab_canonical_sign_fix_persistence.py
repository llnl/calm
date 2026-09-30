from ase import Atoms

from calm.bulk.bulk import Bulk
from calm.slab.oriented.model import build_oriented_slab
from calm.structure.payloads import atoms_to_dict
from calm.structure.payloads import dict_to_atoms
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from calm.slab.slab import get_oriented_slab_transforms_payload


def test_canonical_sign_fix_roundtrip_via_atoms_info() -> None:
    """Ensure canonical_sign_fix metadata round-trips through atoms_to_dict/dict_to_atoms.

    We synthesize a transforms payload that includes a canonical_sign_fix entry,
    stamp it into the slab Atoms.info JSON string, persist via atoms_to_dict, and
    verify the recovered Atoms contains the same payload after dict->atoms.
    """

    conv = Atoms("Al", positions=[[0.0, 0.0, 0.0]], cell=[3.0, 3.0, 3.0], pbc=True)

    res = build_oriented_slab(Bulk(conv), hkl=(0, 0, 1), layers=1, vacuum=None)
    slab = res.slab

    payload = dict(slab.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY])
    payload["canonical_sign_fix"] = {"L_diag": [1, -1, 1]}
    slab.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY] = payload

    # Persist via atoms_to_dict and reconstruct via dict_to_atoms
    d = atoms_to_dict(slab)
    assert "info" in d and ORIENTED_SLAB_TRANSFORMS_INFO_KEY in d["info"]

    slab_rt = dict_to_atoms(d)
    assert slab_rt is not None

    payload = get_oriented_slab_transforms_payload(slab_rt)
    assert payload is not None
    assert "canonical_sign_fix" in payload
    assert payload["canonical_sign_fix"]["L_diag"] == [1, -1, 1]
