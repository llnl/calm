"""Canonical artifact URI resolution for the project UX layer."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse


def resolve_artifact_uri(uri: str) -> Path:
    """Resolve one current absolute ``file://`` artifact URI."""

    if not isinstance(uri, str):
        raise TypeError("Artifact URI must be a string.")

    parsed = urlparse(uri.strip())
    if parsed.scheme != "file":
        raise ValueError("Current artifact URIs must use the file:// scheme.")
    if parsed.netloc:
        raise ValueError("Current artifact URIs cannot contain a file host.")
    if parsed.query or parsed.fragment:
        raise ValueError("Current artifact URIs cannot contain query or fragment data.")

    path = unquote(parsed.path)
    if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path[1:]
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError("Current file artifact URIs must contain an absolute path.")
    return resolved.resolve()
