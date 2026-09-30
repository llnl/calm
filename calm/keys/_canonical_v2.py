"""Version-2 canonical bytes for explicitly separated identity domains.

This module defines the serialization contract only.  Existing UID and
regression-signature helpers retain their historical version-1 behavior until
callers opt into a named version-2 domain and persisted identifiers are
migrated explicitly.
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping
from enum import Enum
from typing import Any

import numpy as np


CANONICAL_IDENTITY_VERSION = 2
CANONICAL_IDENTITY_MAGIC = b"CALM-CID\x00"


class CanonicalIdentityDomain(str, Enum):
    """Named non-interchangeable uses of canonical serialization."""

    SCIENTIFIC_IDENTITY = "scientific_identity"
    APPLICATION_IDENTITY = "application_identity"
    REGRESSION_SIGNATURE = "regression_signature"
    GROUP_IDENTITY = "group_identity"
    DATASET_DECLARATION = "dataset_declaration"
    CAMPAIGN_IDENTITY = "campaign_identity"
    CONTENT_FINGERPRINT = "content_fingerprint"
    NUMERICAL_GROUPING = "numerical_grouping"


class CanonicalIdentityError(ValueError):
    """Base error for invalid version-2 canonical identity payloads."""


class InvalidCanonicalIdentityDomainError(CanonicalIdentityError):
    """The requested identity domain is not one of the frozen domain names."""


class NonFiniteCanonicalValueError(CanonicalIdentityError):
    """A scalar or array contains NaN or positive or negative infinity."""


class InvalidCanonicalStringError(CanonicalIdentityError):
    """A string cannot be represented as valid UTF-8 bytes."""


class UnsupportedCanonicalTypeError(TypeError):
    """A payload value has no version-2 canonical encoding."""


class UnsupportedCanonicalMappingKeyError(TypeError):
    """A mapping key is not in the explicitly supported key grammar."""


class CanonicalMappingKeyCollisionError(CanonicalIdentityError):
    """Distinct input keys collapse to the same canonical key bytes."""


class CanonicalIdentityCycleError(CanonicalIdentityError):
    """A list, tuple, or mapping contains a recursive reference."""


# All variable lengths and container counts inside the value grammar are
# unsigned 64-bit big-endian integers.  The envelope uses a uint16 version and
# domain length followed by a uint64 body length.
_U16 = struct.Struct(">H")
_U64 = struct.Struct(">Q")
_FLOAT64 = struct.Struct(">d")

_TAG_NONE = b"n"
_TAG_BOOL = b"b"
_TAG_INT = b"i"
_TAG_FLOAT = b"f"
_TAG_STRING = b"s"
_TAG_BYTES = b"y"
_TAG_LIST = b"l"
_TAG_TUPLE = b"t"
_TAG_MAPPING = b"m"
_TAG_ARRAY = b"a"

_SUPPORTED_NUMERIC_ITEM_SIZES = frozenset({1, 2, 4, 8})
_SUPPORTED_FLOAT_ITEM_SIZES = frozenset({2, 4, 8})


def _pack_u16(value: int, *, field: str) -> bytes:
    if value < 0 or value > 0xFFFF:
        raise CanonicalIdentityError(f"{field} does not fit uint16: {value}.")
    return _U16.pack(value)


def _pack_u64(value: int, *, field: str) -> bytes:
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise CanonicalIdentityError(f"{field} does not fit uint64: {value}.")
    return _U64.pack(value)


def _length_prefixed(payload: bytes, *, field: str) -> bytes:
    return _pack_u64(len(payload), field=f"{field} length") + payload


def _encode_utf8(value: str, *, field: str) -> bytes:
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InvalidCanonicalStringError(
            f"{field} must be encodable as valid UTF-8."
        ) from exc


def _canonical_domain(domain: CanonicalIdentityDomain | str) -> CanonicalIdentityDomain:
    if isinstance(domain, CanonicalIdentityDomain):
        return domain
    if isinstance(domain, str):
        try:
            return CanonicalIdentityDomain(domain)
        except ValueError as exc:
            raise InvalidCanonicalIdentityDomainError(
                f"Unsupported canonical identity domain: {domain!r}."
            ) from exc
    raise InvalidCanonicalIdentityDomainError(
        "Canonical identity domain must be a CanonicalIdentityDomain or its exact "
        f"string value, got {type(domain).__name__}."
    )


def _normalize_numpy_scalar(value: np.generic) -> Any:
    dtype = value.dtype
    kind = dtype.kind
    if kind == "b":
        return bool(value)
    if kind in {"i", "u"}:
        return int(value)
    if kind == "f":
        if dtype.itemsize not in _SUPPORTED_FLOAT_ITEM_SIZES:
            raise UnsupportedCanonicalTypeError(
                "Only NumPy float16, float32, and float64 scalars are supported; "
                f"got dtype {dtype}."
            )
        return float(value)
    if kind == "U":
        return str(value)
    if kind == "S":
        return bytes(value)
    raise UnsupportedCanonicalTypeError(
        f"NumPy scalar dtype {dtype} has no canonical version-2 encoding."
    )


def _encode_float(value: float) -> bytes:
    if not math.isfinite(value):
        raise NonFiniteCanonicalValueError("Canonical identity floats must be finite.")
    normalized = 0.0 if value == 0.0 else value
    return _TAG_FLOAT + _FLOAT64.pack(normalized)


def _array_dtype_and_payload(array: np.ndarray) -> tuple[bytes, bytes]:
    dtype = array.dtype
    if dtype.hasobject:
        raise UnsupportedCanonicalTypeError(
            "Object-dtype arrays have no canonical version-2 encoding."
        )
    if dtype.fields is not None:
        raise UnsupportedCanonicalTypeError(
            "Structured arrays have no canonical version-2 encoding."
        )
    if dtype.subdtype is not None:
        raise UnsupportedCanonicalTypeError(
            "Subarray dtypes have no canonical version-2 encoding."
        )

    kind = dtype.kind
    itemsize = int(dtype.itemsize)
    if kind == "b":
        token = b"bool"
        payload = np.asarray(array, dtype=np.uint8, order="C").tobytes(order="C")
        return token, payload

    if kind in {"i", "u"}:
        if itemsize not in _SUPPORTED_NUMERIC_ITEM_SIZES:
            raise UnsupportedCanonicalTypeError(
                f"Integer array dtype {dtype} has unsupported item size {itemsize}."
            )
        token = f"{kind}{itemsize}".encode("ascii")
        target = np.dtype(f">{kind}{itemsize}")
        payload = np.asarray(array, dtype=target, order="C").tobytes(order="C")
        return token, payload

    if kind == "f":
        if itemsize not in _SUPPORTED_FLOAT_ITEM_SIZES:
            raise UnsupportedCanonicalTypeError(
                f"Floating array dtype {dtype} has unsupported item size {itemsize}."
            )
        if not bool(np.all(np.isfinite(array))):
            raise NonFiniteCanonicalValueError(
                "Canonical identity arrays must not contain NaN or infinity."
            )
        token = f"f{itemsize}".encode("ascii")
        native = np.array(array, dtype=np.dtype(f"f{itemsize}"), order="C", copy=True)
        native[native == 0] = 0.0
        target = np.dtype(f">f{itemsize}")
        payload = native.astype(target, copy=False).tobytes(order="C")
        return token, payload

    if kind == "S":
        token = f"S{itemsize}".encode("ascii")
        payload = np.asarray(array, order="C").tobytes(order="C")
        return token, payload

    if kind == "U":
        if itemsize % 4 != 0:
            raise UnsupportedCanonicalTypeError(
                f"Unicode array dtype {dtype} has invalid item size {itemsize}."
            )
        token = f"U{itemsize // 4}".encode("ascii")
        chunks = []
        for item in np.asarray(array).ravel(order="C"):
            encoded = _encode_utf8(str(item), field="unicode array element")
            chunks.append(_length_prefixed(encoded, field="unicode array element"))
        return token, b"".join(chunks)

    raise UnsupportedCanonicalTypeError(
        f"NumPy array dtype {dtype} has no canonical version-2 encoding."
    )


def _encode_array(value: np.ndarray) -> bytes:
    array = np.asarray(value)
    dtype_token, payload = _array_dtype_and_payload(array)
    shape = tuple(int(dimension) for dimension in array.shape)
    return b"".join(
        [
            _TAG_ARRAY,
            _length_prefixed(dtype_token, field="array dtype token"),
            _pack_u64(len(shape), field="array rank"),
            *(_pack_u64(dimension, field="array dimension") for dimension in shape),
            _length_prefixed(payload, field="array payload"),
        ]
    )


def _encode_mapping_key(value: Any) -> bytes:
    if isinstance(value, np.generic):
        value = _normalize_numpy_scalar(value)
    if value is None or type(value) in {bool, int, float, str, bytes}:
        return _encode_value(value)
    if type(value) is tuple:
        return (
            _TAG_TUPLE
            + _pack_u64(len(value), field="mapping-key tuple count")
            + b"".join(_encode_mapping_key(item) for item in value)
        )
    raise UnsupportedCanonicalMappingKeyError(
        "Canonical mapping keys must be None, bool, int, finite float, string, "
        "bytes, a tuple of supported keys, or a supported NumPy scalar; got "
        f"{type(value).__name__}."
    )


def _encode_mapping(
    value: Mapping[Any, Any],
    *,
    active_containers: set[int],
) -> bytes:
    encoded_items: list[tuple[bytes, bytes]] = []
    seen_keys: set[bytes] = set()
    for key, item in value.items():
        encoded_key = _encode_mapping_key(key)
        if encoded_key in seen_keys:
            raise CanonicalMappingKeyCollisionError(
                "Distinct mapping keys collapse to the same canonical bytes."
            )
        seen_keys.add(encoded_key)
        encoded_items.append(
            (
                encoded_key,
                _encode_value(item, active_containers=active_containers),
            )
        )
    encoded_items.sort(key=lambda pair: pair[0])
    return (
        _TAG_MAPPING
        + _pack_u64(len(encoded_items), field="mapping item count")
        + b"".join(key + item for key, item in encoded_items)
    )


def _encode_value(
    value: Any,
    *,
    active_containers: set[int] | None = None,
) -> bytes:
    if active_containers is None:
        active_containers = set()

    if isinstance(value, np.generic):
        value = _normalize_numpy_scalar(value)

    if value is None:
        return _TAG_NONE
    if type(value) is bool:
        return _TAG_BOOL + (b"\x01" if value else b"\x00")
    if type(value) is int:
        payload = str(value).encode("ascii")
        return _TAG_INT + _length_prefixed(payload, field="integer")
    if type(value) is float:
        return _encode_float(value)
    if type(value) is str:
        payload = _encode_utf8(value, field="string")
        return _TAG_STRING + _length_prefixed(payload, field="string")
    if type(value) is bytes:
        return _TAG_BYTES + _length_prefixed(value, field="bytes")
    if type(value) is np.ndarray:
        return _encode_array(value)

    if type(value) is list:
        container_id = id(value)
        if container_id in active_containers:
            raise CanonicalIdentityCycleError(
                "Canonical identity payloads must not contain cyclic lists."
            )
        active_containers.add(container_id)
        try:
            return (
                _TAG_LIST
                + _pack_u64(len(value), field="list item count")
                + b"".join(
                    _encode_value(item, active_containers=active_containers)
                    for item in value
                )
            )
        finally:
            active_containers.remove(container_id)

    if type(value) is tuple:
        container_id = id(value)
        if container_id in active_containers:
            raise CanonicalIdentityCycleError(
                "Canonical identity payloads must not contain cyclic tuples."
            )
        active_containers.add(container_id)
        try:
            return (
                _TAG_TUPLE
                + _pack_u64(len(value), field="tuple item count")
                + b"".join(
                    _encode_value(item, active_containers=active_containers)
                    for item in value
                )
            )
        finally:
            active_containers.remove(container_id)

    if isinstance(value, Mapping):
        container_id = id(value)
        if container_id in active_containers:
            raise CanonicalIdentityCycleError(
                "Canonical identity payloads must not contain cyclic mappings."
            )
        active_containers.add(container_id)
        try:
            return _encode_mapping(value, active_containers=active_containers)
        finally:
            active_containers.remove(container_id)

    raise UnsupportedCanonicalTypeError(
        "Canonical identity serialization does not use str() or repr() fallbacks; "
        f"unsupported value type: {type(value).__name__}."
    )


def canonical_identity_bytes_v2(
    value: Any,
    *,
    domain: CanonicalIdentityDomain | str,
) -> bytes:
    """Encode one value under the exact version-2 identity byte contract."""

    canonical_domain = _canonical_domain(domain)
    domain_bytes = canonical_domain.value.encode("ascii")
    body = _encode_value(value)
    return b"".join(
        [
            CANONICAL_IDENTITY_MAGIC,
            _pack_u16(CANONICAL_IDENTITY_VERSION, field="schema version"),
            _pack_u16(len(domain_bytes), field="domain length"),
            domain_bytes,
            _pack_u64(len(body), field="body length"),
            body,
        ]
    )


def canonical_identity_digest_v2(
    value: Any,
    *,
    domain: CanonicalIdentityDomain | str,
) -> str:
    """Return SHA-256 over :func:`canonical_identity_bytes_v2`."""

    encoded = canonical_identity_bytes_v2(value, domain=domain)
    return hashlib.sha256(encoded).hexdigest()
