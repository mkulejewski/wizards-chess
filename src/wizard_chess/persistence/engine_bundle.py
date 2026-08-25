"""Materialize platform-specific chess-engine assets from the application bundle."""

from __future__ import annotations

import hashlib
import json
import logging
import lzma
import os
import platform
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

LOGGER = logging.getLogger(__name__)

_BUNDLE_RELEASE = "stockfish-18"
_BUNDLE_ROOT = Path(__file__).resolve().parents[1] / "engine" / "bundled" / _BUNDLE_RELEASE
_BUFFER_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class _BundleManifest:
    archive: str
    archive_sha256: str
    executable: str
    executable_sha256: str
    executable_size: int
    platform_key: str
    version: str


def bundled_platform_key(system: str | None = None, machine: str | None = None) -> str | None:
    """Return the stable bundle directory name for a supported OS/CPU pair."""
    system_name = (system or platform.system()).casefold()
    architecture = (machine or platform.machine()).casefold()
    normalized_system = {
        "darwin": "macos",
        "linux": "linux",
        "windows": "windows",
    }.get(system_name)
    normalized_architecture = {
        "aarch64": "arm64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "x86_64": "x86_64",
    }.get(architecture)
    if normalized_system is None or normalized_architecture is None:
        return None
    return f"{normalized_system}-{normalized_architecture}"


def resolve_bundled_stockfish(
    *,
    bundle_root: Path | None = None,
    cache_root: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
) -> str | None:
    """Return an executable bundled Stockfish path, extracting it once when compressed."""
    platform_key = bundled_platform_key(system, machine)
    if platform_key is None:
        return None
    selected_bundle_root = (bundle_root or _BUNDLE_ROOT).resolve()
    selected_cache_root = (cache_root or _default_cache_root()).resolve()
    return _resolve_bundled_stockfish(selected_bundle_root, selected_cache_root, platform_key)


@lru_cache(maxsize=16)
def _resolve_bundled_stockfish(
    bundle_root: Path,
    cache_root: Path,
    platform_key: str,
) -> str | None:
    variant_root = bundle_root / platform_key
    manifest_path = variant_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = _load_manifest(manifest_path)
        if manifest.platform_key != platform_key:
            raise ValueError(
                f"bundle declares platform {manifest.platform_key!r}, expected {platform_key!r}"
            )

        packaged_executable = variant_root / manifest.executable
        if packaged_executable.is_file() and _matches_executable(packaged_executable, manifest):
            _make_executable(packaged_executable)
            return str(packaged_executable)

        archive = variant_root / manifest.archive
        if not archive.is_file() or _sha256(archive) != manifest.archive_sha256:
            raise ValueError("bundled Stockfish archive is missing or has an invalid checksum")

        destination = cache_root / manifest.version / platform_key / manifest.executable
        if destination.is_file() and _matches_executable(destination, manifest):
            _make_executable(destination)
            return str(destination)
        return str(_extract_archive(archive, destination, manifest))
    except (OSError, lzma.LZMAError, ValueError) as error:
        LOGGER.warning("Bundled Stockfish is unavailable: %s", error)
        return None


def _load_manifest(path: Path) -> _BundleManifest:
    payload_value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload_value, dict):
        raise ValueError("bundled Stockfish manifest must be a JSON object")
    payload = cast(dict[str, object], payload_value)
    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"unsupported bundled Stockfish manifest schema: {schema_version!r}")
    executable_size = payload.get("executable_size")
    if not isinstance(executable_size, int) or isinstance(executable_size, bool):
        raise ValueError("bundled Stockfish manifest has an invalid executable size")
    return _BundleManifest(
        archive=_required_string(payload, "archive"),
        archive_sha256=_required_hash(payload, "archive_sha256"),
        executable=_required_string(payload, "executable"),
        executable_sha256=_required_hash(payload, "executable_sha256"),
        executable_size=executable_size,
        platform_key=_required_string(payload, "platform_key"),
        version=_required_string(payload, "version"),
    )


def _required_string(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise ValueError(f"bundled Stockfish manifest has an invalid {name}")
    return value


def _required_hash(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"bundled Stockfish manifest has an invalid {name}")
    return value


def _extract_archive(
    archive: Path,
    destination: Path,
    manifest: _BundleManifest,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output, lzma.open(archive, "rb") as source:
            shutil.copyfileobj(source, output, length=_BUFFER_SIZE)
        if not _matches_executable(temporary, manifest):
            raise ValueError("extracted Stockfish executable has an invalid checksum")
        _make_executable(temporary)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _matches_executable(path: Path, manifest: _BundleManifest) -> bool:
    try:
        return (
            path.stat().st_size == manifest.executable_size
            and _sha256(path) == manifest.executable_sha256
        )
    except OSError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_BUFFER_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | 0o111)


def _default_cache_root() -> Path:
    configured = os.environ.get("XDG_CACHE_HOME", "").strip()
    root = Path(configured).expanduser() if configured else Path.home() / ".cache"
    return root / "wizard-chess" / "engines"
