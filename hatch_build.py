from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging import tags


ROOT = Path(__file__).resolve().parent
PLUGIN_NAME = "tcomb"
DEFAULT_REPOSITORY = "RyougiKukoc/vapoursynth-tcomb-api4"
WINDOWS_PREBUILT_ASSET = "tcomb-msys2-ucrt64.zip"
LINUX_PREBUILT_ASSET = "tcomb-linux-x86_64.zip"


def _find_command(*candidates: str) -> str | None:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _prepend_path_entries(env: dict[str, str], entries: list[Path]) -> None:
    parts = [str(entry) for entry in entries if entry.exists()]
    if not parts:
        return
    existing = env.get("PATH")
    env["PATH"] = os.pathsep.join(parts + ([existing] if existing else []))


def _configure_build_env(env: dict[str, str]) -> dict[str, str]:
    if sys.platform != "win32":
        # The Linux VapourSynth wheel ships its own headers, library and
        # vapoursynth.pc rather than installing the latter system-wide.
        try:
            import vapoursynth
        except ImportError:
            return env
        pkgconfig_dir = Path(vapoursynth.__file__).resolve().parent / "pkgconfig"
        if pkgconfig_dir.is_dir() and "PKG_CONFIG_PATH" not in env:
            env["PKG_CONFIG_PATH"] = str(pkgconfig_dir)
        return env

    msystem_prefix = env.get("MSYSTEM_PREFIX")
    vs_wheel_dir = ROOT / "_deps" / "vapoursynth-wheel-R77"
    path_entries: list[Path] = []

    if vs_wheel_dir.exists():
        path_entries.append(vs_wheel_dir)

    if msystem_prefix:
        prefix_path = Path(msystem_prefix)
        path_entries.append(prefix_path / "bin")
        path_entries.append(prefix_path.parent / "usr" / "bin")
    else:
        path_entries.extend([Path(r"C:\msys64\ucrt64\bin"), Path(r"C:\msys64\usr\bin")])

    _prepend_path_entries(env, path_entries)

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


def _meson_command() -> list[str]:
    meson = _find_command("meson")
    if meson:
        return [meson]

    for module_name in ("mesonbuild", "mesonbuild.mesonmain"):
        module_runner = [sys.executable, "-m", module_name]
        probe = subprocess.run(module_runner + ["--version"], cwd=ROOT, capture_output=True, text=True)
        if probe.returncode == 0:
            return module_runner

    raise FileNotFoundError("meson executable not found and python -m mesonbuild is unavailable")


def _run(cmd: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in {"", "0", "false", "no", "off"})


