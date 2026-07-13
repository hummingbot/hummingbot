#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = ROOT.parent / "hummingbot-backups" / "strategy-evolution"
INCLUDE_PATTERNS = (
    "data/strategy-evolution",
    "data/*_runtime.json",
    "data/conf_evo_*.sqlite",
    "data/conf_pmm_mister_paper.sqlite",
    "conf/controllers/conf_evo_*.yml",
    "conf/scripts/conf_evo_*.yml",
    "reports/strategy_evolution_loop.md",
    "reports/strategy_promotion_evidence.json",
    "reports/*_walk_forward_latest.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_files(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for pattern in INCLUDE_PATTERNS:
        candidate = root / pattern
        matches = list(root.glob(pattern)) if "*" in pattern else [candidate]
        for match in matches:
            if match.is_dir():
                paths.update(path for path in match.rglob("*") if path.is_file())
            elif match.is_file():
                paths.add(match)
    return sorted(paths)


def create_backup(root: Path, backup_dir: Path, retain: int) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"strategy-evolution-{stamp}.tar.gz"
    files = selected_files(root)
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "files": {
            str(path.relative_to(root)): {
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
            for path in files
        },
    }
    with tempfile.TemporaryDirectory() as directory:
        manifest_path = Path(directory) / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary = target.with_suffix(".tmp")
        with tarfile.open(temporary, "w:gz") as archive:
            archive.add(manifest_path, arcname="manifest.json", recursive=False)
            for path in files:
                archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
        temporary.replace(target)
    os.chmod(target, 0o600)
    verify_backup(target)
    backups = sorted(backup_dir.glob("strategy-evolution-*.tar.gz"), reverse=True)
    for expired in backups[max(retain, 1) :]:
        expired.unlink()
    return target


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise ValueError(f"unsafe archive member: {member.name}")
    return members


def verify_backup(path: Path) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory)
        with tarfile.open(path, "r:gz") as archive:
            members = _safe_members(archive)
            # Members are explicitly rejected above when absolute, traversing,
            # or link-based. Avoid tarfile's newer filter= API so operations
            # also work with the older system Python on the LAN Mac.
            archive.extractall(destination, members=members)
        manifest = json.loads(
            (destination / "manifest.json").read_text(encoding="utf-8")
        )
        for relative, expected in manifest["files"].items():
            restored = destination / relative
            if not restored.is_file() or sha256(restored) != expected["sha256"]:
                raise ValueError(f"backup verification failed: {relative}")
    return manifest


def restore_backup(path: Path, destination: Path, confirm: str) -> dict:
    if confirm != "RESTORE":
        raise ValueError("restore requires --confirm RESTORE")
    manifest = verify_backup(path)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        with tarfile.open(path, "r:gz") as archive:
            members = _safe_members(archive)
            archive.extractall(staging, members=members)
        for relative in manifest["files"]:
            source = staging / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(f"{target.suffix}.restore-tmp")
            shutil.copy2(source, temporary)
            temporary.replace(target)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up Strategy Evolution state.")
    parser.add_argument("action", choices=("create", "verify", "restore"))
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--retain", type=int, default=14)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.action == "create":
        archive = create_backup(
            args.root.resolve(), args.backup_dir.resolve(), args.retain
        )
        print(json.dumps({"status": "verified", "archive": str(archive)}))
        return 0
    if args.archive is None:
        parser.error("verify and restore require an archive")
    if args.action == "verify":
        manifest = verify_backup(args.archive.resolve())
        print(json.dumps({"status": "verified", "files": len(manifest["files"])}))
        return 0
    destination = (args.destination or args.root).resolve()
    manifest = restore_backup(args.archive.resolve(), destination, args.confirm)
    print(
        json.dumps(
            {
                "status": "restored",
                "files": len(manifest["files"]),
                "destination": str(destination),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
