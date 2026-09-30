from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import IntEnum
import math

import numpy as np
import pytest

from calm.keys._canonical_v2 import (
    CANONICAL_IDENTITY_MAGIC,
    CANONICAL_IDENTITY_VERSION,
    CanonicalIdentityDomain,
    CanonicalIdentityCycleError,
    CanonicalMappingKeyCollisionError,
    InvalidCanonicalIdentityDomainError,
    InvalidCanonicalStringError,
    NonFiniteCanonicalValueError,
    UnsupportedCanonicalMappingKeyError,
    UnsupportedCanonicalTypeError,
    canonical_identity_bytes_v2,
    canonical_identity_digest_v2,
)


SCIENTIFIC = CanonicalIdentityDomain.SCIENTIFIC_IDENTITY


@pytest.mark.parametrize(
    ("value", "expected_hex"),
    [
        (None, "43414c4d2d4349440000020013736369656e74696669635f6964656e7469747900000000000000016e"),
        (False, "43414c4d2d4349440000020013736369656e74696669635f6964656e7469747900000000000000026200"),
        (True, "43414c4d2d4349440000020013736369656e74696669635f6964656e7469747900000000000000026201"),
        (0, "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000000a69000000000000000130"),
        (-17, "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000000c6900000000000000032d3137"),
        (1.5, "43414c4d2d4349440000020013736369656e74696669635f6964656e746974790000000000000009663ff8000000000000"),
        ("α", "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000000b730000000000000002ceb1"),
        (b"\x00\xff", "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000000b79000000000000000200ff"),
        ([1, "1"], "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000001d6c00000000000000026900000000000000013173000000000000000131"),
        ((1, "1"), "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000001d7400000000000000026900000000000000013173000000000000000131"),
    ],
)
def test_scalar_and_sequence_golden_vectors(value: object, expected_hex: str) -> None:
    assert canonical_identity_bytes_v2(value, domain=SCIENTIFIC).hex() == expected_hex


def test_composite_mapping_and_array_golden_vectors() -> None:
    mapping = {"z": 1, 2: "two", ("a", 1): True}
    array = np.array([[1, -2], [3, 4]], dtype=np.int32)

    assert canonical_identity_bytes_v2(mapping, domain=SCIENTIFIC).hex() == "43414c4d2d4349440000020013736369656e74696669635f6964656e7469747900000000000000526d00000000000000036900000000000000013273000000000000000374776f7300000000000000017a6900000000000000013174000000000000000273000000000000000161690000000000000001316201"
    assert canonical_identity_bytes_v2(array, domain=SCIENTIFIC).hex() == "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479000000000000003b6100000000000000026934000000000000000200000000000000020000000000000002000000000000001000000001fffffffe0000000300000004"


def test_float32_array_golden_vector() -> None:
    array = np.array([0.0, -1.5, 2.25], dtype=np.float32)
    assert canonical_identity_bytes_v2(array, domain=SCIENTIFIC).hex() == (
        "43414c4d2d4349440000020013736369656e74696669635f6964656e74697479"
        "000000000000002f610000000000000002663400000000000000010000000000"
        "000003000000000000000c00000000bfc0000040100000"
    )


def test_envelope_and_digest_are_exact_and_reconstructible() -> None:
    encoded = canonical_identity_bytes_v2({"a": 1}, domain=SCIENTIFIC)
    digest = canonical_identity_digest_v2({"a": 1}, domain=SCIENTIFIC)

    assert encoded.startswith(CANONICAL_IDENTITY_MAGIC + b"\x00\x02")
    assert CANONICAL_IDENTITY_VERSION == 2
    assert len(digest) == 64
    assert digest == "3a4335473c69c42b9d1abedac9ea22db4fdabd4ae9dc5967907c08830f16dbd3"