def _default_prebuilt_url(version: str) -> str:
    repository = os.environ.get("TCOMB_PREBUILT_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPOSITORY
    tag = os.environ.get("TCOMB_PREBUILT_TAG") or f"v{version}"
    asset = os.environ.get("TCOMB_PREBUILT_ASSET_NAME") or _default_prebuilt_asset()
    return f"https://github.com/{repository}/releases/download/{tag}/{asset}"


def _default_prebuilt_asset() -> str:
    if sys.platform == "linux" and platform.machine().lower() in {"amd64", "x86_64"}:
        return LINUX_PREBUILT_ASSET
    return WINDOWS_PREBUILT_ASSET


def _project_version() -> str:
    override = os.environ.get("TCOMB_PREBUILT_VERSION")
    if override:
        return override
    pyproject = ROOT / "pyproject.toml"
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError(f"project.version missing from {pyproject}")
    return version


def _prebuilt_source(version: str) -> tuple[str, bool]:
    explicit = os.environ.get("TCOMB_PREBUILT_URL")
    if explicit:
        return explicit, True
    return _default_prebuilt_url(version), False


def _supports_prebuilt() -> bool:
    return sys.platform in {"win32", "linux"} and platform.machine().lower() in {"amd64", "x86_64"}


def _plugin_filename() -> str:
    return f"{PLUGIN_NAME}.dll" if sys.platform == "win32" else f"{PLUGIN_NAME}.so"


def _fetch_prebuilt_archive(source: str, destination: Path) -> None:
    candidate = Path(source)
    if candidate.exists():
        shutil.copy2(candidate, destination)
        return

    request = urllib.request.Request(source, headers={"User-Agent": "vapoursynth-tcomb-build-hook"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _write_manifest(target_dir: Path) -> None:
    (target_dir / "manifest.vs").write_text(
        "[VapourSynth Manifest V1]\n"
        f"{PLUGIN_NAME}\n",
        encoding="utf-8",
    )


def _stage_prebuilt_plugin(version: str, target_dir: Path) -> bool:
    if _truthy(os.environ.get("TCOMB_FORCE_BUILD")):
        print("TComb wheel build: skipping prebuilt asset because TCOMB_FORCE_BUILD is set")
        return False
    if not _supports_prebuilt():
        print("TComb wheel build: prebuilt release asset path only applies to Windows x86_64; falling back to local build")
        return False

    source, explicit = _prebuilt_source(version)
    asset_name = Path(source).name or _default_prebuilt_asset()
    try:
        with tempfile.TemporaryDirectory(prefix="tcomb-prebuilt-") as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            archive_path = temp_dir / asset_name
            _fetch_prebuilt_archive(source, archive_path)
            with zipfile.ZipFile(archive_path) as zf:
                package_members = [
                    name
                    for name in zf.namelist()
                    if name.replace("\\", "/").startswith(f"{PLUGIN_NAME}/") and not name.endswith("/")
                ]
                if not package_members:
                    package_members = [
                        name
                        for name in zf.namelist()
                        if name.replace("\\", "/") in {_plugin_filename(), "manifest.vs"}
                    ]
                if not package_members:
                    raise FileNotFoundError(f"prebuilt archive does not contain a {PLUGIN_NAME}/ package directory")

                for member in package_members:
                    normalized = member.replace("\\", "/")
                    relative = normalized.split("/", 1)[1] if normalized.startswith(f"{PLUGIN_NAME}/") else normalized
                    out_path = target_dir / relative
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, out_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
            plugin = target_dir / _plugin_filename()
            if not plugin.exists():
                raise FileNotFoundError(f"prebuilt archive did not provide {_plugin_filename()}")
            if not (target_dir / "manifest.vs").exists():
                _write_manifest(target_dir)
    except Exception as exc:
        if explicit:
            raise RuntimeError(f"failed to use explicit TComb prebuilt asset {source!r}") from exc
        print(f"TComb wheel build: prebuilt asset unavailable at {source}; falling back to local build ({exc})")
        return False

    print(f"TComb wheel build: using prebuilt release asset {source}")
    return True


def _find_built_plugin(build_dir: Path) -> Path:
    suffixes = [".dll"] if sys.platform == "win32" else [".so", ".dylib"]
    for suffix in suffixes:
        for stem in (PLUGIN_NAME, f"lib{PLUGIN_NAME}"):
            candidate = build_dir / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"missing built plugin under {build_dir}")


class CustomHook(BuildHookInterface[Any]):
    build_dir = ROOT / "build-wheel"
    dist_dir = ROOT / "vapoursynth" / "plugins" / PLUGIN_NAME

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        del version
        build_data["pure_python"] = False
        platform_tag = os.environ.get("TCOMB_PLATFORM_TAG") or str(next(tags.platform_tags()))
        build_data["tag"] = f"py3-none-{platform_tag}"
        project_version = _project_version()

        shutil.rmtree(self.build_dir, ignore_errors=True)
        shutil.rmtree(self.dist_dir.parent.parent, ignore_errors=True)
        self.dist_dir.mkdir(parents=True, exist_ok=True)

        if not _stage_prebuilt_plugin(project_version, self.dist_dir):
            env = _configure_build_env(os.environ.copy())
            meson = _meson_command()
            _run(meson + ["setup", str(self.build_dir), "--wipe"], env=env)
            _run(meson + ["compile", "-C", str(self.build_dir)], env=env)

            plugin_dll = _find_built_plugin(self.build_dir)
            suffix = plugin_dll.suffix
            shutil.copy2(plugin_dll, self.dist_dir / f"{PLUGIN_NAME}{suffix}")
            _write_manifest(self.dist_dir)

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        del version, build_data, artifact_path
        shutil.rmtree(self.build_dir, ignore_errors=True)
        shutil.rmtree(self.dist_dir.parent.parent, ignore_errors=True)
