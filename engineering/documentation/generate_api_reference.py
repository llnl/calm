"""Generate virtual API reference pages during the MkDocs build."""

from __future__ import annotations

from pathlib import Path
import sys

import mkdocs_gen_files

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from api_reference_manifest import rendered_pages  # noqa: E402


for relative, content in rendered_pages().items():
    with mkdocs_gen_files.open(relative.as_posix(), "w") as stream:
        stream.write(content)
