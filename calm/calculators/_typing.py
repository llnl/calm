"""Type definitions for CALM calculator interfaces.

This module centralizes lightweight typing aliases used by the calculator
subpackage. It intentionally avoids heavy imports so it can be imported by
type-checkers without pulling runtime dependencies.

The aliases are:

- ``JsonPrimitive``: a JSON primitive value type.
- ``JsonValue``: recursive JSON value supporting mappings and sequences.
- ``JsonDict``: a mapping with string keys and JSON-compatible values.
"""

from __future__ import annotations

from typing import Mapping, Sequence, TypeAlias, Union

JsonPrimitive: TypeAlias = Union[None, bool, int, float, str]
JsonValue: TypeAlias = Union[
    JsonPrimitive, Mapping[str, "JsonValue"], Sequence["JsonValue"]
]
JsonDict: TypeAlias = dict[str, JsonValue]
