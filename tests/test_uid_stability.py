"""Tests for deterministic UID behavior used by current workflows."""

from __future__ import annotations

import pytest
import numpy as np

from calm.keys import uid


class TestCanonicalJSONStability:
    """Test that canonical JSON serialization remains stable."""

    def test_dict_key_sorting(self):
        """Test that dict keys are sorted alphabetically."""
        obj = {"z": 3, "a": 1, "m": 2}
        json_str = uid.canonical_json(obj)
        assert json_str == '{"a":1,"m":2,"z":3}'

    def test_float_rounding_default(self):
        """Test default 12-decimal float rounding."""
        obj = {"value": 1.234567890123456789}
        json_str = uid.canonical_json(obj)
        assert json_str == '{"value":1.234567890123}'

    def test_float_zero_threshold(self):
        """Test that tiny floats become exactly 0.0."""
        obj = {"value": 1e-13}  # Below 12-decimal threshold
        json_str = uid.canonical_json(obj)
        assert json_str == '{"value":0.0}'

    def test_numpy_array_to_list(self):
        """Test that numpy arrays become lists."""
        obj = {"arr": np.array([1, 2, 3])}
        json_str = uid.canonical_json(obj)
        assert json_str == '{"arr":[1,2,3]}'

    def test_numpy_float_array_rounding(self):
        """Test that numpy float arrays are rounded."""
        obj = {"arr": np.array([1.123456789012345, 2.987654321098765])}
        json_str = uid.canonical_json(obj)
        assert json_str == '{"arr":[1.123456789012,2.987654321099]}'

    def test_nested_dict_sorting(self):
        """Test that nested dicts also have sorted keys."""
        obj = {"outer": {"z": 1, "a": 2}}
        json_str = uid.canonical_json(obj)
        assert json_str == '{"outer":{"a":2,"z":1}}'


class TestHashObjStability:
    """Test that hash_obj produces stable hashes."""

    def test_simple_dict_hash(self):
        """Test hash of a simple dict."""
        obj = {"family": "mace", "model": "medium-mpa-0"}
        hash1 = uid.hash_obj(obj)
        hash2 = uid.hash_obj(obj)

        # Same object should produce same hash
        assert hash1 == hash2

        # Hash should be 64 hex characters (SHA256)
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_order_independence(self):
        """Test that dict key order doesn't affect hash."""
        obj1 = {"a": 1, "b": 2, "c": 3}
        obj2 = {"c": 3, "a": 1, "b": 2}
        obj3 = {"b": 2, "c": 3, "a": 1}

        hash1 = uid.hash_obj(obj1)
        hash2 = uid.hash_obj(obj2)
        hash3 = uid.hash_obj(obj3)

        assert hash1 == hash2 == hash3

    def test_numpy_array_hash_stability(self):
        """Test that numpy arrays hash consistently."""
        obj1 = {"arr": np.array([1.0, 2.0, 3.0])}
        obj2 = {"arr": np.array([1.0, 2.0, 3.0])}

        hash1 = uid.hash_obj(obj1)
        hash2 = uid.hash_obj(obj2)

        assert hash1 == hash2