def test_declared_domains_are_separate_and_cross_substitution_is_forbidden() -> None:
    payload = {"value": 1}
    encodings = {
        domain: canonical_identity_bytes_v2(payload, domain=domain)
        for domain in CanonicalIdentityDomain
    }
    digests = {
        domain: canonical_identity_digest_v2(payload, domain=domain)
        for domain in CanonicalIdentityDomain
    }

    assert len(set(encodings.values())) == len(CanonicalIdentityDomain)
    assert len(set(digests.values())) == len(CanonicalIdentityDomain)
    assert {domain.value: digest for domain, digest in digests.items()} == {
        "scientific_identity": (
            "67798ff3ef7b2be6b424aee172ef8385a10036aee7334f5842705a65e83d27c6"
        ),
        "application_identity": (
            "dd5ca29d9dcdd1640b0b01055360e0a086caa8960d08e17d161bbef1bdc309bb"
        ),
        "regression_signature": (
            "c736b554db2f41c39a8325b651e807a2250eeb24e6aac30f11b41708aea7a6eb"
        ),
        "group_identity": (
            "bd4fffc45bdb5dc82c5efad7bc31cda827b368b4e4a2b12d3051620c040ab170"
        ),
        "dataset_declaration": (
            "eb092a0171ea985e902cd57d70153807da4e9d6e871cd03049283400c2805c31"
        ),
        "campaign_identity": (
            "05302288c39129db52460ef4e703970f738c01ef84c1db4eb145d88fdbf67292"
        ),
        "content_fingerprint": (
            "5ed9019c2b2a63411b5bfc957881d25a69106a07077e1fc4032ff3b2838fca6f"
        ),
        "numerical_grouping": (
            "f2d9994ae1fc27b3e4afb7e73ab47b90a290b6b184405ebbc1888346317c393f"
        ),
    }


def test_invalid_domain_is_rejected_instead_of_becoming_an_ad_hoc_namespace() -> None:
    with pytest.raises(InvalidCanonicalIdentityDomainError):
        canonical_identity_bytes_v2(1, domain="scientific")
    with pytest.raises(InvalidCanonicalIdentityDomainError):
        canonical_identity_bytes_v2(1, domain=1)  # type: ignore[arg-type]


def test_type_tags_prevent_v1_coercion_collisions() -> None:
    pairs = [
        (1, "1"),
        (True, 1),
        (1, 1.0),
        ([1, 2], (1, 2)),
        ((1, 2), "(1, 2)"),
        ([1, 2], np.array([1, 2], dtype=np.int64)),
        ({1: "x"}, {"1": "x"}),
        ({True: "x"}, {1: "x"}),
    ]
    for left, right in pairs:
        assert canonical_identity_bytes_v2(left, domain=SCIENTIFIC) != (
            canonical_identity_bytes_v2(right, domain=SCIENTIFIC)
        )


