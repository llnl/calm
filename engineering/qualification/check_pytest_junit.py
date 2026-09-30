#!/usr/bin/env python3
"""Reject unexpected skipped tests in a pytest JUnit XML report."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _node_id(testcase: ET.Element) -> str:
    file_name = testcase.get("file")
    class_name = testcase.get("classname", "")
    test_name = testcase.get("name", "")
    if file_name:
        return f"{file_name}::{test_name}"
    return f"{class_name}::{test_name}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("--allow-skipped", action="append", default=[])
    args = parser.parse_args(argv)

    root = ET.parse(args.junit_xml).getroot()
    skipped = {
        _node_id(testcase): (testcase.find("skipped").get("message", ""))
        for testcase in root.iter("testcase")
        if testcase.find("skipped") is not None
    }
    allowed = set(args.allow_skipped)
    unexpected = sorted(set(skipped) - allowed)
    missing = sorted(allowed - set(skipped))

    for node_id in sorted(skipped):
        print(f"SKIPPED {node_id}: {skipped[node_id]}")
    if unexpected:
        print("Unexpected skipped tests:", file=sys.stderr)
        for node_id in unexpected:
            print(f"  {node_id}", file=sys.stderr)
    if missing:
        print("Allowed skips that did not occur:")
        for node_id in missing:
            print(f"  {node_id}")
    return 1 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