class TestMaterialUIDStability:
    """Test material UID stability."""

    def test_material_uid_format(self):
        """Test that material UID has correct format."""
        # Create simple test structure
        from ase.build import bulk

        atoms = bulk("Al", "fcc", a=4.05)

        mat_uid = uid.material_uid_from_conv_atoms(atoms)

        # Should start with "mat:"
        assert mat_uid.startswith("mat:")

        # After prefix should be 64 hex chars
        hash_part = mat_uid[4:]
        assert len(hash_part) == 64
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_material_uid_reproducibility(self):
        """Test that same structure produces same material UID."""
        from ase.build import bulk

        atoms1 = bulk("Al", "fcc", a=4.05)
        atoms2 = bulk("Al", "fcc", a=4.05)

        uid1 = uid.material_uid_from_conv_atoms(atoms1)
        uid2 = uid.material_uid_from_conv_atoms(atoms2)

        assert uid1 == uid2

    def test_material_uid_atom_order_independence(self):
        """Test that atom order doesn't affect material UID (after sorting)."""
        from ase import Atoms

        # Create structure with two atoms in different orders
        atoms1 = Atoms(
            symbols=["Cu", "Au"],
            scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        )

        atoms2 = Atoms(
            symbols=["Au", "Cu"],
            scaled_positions=[[0.5, 0.5, 0.5], [0.0, 0.0, 0.0]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        )

        uid1 = uid.material_uid_from_conv_atoms(atoms1)
        uid2 = uid.material_uid_from_conv_atoms(atoms2)

        # After sorting by (symbol, frac_x, frac_y, frac_z), UIDs should match
        assert uid1 == uid2


class TestBulkUIDStability:
    """Test bulk UID stability."""

    def test_reference_bulk_uid_from_material(self):
        """Test reference bulk UID derivation from material UID."""
        mat_uid = "mat:abc123"
        bulk_uid = uid.reference_bulk_uid(mat_uid)

        # Should replace "mat:" with "bulk:"
        assert bulk_uid == "bulk:abc123"

    def test_reference_bulk_uid_format(self):
        """Test reference bulk UID has correct format."""
        mat_uid = "mat:" + "a" * 64
        bulk_uid = uid.reference_bulk_uid(mat_uid)

        assert bulk_uid.startswith("bulk:")
        assert len(bulk_uid) == 5 + 64  # "bulk:" + 64 hex chars


class TestSlabUIDStability:
    """Test slab UID stability."""

    def test_slab_uid_format(self):
        """Test slab UID format."""
        mat_uid = "mat:abc123"
        miller = [1, 1, 1]
        sspec_uid = "sspec:def456"

        s_uid = uid.slab_uid(material_uid=mat_uid, miller=miller, slab_spec_uid=sspec_uid)

        # Format: slab:mat:abc123:1,1,1:sspec:def456
        assert s_uid.startswith("slab:")
        assert ":1,1,1:" in s_uid
        assert mat_uid in s_uid
        assert sspec_uid in s_uid

    def test_slab_uid_miller_indices(self):
        """Test that miller indices are correctly embedded."""
        mat_uid = "mat:abc123"
        sspec_uid = "sspec:def456"

        s_uid_111 = uid.slab_uid(material_uid=mat_uid, miller=[1, 1, 1], slab_spec_uid=sspec_uid)
        s_uid_100 = uid.slab_uid(material_uid=mat_uid, miller=[1, 0, 0], slab_spec_uid=sspec_uid)

        assert ":1,1,1:" in s_uid_111
        assert ":1,0,0:" in s_uid_100
        assert s_uid_111 != s_uid_100

    def test_slab_uid_property_uses_canonical_uid_algorithm(self):
        """Test that Slab.uid delegates to the canonical slab UID algorithm."""
        pytest.importorskip("ase")

        from ase import Atoms

        from calm.bulk.bulk import Bulk
        from calm.keys.uid import material_uid_from_conv_atoms, slab_spec_uid
        from calm.slab.slab import Slab
        from calm.slab.slab import SlabSpec

        atoms = Atoms("Al", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3) * 4.05, pbc=True)

        bulk = Bulk(uid="mat:Al", atoms=atoms)
        spec = SlabSpec(miller=(1, 1, 1), n_layers=1, vacuum=8.0)
        slab = Slab(bulk, spec)

        expected = uid.slab_uid(
            material_uid=material_uid_from_conv_atoms(
                bulk.conv,
                symprec=bulk.symprec,
                no_idealize=bulk.no_idealize,
            ),
            miller=slab.hkl,
            slab_spec_uid=slab_spec_uid(spec),
        )

        assert isinstance(slab.uid, str)
        assert slab.uid.startswith("slab:")
        assert slab.uid == expected


class TestCalculatorUIDStability:
    """Test calculator UID stability."""

    def test_calculator_uid_format(self):
        """Test calculator UID format."""
        calc_spec = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}

        calc_uid = uid.calculator_uid(calc_spec)

        # Should start with "calc:"
        assert calc_uid.startswith("calc:")

        # After prefix should be 64 hex chars
        hash_part = calc_uid[5:]
        assert len(hash_part) == 64

    def test_calculator_uid_reproducibility(self):
        """Test that same spec produces same calculator UID."""
        spec1 = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}
        spec2 = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}

        uid1 = uid.calculator_uid(spec1)
        uid2 = uid.calculator_uid(spec2)

        assert uid1 == uid2

    def test_calculator_uid_key_order_independence(self):
        """Test that dict key order doesn't affect calculator UID."""
        spec1 = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}
        spec2 = {"device": "cpu", "family": "mace", "model": "medium-mpa-0"}
        spec3 = {"model": "medium-mpa-0", "device": "cpu", "family": "mace"}

        uid1 = uid.calculator_uid(spec1)
        uid2 = uid.calculator_uid(spec2)
        uid3 = uid.calculator_uid(spec3)

        assert uid1 == uid2 == uid3

    def test_calculator_uid_changes_with_spec(self):
        """Test that different specs produce different UIDs."""
        spec1 = {"family": "mace", "model": "medium-mpa-0", "device": "cpu"}
        spec2 = {"family": "mace", "model": "large", "device": "cpu"}

        uid1 = uid.calculator_uid(spec1)
        uid2 = uid.calculator_uid(spec2)

        assert uid1 != uid2


