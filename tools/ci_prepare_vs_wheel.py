#!/usr/bin/env python3
"""Prepare normalized VapourSynth wheel metadata for Meson/pkg-config builds."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def find_vapoursynth_root() -> Path:
    spec = importlib.util.find_spec("vapoursynth")
    if spec is None or spec.origin is None:
        raise RuntimeError("vapoursynth module is not importable")
    package_dir = Path(spec.origin).resolve().parent
    include_dir = package_dir / "include"
    if include_dir.exists():
        return package_dir
    raise RuntimeError(f"vapoursynth package at {package_dir} does not contain include/")


def write_pc(out_dir: Path, package_root: Path) -> Path:
    out_pkgconfig = out_dir / "vapoursynth" / "lib" / "pkgconfig"
    out_pkgconfig.mkdir(parents=True, exist_ok=True)
    pc_path = out_pkgconfig / "vapoursynth.pc"
    pc_path.write_text(
        "\n".join(
            [
                f"prefix={package_root.as_posix()}",
                "includedir=${prefix}/include",
                "libdir=${prefix}/lib",
                "",
                "Name: vapoursynth",
                "Description: VapourSynth wheel headers for plugin builds",
                "Version: 77",
                "Cflags: -I${includedir}",
                "Libs:",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return pc_path


def write_pkg_config_shim(out_dir: Path) -> Path:
    shim = out_dir / "pkg-config.cmd"
    helper = ROOT / "tools" / "pkg_config_shim.py"
    shim.write_text(
        "@echo off\r\n"
        f"\"{sys.executable}\" \"{helper}\" %*\r\n",
        encoding="ascii",
    )
    return shim


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Prepare normalized VapourSynth wheel metadata for CI builds.")
    parser.add_argument("--out-dir", default="_deps/vapoursynth-wheel-R77", help="Output directory for metadata.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    package_root = find_vapoursynth_root()
    out_dir = Path(args.out_dir).resolve()
    pc_path = write_pc(out_dir, package_root)
    shim_path = write_pkg_config_shim(out_dir)
    result = {
        "vapoursynth_root": str(package_root),
        "pc_path": str(pc_path),
        "pkg_config_path": str(pc_path.parent),
        "pkg_config_shim": str(shim_path),
        "include_dir": str(package_root / "include"),
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
