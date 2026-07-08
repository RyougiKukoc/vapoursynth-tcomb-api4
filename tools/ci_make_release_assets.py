#!/usr/bin/env python3
"""Create release-ready TComb assets from the built package directory and wheel."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "tcomb"
DEFAULT_ZIP_NAME = "tcomb-msys2-ucrt64.zip"


def create_package_zip(package_dir: Path, out_path: Path) -> None:
    if not package_dir.is_dir():
        raise FileNotFoundError(f"missing package directory: {package_dir}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(package_dir.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = f"{package_dir.name}/{file_path.relative_to(package_dir).as_posix()}"
            zf.write(file_path, arcname)


def copy_wheels(wheel_dir: Path, out_dir: Path) -> list[Path]:
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise FileNotFoundError(f"no wheels found under {wheel_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for wheel in wheels:
        destination = out_dir / wheel.name
        shutil.copy2(wheel, destination)
        copied.append(destination)
    return copied


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Create release-ready TComb zip and wheel assets.")
    parser.add_argument("--package-dir", default="dist/msys2-ucrt64/tcomb", help="Built plugin package directory.")
    parser.add_argument("--wheel-dir", default="dist/wheels", help="Directory containing built wheels.")
    parser.add_argument("--out-dir", default="dist/release-assets", help="Output directory for release assets.")
    parser.add_argument("--zip-name", default=DEFAULT_ZIP_NAME, help="Release zip filename.")
    parser.add_argument("--clean", action="store_true", help="Remove the output directory first.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    package_dir = (ROOT / args.package_dir).resolve()
    wheel_dir = (ROOT / args.wheel_dir).resolve()
    out_dir = (ROOT / args.out_dir).resolve()

    if args.clean:
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_path = out_dir / args.zip_name
    create_package_zip(package_dir, zip_path)
    wheel_paths = copy_wheels(wheel_dir, out_dir)

    result = {
        "out_dir": str(out_dir),
        "package_dir": str(package_dir),
        "zip": str(zip_path),
        "wheels": [str(path) for path in wheel_paths],
        "asset_count": 1 + len(wheel_paths),
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