class TestBuildUIDStability:
    """Test build UID stability."""

    def test_build_uid_format(self):
        """Test build UID format."""
        strained = "strain:proto:A[...]__B[...]:smodel:abc"
        translation = [0.1, 0.2]
        z_pad = 15.0

        b_uid = uid.build_uid(strained_uid=strained, translation_frac=translation, z_padding=z_pad)

        # Format: build:strain:...:t=0.1,0.2:zp=15.0
        assert b_uid.startswith("build:")
        assert ":t=0.1,0.2:" in b_uid
        assert ":zp=15.0" in b_uid

    def test_build_uid_translation_wrapping(self):
        """Test that translations are wrapped to [0, 1)."""
        strained = "strain:test"

        # Translation > 1.0 should wrap
        b_uid1 = uid.build_uid(strained_uid=strained, translation_frac=[1.5, 0.0], z_padding=10.0)
        b_uid2 = uid.build_uid(strained_uid=strained, translation_frac=[0.5, 0.0], z_padding=10.0)

        # 1.5 wraps to 0.5
        assert ":t=0.5,0.0:" in b_uid1
        assert b_uid1 == b_uid2

    def test_build_uid_zero_threshold(self):
        """Test that tiny values become exactly 0.0."""
        strained = "strain:test"

        b_uid = uid.build_uid(
            strained_uid=strained, translation_frac=[1e-9, 1e-9], z_padding=1e-9, round_decimals=8
        )

        # Should have exact 0.0 (not 1e-9 or -0.0)
        assert ":t=0.0,0.0:" in b_uid
        assert ":zp=0.0" in b_uid


class TestWrap01Function:
    """Test the wrap01 helper function."""

    def test_wrap_positive(self):
        """Test wrapping positive values."""
        assert uid.wrap01(0.0) == 0.0
        assert uid.wrap01(0.5) == 0.5
        assert uid.wrap01(1.0) == 0.0  # 1.0 wraps to 0.0
        assert uid.wrap01(1.5) == pytest.approx(0.5)
        assert uid.wrap01(2.7) == pytest.approx(0.7)

    def test_wrap_negative(self):
        """Test wrapping negative values."""
        assert uid.wrap01(-0.5) == pytest.approx(0.5)
        assert uid.wrap01(-1.0) == 0.0
        assert uid.wrap01(-1.3) == pytest.approx(0.7, abs=1e-10)


class TestCurrentUIDContract:
    """Meta-tests for the active legacy-JSON UID contract."""

    def test_json_format_stable(self):
        """Test JSON format settings (separators, key sorting, ASCII)."""
        obj = {"b": 2, "a": 1}
        json_str = uid.canonical_json(obj)

        # Must be: {"a":1,"b":2}
        # NOT: {"a": 1, "b": 2} (has spaces)
        # NOT: {"b":2,"a":1} (wrong key order)
        assert json_str == '{"a":1,"b":2}'

    def test_default_float_decimals(self):
        """Test that default float_decimals is 12."""
        # This is implicit in all UID functions
        # Changing this would break all existing UIDs
        obj = {"val": 1.23456789012345}

        # Default should round to 12 decimals
        json_str = uid.canonical_json(obj)
        assert "1.234567890123" in json_str

    def test_uid_prefixes_stable(self):
        """Test that UID prefixes are stable."""
        # These prefixes must never change
        assert uid.material_uid_from_conv_atoms.__doc__ is not None

        # reference_bulk_uid converts "mat:" to "bulk:"
        bulk = uid.reference_bulk_uid("mat:test")
        assert bulk.startswith("bulk:")
        assert bulk == "bulk:test"

        # calculator_uid uses "calc:" prefix
        assert uid.calculator_uid({}).startswith("calc:")
