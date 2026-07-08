#!/usr/bin/env python3
"""Build and package the TComb plugin for Windows CI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "tcomb"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def prepend_path_entries(env: dict[str, str], entries: list[Path]) -> None:
    parts = [str(entry) for entry in entries if entry.exists()]
    if not parts:
        return
    existing = env.get("PATH")
    env["PATH"] = os.pathsep.join(parts + ([existing] if existing else []))


def configure_windows_build_env(env: dict[str, str]) -> dict[str, str]:
    if os.name != "nt":
        return env

    msystem_prefix = env.get("MSYSTEM_PREFIX")
    path_entries: list[Path] = []

    vs_wheel_dir = ROOT / "_deps" / "vapoursynth-wheel-R77"
    if vs_wheel_dir.exists():
        path_entries.append(vs_wheel_dir)

    if msystem_prefix:
        prefix_path = Path(msystem_prefix)
        path_entries.append(prefix_path / "bin")
        path_entries.append(prefix_path.parent / "usr" / "bin")
    else:
        path_entries.extend([Path(r"C:\msys64\ucrt64\bin"), Path(r"C:\msys64\usr\bin")])

    prepend_path_entries(env, path_entries)

    if "PKG_CONFIG" not in env:
        pkg_config_shim = vs_wheel_dir / "pkg-config.cmd"
        if pkg_config_shim.exists():
            env["PKG_CONFIG"] = str(pkg_config_shim)
    if "PKG_CONFIG_PATH" not in env:
        pkg_config_path = vs_wheel_dir / "vapoursynth" / "lib" / "pkgconfig"
        if pkg_config_path.exists():
            env["PKG_CONFIG_PATH"] = str(pkg_config_path)

    path_value = env.get("PATH")
    if "CC" not in env and shutil.which("gcc", path=path_value):
        env["CC"] = "gcc"
    return env


def meson_command(meson_python: str | None, meson_exe: str | None) -> list[str]:
    if meson_exe:
        return [meson_exe]
    meson = find_command("meson")
    if meson:
        return [meson]
    python_candidates = []
    if meson_python:
        python_candidates.append(meson_python)
    python_candidates.append(sys.executable)
    for candidate in python_candidates:
        for module_name in ("mesonbuild", "mesonbuild.mesonmain"):
            module_runner = [candidate, "-m", module_name]
            probe = subprocess.run(module_runner + ["--version"], cwd=ROOT, capture_output=True, text=True)
            if probe.returncode == 0:
                return module_runner
    raise FileNotFoundError("meson executable not found and python -m mesonbuild is unavailable")


def find_built_plugin(build_dir: Path) -> Path:
    for candidate in [build_dir / f"{PLUGIN_NAME}.dll", build_dir / f"lib{PLUGIN_NAME}.dll"]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"missing built plugin under {build_dir}")


def package_plugin(build_dir: Path, dist_dir: Path) -> dict[str, str]:
    plugin_dll = find_built_plugin(build_dir)

    package_dir = dist_dir / PLUGIN_NAME
    package_dir.mkdir(parents=True, exist_ok=True)
    packaged_plugin = package_dir / f"{PLUGIN_NAME}.dll"
    shutil.copy2(plugin_dll, packaged_plugin)
    manifest = package_dir / "manifest.vs"
    manifest.write_text(
        "[VapourSynth Manifest V1]\n"
        f"{PLUGIN_NAME}\n",
        encoding="utf-8",
    )
    return {
        "plugin_dll": str(packaged_plugin),
        "package_dir": str(package_dir),
        "manifest": str(manifest),
    }


def build_wheel(wheel_dir: Path, *, python_exe: str | None, env: dict[str, str]) -> Path:
    python_cmd = python_exe or sys.executable
    wheel_dir.mkdir(parents=True, exist_ok=True)
    run([python_cmd, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_dir)], env=env)
    wheels = sorted(wheel_dir.glob("*.whl"))
    if not wheels:
        raise FileNotFoundError(f"no wheel produced under {wheel_dir}")
    return wheels[-1]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build TComb with Meson and package the artifact.")
    parser.add_argument("--build-dir", default="build-ci-msys2", help="Meson build directory.")
    parser.add_argument("--dist-dir", default="dist/msys2-ucrt64", help="Packaged artifact directory.")
    parser.add_argument("--meson-exe", help="Path to a meson executable.")
    parser.add_argument("--meson-python", help="Python executable that has mesonbuild installed.")
    parser.add_argument("--build-python", help="Python executable used for python -m build.")
    parser.add_argument("--clean", action="store_true", help="Remove previous build/dist directories first.")
    parser.add_argument("--wheel", action="store_true", help="Build a wheel in addition to the package directory.")
    parser.add_argument("--wheel-dir", default="dist/wheels", help="Output directory for built wheels.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    build_dir = (ROOT / args.build_dir).resolve()
    dist_dir = (ROOT / args.dist_dir).resolve()
    wheel_dir = (ROOT / args.wheel_dir).resolve()

    if args.clean:
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(dist_dir, ignore_errors=True)
        shutil.rmtree(wheel_dir, ignore_errors=True)

    build_dir.parent.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    meson = meson_command(args.meson_python, args.meson_exe)
    env = configure_windows_build_env(os.environ.copy())
    run(meson + ["setup", str(build_dir), "--wipe"], env=env)
    run(meson + ["compile", "-C", str(build_dir)], env=env)

    package_info = package_plugin(build_dir, dist_dir)
    result = {
        "build_dir": str(build_dir),
        "dist_dir": str(dist_dir),
        **package_info,
    }

    if args.wheel:
        wheel_path = build_wheel(wheel_dir, python_exe=args.build_python, env=env)
        result["wheel"] = str(wheel_path)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
