import hashlib
import json
import lzma
from pathlib import Path

import pytest

from wizard_chess.persistence.engine_bundle import (
    bundled_platform_key,
    resolve_bundled_stockfish,
)


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "linux-x86_64"),
        ("Linux", "AMD64", "linux-x86_64"),
        ("Darwin", "arm64", "macos-arm64"),
        ("Windows", "AMD64", "windows-x86_64"),
        ("Plan9", "x86_64", None),
        ("Linux", "riscv64", None),
    ],
)
def test_bundled_platform_key_normalizes_supported_platforms(
    system: str,
    machine: str,
    expected: str | None,
) -> None:
    assert bundled_platform_key(system, machine) == expected


def test_bundled_engine_is_verified_extracted_and_reused(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    cache_root = tmp_path / "cache"
    executable = b"fake UCI engine\n"
    archive = _write_bundle(bundle_root, executable)

    resolved = resolve_bundled_stockfish(
        bundle_root=bundle_root,
        cache_root=cache_root,
        system="Linux",
        machine="AMD64",
    )

    assert resolved is not None
    extracted = Path(resolved)
    assert extracted.read_bytes() == executable
    assert extracted.stat().st_mode & 0o111

    archive.unlink()
    assert (
        resolve_bundled_stockfish(
            bundle_root=bundle_root,
            cache_root=cache_root,
            system="Linux",
            machine="AMD64",
        )
        == resolved
    )


def test_corrupt_bundled_engine_archive_is_ignored(tmp_path: Path) -> None:
    bundle_root = tmp_path / "bundle"
    archive = _write_bundle(bundle_root, b"fake UCI engine\n")
    archive.write_bytes(b"corrupt")

    assert (
        resolve_bundled_stockfish(
            bundle_root=bundle_root,
            cache_root=tmp_path / "cache",
            system="Linux",
            machine="x86_64",
        )
        is None
    )


def _write_bundle(bundle_root: Path, executable: bytes) -> Path:
    variant = bundle_root / "linux-x86_64"
    variant.mkdir(parents=True)
    compressed = lzma.compress(executable)
    archive = variant / "stockfish.xz"
    archive.write_bytes(compressed)
    manifest = {
        "schema_version": 1,
        "version": "stockfish-test",
        "platform_key": "linux-x86_64",
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(compressed).hexdigest(),
        "executable": "stockfish",
        "executable_sha256": hashlib.sha256(executable).hexdigest(),
        "executable_size": len(executable),
    }
    (variant / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return archive