def test_mapping_order_is_canonical_and_keys_use_encoded_byte_order() -> None:
    left = {"z": 0, 2: "two", b"a": 3, (1, "x"): 4}
    right = {(1, "x"): 4, b"a": 3, 2: "two", "z": 0}

    assert canonical_identity_bytes_v2(left, domain=SCIENTIFIC) == (
        canonical_identity_bytes_v2(right, domain=SCIENTIFIC)
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_python_floats_are_rejected(value: float) -> None:
    with pytest.raises(NonFiniteCanonicalValueError):
        canonical_identity_bytes_v2(value, domain=SCIENTIFIC)


def test_unpaired_unicode_surrogates_are_rejected() -> None:
    with pytest.raises(InvalidCanonicalStringError):
        canonical_identity_bytes_v2("\ud800", domain=SCIENTIFIC)
    with pytest.raises(InvalidCanonicalStringError):
        canonical_identity_bytes_v2({"\ud800": 1}, domain=SCIENTIFIC)


def test_negative_zero_is_normalized_without_implicit_decimal_rounding() -> None:
    assert canonical_identity_bytes_v2(-0.0, domain=SCIENTIFIC) == (
        canonical_identity_bytes_v2(0.0, domain=SCIENTIFIC)
    )
    assert canonical_identity_bytes_v2(1.0, domain=SCIENTIFIC) != (
        canonical_identity_bytes_v2(np.nextafter(1.0, 2.0), domain=SCIENTIFIC)
    )


def test_supported_numpy_scalars_normalize_to_python_scalars() -> None:
    equivalent_pairs = [
        (np.bool_(True), True),
        (np.int8(-3), -3),
        (np.uint64(5), 5),
        (np.float16(1.5), 1.5),
        (np.float32(1.5), 1.5),
        (np.float64(1.5), 1.5),
        (np.str_("α"), "α"),
        (np.bytes_(b"ab"), b"ab"),
    ]
    for numpy_value, python_value in equivalent_pairs:
        assert canonical_identity_bytes_v2(numpy_value, domain=SCIENTIFIC) == (
            canonical_identity_bytes_v2(python_value, domain=SCIENTIFIC)
        )


@pytest.mark.parametrize(
    "value",
    [np.complex64(1 + 2j), np.datetime64("2026-07-23"), np.timedelta64(1, "D")],
)
def test_unsupported_numpy_scalars_are_rejected(value: np.generic) -> None:
    with pytest.raises(UnsupportedCanonicalTypeError):
        canonical_identity_bytes_v2(value, domain=SCIENTIFIC)


def test_all_value_node_tags_are_distinct() -> None:
    values = [
        None,
        False,
        0,
        0.0,
        "",
        b"",
        [],
        (),
        {},
        np.array([], dtype=np.int8),
    ]
    encodings = [
        canonical_identity_bytes_v2(value, domain=SCIENTIFIC)
        for value in values
    ]
    assert len(set(encodings)) == len(values)


def test_array_dtype_and_shape_are_identity_bearing() -> None:
    values = np.array([1, 2, 3, 4])
    int32 = values.astype(np.int32)
    int64 = values.astype(np.int64)
    matrix = values.astype(np.int32).reshape(2, 2)

    assert canonical_identity_bytes_v2(int32, domain=SCIENTIFIC) != (
        canonical_identity_bytes_v2(int64, domain=SCIENTIFIC)
    )
    assert canonical_identity_bytes_v2(int32, domain=SCIENTIFIC) != (
        canonical_identity_bytes_v2(matrix, domain=SCIENTIFIC)
    )


def test_array_byte_order_and_physical_memory_order_are_not_identity_bearing() -> None:
    logical = np.array([[1, 2], [3, 4]], dtype=np.int32)
    little = logical.astype("<i4")
    big = logical.astype(">i4")
    fortran = np.asfortranarray(logical)

    expected = canonical_identity_bytes_v2(logical, domain=SCIENTIFIC)
    assert canonical_identity_bytes_v2(little, domain=SCIENTIFIC) == expected
    assert canonical_identity_bytes_v2(big, domain=SCIENTIFIC) == expected
    assert canonical_identity_bytes_v2(fortran, domain=SCIENTIFIC) == expected

    float_values = np.array([[0.5, -1.25], [2.0, 3.5]], dtype=np.float32)
    float_expected = canonical_identity_bytes_v2(float_values, domain=SCIENTIFIC)
    assert canonical_identity_bytes_v2(
        float_values.astype("<f4"), domain=SCIENTIFIC
    ) == float_expected
    assert canonical_identity_bytes_v2(
        float_values.astype(">f4"), domain=SCIENTIFIC
    ) == float_expected
    assert canonical_identity_bytes_v2(
        np.asfortranarray(float_values), domain=SCIENTIFIC
    ) == float_expected


def test_float_arrays_reject_nonfinite_values_and_normalize_negative_zero() -> None:
    positive_zero = np.array([0.0, 1.0], dtype=np.float32)
    negative_zero = np.array([-0.0, 1.0], dtype=np.float32)
    assert canonical_identity_bytes_v2(positive_zero, domain=SCIENTIFIC) == (
        canonical_identity_bytes_v2(negative_zero, domain=SCIENTIFIC)
    )

    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(NonFiniteCanonicalValueError):
            canonical_identity_bytes_v2(
                np.array([value], dtype=np.float64), domain=SCIENTIFIC
            )


def test_fixed_width_string_array_dtypes_are_preserved() -> None:
    bytes2 = np.array([b"a", b"bc"], dtype="S2")
    bytes3 = np.array([b"a", b"bc"], dtype="S3")
    unicode2 = np.array(["α", "b"], dtype="U2")
    unicode3 = np.array(["α", "b"], dtype="U3")

    assert canonical_identity_bytes_v2(bytes2, domain=SCIENTIFIC) != (
        canonical_identity_bytes_v2(bytes3, domain=SCIENTIFIC)
    )
    assert canonical_identity_bytes_v2(unicode2, domain=SCIENTIFIC) != (
        canonical_identity_bytes_v2(unicode3, domain=SCIENTIFIC)
    )


@pytest.mark.parametrize(
    "array",
    [
        np.array([object()], dtype=object),
        np.array([1 + 2j], dtype=np.complex128),
        np.array(["2026-07-23"], dtype="datetime64[D]"),
        np.array([(1, 2.0)], dtype=[("a", "i4"), ("b", "f8")]),
    ],
)
def test_unsupported_array_dtypes_are_rejected(array: np.ndarray) -> None:
    with pytest.raises(UnsupportedCanonicalTypeError):
        canonical_identity_bytes_v2(array, domain=SCIENTIFIC)


class ExampleArray(np.ndarray):
    pass


def test_ndarray_subclasses_require_explicit_conversion() -> None:
    subclass = np.array([[1, 2], [3, 4]], dtype=np.int64).view(ExampleArray)
    with pytest.raises(UnsupportedCanonicalTypeError):
        canonical_identity_bytes_v2(subclass, domain=SCIENTIFIC)
    canonical_identity_bytes_v2(np.asarray(subclass), domain=SCIENTIFIC)


@dataclass
class ExampleDataclass:
    value: int


class ExampleIntEnum(IntEnum):
    ONE = 1


class ExampleInt(int):
    pass


@pytest.mark.parametrize(
    "value",
    [ExampleDataclass(1), ExampleIntEnum.ONE, ExampleInt(1), {1, 2}, frozenset({1, 2}), range(3), bytearray(b"x"), 1j],
)
def test_unsupported_objects_are_rejected_without_string_fallback(value: object) -> None:
    with pytest.raises(UnsupportedCanonicalTypeError):
        canonical_identity_bytes_v2(value, domain=SCIENTIFIC)


def test_unsupported_mapping_key_is_rejected() -> None:
    with pytest.raises(UnsupportedCanonicalMappingKeyError):
        canonical_identity_bytes_v2({frozenset({1}): "x"}, domain=SCIENTIFIC)


class DuplicateCanonicalKeyMapping(Mapping[object, str]):
    def __getitem__(self, key: object) -> str:
        return "x"

    def __iter__(self) -> Iterator[object]:
        yield np.int64(1)
        yield 1

    def __len__(self) -> int:
        return 2


def test_mapping_rejects_distinct_keys_with_identical_canonical_bytes() -> None:
    with pytest.raises(CanonicalMappingKeyCollisionError):
        canonical_identity_bytes_v2(
            DuplicateCanonicalKeyMapping(), domain=SCIENTIFIC
        )


def test_cyclic_containers_are_rejected_deterministically() -> None:
    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)
    cyclic_mapping: dict[str, object] = {}
    cyclic_mapping["self"] = cyclic_mapping

    for value in (cyclic_list, cyclic_mapping):
        with pytest.raises(CanonicalIdentityCycleError):
            canonical_identity_bytes_v2(value, domain=SCIENTIFIC)


def test_historical_scientific_and_regression_serializers_remain_distinct() -> None:
    from calm.keys.uid import canonical_json, hash_obj
    from calm.serialization.regression import deterministic_json, fingerprint_json

    payload = {"symbol": "α", "values": (1, 2)}

    assert canonical_json(payload) == r'{"symbol":"\u03b1","values":[1,2]}'
    assert deterministic_json(payload) == r'{"symbol":"\u03b1","values":[1,2]}'
    assert hash_obj(payload) == (
        "9db139895766804903a51829161347bc1c2cbe5cb5dde0e042500b50112a49ad"
    )
    assert fingerprint_json(payload) == (
        "9db139895766804903a51829161347bc1c2cbe5cb5dde0e042500b50112a49ad"
    )
    assert hash_obj(payload) != canonical_identity_digest_v2(
        payload, domain=CanonicalIdentityDomain.SCIENTIFIC_IDENTITY
    )
    assert fingerprint_json(payload) != canonical_identity_digest_v2(
        payload, domain=CanonicalIdentityDomain.REGRESSION_SIGNATURE
    )
