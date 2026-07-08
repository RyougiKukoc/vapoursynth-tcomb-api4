#!/usr/bin/env python3
"""Smoke-load the packaged TComb plugin and render a deterministic frame."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "tcomb"


class IsolatedEnvironmentPolicy:
    """Create a single VapourSynth environment with autoload disabled."""

    def __init__(self, vs_module: Any, flags: int) -> None:
        self._api: Any = None
        self._environment: Any = None
        self._flags = flags

    def on_policy_registered(self, api: Any) -> None:
        self._api = api
        self._environment = api.create_environment(self._flags)

    def on_policy_cleared(self) -> None:
        self._api = None
        self._environment = None

    def get_current_environment(self) -> Any:
        return self._environment

    def set_environment(self, environment: Any) -> Any:
        previous = self._environment
        if environment is not None:
            self._environment = environment
        return previous

    def is_alive(self, environment: Any) -> bool:
        return environment is self._environment

    def close(self) -> None:
        if self._api is not None and self._environment is not None:
            self._api.destroy_environment(self._environment)
            self._environment = None


def install_isolated_policy(vs_module: Any) -> IsolatedEnvironmentPolicy | None:
    if not hasattr(vs_module, "register_policy") or vs_module.has_policy():
        return None
    policy = IsolatedEnvironmentPolicy(vs_module, int(vs_module.DISABLE_AUTO_LOADING))
    vs_module.register_policy(policy)
    return policy


def resolve_artifact_dir(artifact_dir_arg: str | None, artifact_zip_arg: str | None) -> tuple[Path, Path | None]:
    if artifact_zip_arg:
        archive = (ROOT / artifact_zip_arg).resolve()
        if not archive.exists():
            raise FileNotFoundError(f"missing artifact zip: {archive}")
        temp_dir = Path(tempfile.mkdtemp(prefix="tcomb-package-"))
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(temp_dir)
        candidates = [path for path in temp_dir.iterdir() if path.is_dir()]
        if len(candidates) != 1:
            raise RuntimeError(f"expected one top-level package directory in {archive}, found {len(candidates)}")
        return candidates[0], temp_dir

    artifact_dir = (ROOT / (artifact_dir_arg or "dist/msys2-ucrt64/tcomb")).resolve()
    return artifact_dir, None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Smoke test a packaged TComb plugin.")
    parser.add_argument("--artifact-dir", help="Packaged plugin directory.")
    parser.add_argument("--artifact-zip", help="Packaged plugin zip asset.")
    parser.add_argument("--json", action="store_true", help="Emit JSON result.")
    args = parser.parse_args(argv)

    artifact_dir, temp_dir = resolve_artifact_dir(args.artifact_dir, args.artifact_zip)
    plugin = artifact_dir / f"{PLUGIN_NAME}.dll"
    manifest = artifact_dir / "manifest.vs"
    if not plugin.exists():
        raise FileNotFoundError(f"missing plugin: {plugin}")
    if not manifest.exists():
        raise FileNotFoundError(f"missing manifest: {manifest}")

    add_dll_directory = getattr(os, "add_dll_directory", None)
    dll_handles = []
    if add_dll_directory is not None:
        dll_handles.append(add_dll_directory(str(artifact_dir)))

    import vapoursynth as vs  # pylint: disable=import-outside-toplevel

    policy = install_isolated_policy(vs)
    core = vs.core

    core.std.LoadPlugin(str(plugin))
    src = core.std.BlankClip(width=64, height=48, format=vs.YUV420P8, length=12, color=[96, 128, 128])
    out = core.tcomb.TComb(src)
    frame = out.get_frame(3)
    stats = dict(core.std.PlaneStats(out).get_frame(3).props)
    result = {
        "plugin": str(plugin),
        "manifest": str(manifest),
        "width": frame.width,
        "height": frame.height,
        "format": frame.format.name,
        "frames": out.num_frames,
        "plane_stats_average": float(stats["PlaneStatsAverage"]),
        "plane_stats_min": float(stats["PlaneStatsMin"]),
        "plane_stats_max": float(stats["PlaneStatsMax"]),
    }

    try:
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            for key, value in result.items():
                print(f"{key}={value}")
        return 0
    finally:
        for handle in dll_handles:
            handle.close()
        if policy is not None:
            policy.close()
        if temp_dir is not None:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
