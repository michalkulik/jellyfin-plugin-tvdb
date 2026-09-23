#!/usr/bin/env python3
"""Builds a Jellyfin plugin repository (ZIP + manifest.json) for this fork.

Jellyfin reads a plugin repository by fetching a `manifest.json` that lists plugins and their
versions. Each version points at a ZIP containing the plugin assemblies plus a `meta.json` with
the plugin's own manifest. This script produces both files from a completed Release build, so the
fork can be added to a Jellyfin server as an extra plugin repository.

The metadata that describes the plugin (guid, name, category, target ABI, ...) is read from
`build.yaml` in the repository root, which stays the single source of truth.

Usage:
    python tools/build-plugin-repo.py --version 24.0.0.1 --output dist

    --version   Version to publish, matching the build's PluginVersion (for example 24.0.0.1).
    --output    Directory to write the ZIP and manifest.json into (created if missing).
    --build-dir Directory holding the built assemblies. Default: Jellyfin.Plugin.Tvdb/bin/Release/net10.0
    --repo      owner/name of the GitHub repository, used to build the asset download URLs.
                Default: michalkulik/jellyfin-plugin-tvdb
    --tag       Release tag holding the assets. Default: v<version>
    --notes     Changelog text for this version. Default: the changelog from build.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUILD_DIR = REPO_ROOT / "Jellyfin.Plugin.Tvdb" / "bin" / "Release" / "net10.0"


def read_build_yaml() -> dict:
    with open(REPO_ROOT / "build.yaml", "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def make_meta_json(build: dict, version: str, changelog: str, timestamp: str, owner: str) -> dict:
    """The manifest Jellyfin reads from inside the ZIP after installing a plugin."""
    return {
        "category": build["category"],
        "changelog": changelog,
        "description": build["description"],
        "guid": build["guid"],
        "imageUrl": build["imageUrl"],
        "name": build["name"],
        "overview": build["overview"],
        "owner": owner,
        "targetAbi": build["targetAbi"],
        "timestamp": timestamp,
        "version": version,
    }


def make_manifest_json(build: dict, version: str, changelog: str, timestamp: str, owner: str,
                       source_url: str, checksum: str) -> list:
    """The plugin repository manifest, a list of packages with all their published versions."""
    return [
        {
            "guid": build["guid"],
            "name": build["name"],
            "description": build["description"],
            "overview": build["overview"],
            "owner": owner,
            "category": build["category"],
            "imageUrl": build["imageUrl"],
            "versions": [
                {
                    "version": version,
                    "changelog": changelog,
                    "targetAbi": build["targetAbi"],
                    "sourceUrl": source_url,
                    "checksum": checksum,
                    "timestamp": timestamp,
                }
            ],
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", default=str(REPO_ROOT / "dist"))
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD_DIR))
    parser.add_argument("--repo", default="michalkulik/jellyfin-plugin-tvdb")
    parser.add_argument("--tag")
    parser.add_argument("--notes")
    args = parser.parse_args()

    build = read_build_yaml()
    version = args.version.removeprefix("v")
    tag = args.tag or f"v{version}"
    owner = build.get("owner", "jellyfin")
    changelog = args.notes if args.notes is not None else (build.get("changelog") or "").strip()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    build_dir = Path(args.build_dir)
    if not build_dir.is_dir():
        print(f"error: build directory not found: {build_dir}", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Only the assemblies named in build.yaml are shipped, the rest of the build output is provided
    # by the Jellyfin server itself.
    artifacts = build["artifacts"]
    missing = [name for name in artifacts if not (build_dir / name).is_file()]
    if missing:
        print(f"error: missing build artifacts in {build_dir}: {', '.join(missing)}", file=sys.stderr)
        return 1

    zip_name = f"{build['name'].lower().replace(' ', '')}_{version}.zip"
    zip_path = output_dir / zip_name

    staging = output_dir / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    meta = make_meta_json(build, version, changelog, timestamp, owner)
    (staging / "meta.json").write_text(json.dumps(meta, indent=4) + "\n", encoding="utf-8")
    for name in artifacts:
        shutil.copy2(build_dir / name, staging / name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.iterdir()):
            archive.write(path, path.name)
    shutil.rmtree(staging)

    checksum = hashlib.md5(zip_path.read_bytes()).hexdigest()

    source_url = f"https://github.com/{args.repo}/releases/download/{tag}/{zip_name}"
    manifest = make_manifest_json(build, version, changelog, timestamp, owner, source_url, checksum)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")

    print(json.dumps({
        "zip": str(zip_path),
        "zipSize": zip_path.stat().st_size,
        "md5": checksum,
        "manifest": str(manifest_path),
        "sourceUrl": source_url,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
