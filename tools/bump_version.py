#!/usr/bin/env python3
"""Bump version in src/headers/description.html"""

import re
import sys
from pathlib import Path


def parse_version(version: str) -> tuple[int, int, int, bool]:
    """Parse version string like '0.2.0' or '0.2.0-dev'"""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(-dev)?$", version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    major, minor, patch, dev = match.groups()
    return int(major), int(minor), int(patch), bool(dev)


def format_version(major: int, minor: int, patch: int, dev: bool) -> str:
    """Format version tuple back to string"""
    version = f"{major}.{minor}.{patch}"
    if dev:
        version += "-dev"
    return version


def bump_version(version: str, bump_type: str | None, add_dev: bool) -> str:
    """Bump version according to type"""
    major, minor, patch, has_dev = parse_version(version)

    # If current version has -dev and no explicit bump type, just remove -dev
    if has_dev and bump_type is None:
        return format_version(major, minor, patch, add_dev)

    # Otherwise, bump according to type
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    elif bump_type is not None:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return format_version(major, minor, patch, add_dev)


def main():
    description_file = Path("src/headers/description.html")

    # Parse arguments
    bump_type = None  # No default, will be determined based on current version
    add_dev = False

    for arg in sys.argv[1:]:
        if arg in ("major", "minor", "patch"):
            bump_type = arg
        elif arg == "--dev":
            add_dev = True
        else:
            print(f"Usage: {sys.argv[0]} [major|minor|patch] [--dev]")
            print(f"Unknown argument: {arg}")
            sys.exit(1)

    # Read current version
    content = description_file.read_text()
    match = re.search(r"<b>Version: </b>(\d+\.\d+\.\d+(?:-dev)?)", content)
    if not match:
        print("Error: Could not find version in description.html")
        sys.exit(1)

    current_version = match.group(1)
    _, _, _, has_dev = parse_version(current_version)

    # Default bump type: remove -dev if present, otherwise bump minor
    if bump_type is None:
        bump_type = None if has_dev else "minor"

    new_version = bump_version(current_version, bump_type, add_dev)

    # Update file
    new_content = content.replace(
        f"<b>Version: </b>{current_version}", f"<b>Version: </b>{new_version}"
    )
    description_file.write_text(new_content)

    print(f"Bumped version: {current_version} → {new_version}")


if __name__ == "__main__":
    main()
