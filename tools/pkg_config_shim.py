#!/usr/bin/env python3
"""Minimal pkg-config shim for local/CI Meson builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def expand(value: str, values: dict[str, str]) -> str:
    changed = True
    while changed:
        changed = False
        for key, replacement in values.items():
            token = "${" + key + "}"
            if token in value:
                value = value.replace(token, replacement)
                changed = True
    return value


def parse_pc(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    fields: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        eq_pos = line.find("=")
        colon_pos = line.find(":")
        if eq_pos != -1 and (colon_pos == -1 or eq_pos < colon_pos):
            key, value = line.split("=", 1)
            values[key.strip()] = expand(value.strip(), values)
        elif colon_pos != -1:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return {**values, **{k: expand(v, values) for k, v in fields.items()}}


def find_pc(name: str) -> Path | None:
    paths = os.environ.get("PKG_CONFIG_PATH", "").split(os.pathsep)
    for root in paths:
        if not root:
            continue
        candidate = Path(root) / f"{name}.pc"
        if candidate.exists():
            return candidate
    candidate = Path(name)
    if candidate.exists():
        return candidate
    return None


def module_names(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-") and not a.startswith(">") and not a.startswith("<")]


def main(argv: list[str]) -> int:
    if not argv:
        return 1
    if "--version" in argv:
        print("0.29.2-shim")
        return 0

    names = module_names(argv)
    if not names:
        return 0

    pc = find_pc(names[-1])
    if not pc:
        return 1
    data = parse_pc(pc)

    if "--exists" in argv or "--print-errors" in argv:
        return 0
    if "--modversion" in argv:
        print(data.get("Version", ""))
        return 0
    for arg in argv:
        if arg.startswith("--variable="):
            print(data.get(arg.split("=", 1)[1], ""))
            return 0
    if "--cflags" in argv:
        print(data.get("Cflags", ""))
        return 0
    if "--libs" in argv:
        print(data.get("Libs", ""))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
