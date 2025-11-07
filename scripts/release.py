#!/usr/bin/env python3
"""Release automation script for ACHA project."""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")

    content = pyproject_path.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Version not found in pyproject.toml")

    return match.group(1)


def bump_version(current: str, part: str = "patch") -> str:
    """
    Bump version number.

    Args:
        current: Current version (e.g., "0.4.0")
        part: Part to bump ("major", "minor", or "patch")

    Returns:
        New version string
    """
    major, minor, patch = map(int, current.split("."))

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid part: {part}. Must be 'major', 'minor', or 'patch'")

    return f"{major}.{minor}.{patch}"


def update_version_in_file(file_path: Path, old_version: str, new_version: str):
    """Update version in a file."""
    if not file_path.exists():
        return

    content = file_path.read_text()
    updated = content.replace(f'version = "{old_version}"', f'version = "{new_version}"')
    updated = updated.replace(f'__version__ = "{old_version}"', f'__version__ = "{new_version}"')

    if updated != content:
        file_path.write_text(updated)
        print(f"✓ Updated version in {file_path}")


def generate_changelog(since_tag: str = None, output_file: str = "CHANGELOG.md") -> None:
    """
    Generate changelog from git commits.

    Args:
        since_tag: Generate changelog since this tag (default: latest tag)
        output_file: Output file path
    """
    # Get the latest tag if not specified
    if not since_tag:
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                check=True
            )
            since_tag = result.stdout.strip()
        except subprocess.CalledProcessError:
            since_tag = None

    # Get commits
    if since_tag:
        git_cmd = ["git", "log", f"{since_tag}..HEAD", "--pretty=format:%s"]
    else:
        git_cmd = ["git", "log", "--pretty=format:%s"]

    try:
        result = subprocess.run(git_cmd, capture_output=True, text=True, check=True)
        commits = result.stdout.strip().split("\n")
    except subprocess.CalledProcessError:
        print("Error getting git log")
        return

    # Categorize commits
    features = []
    fixes = []
    docs = []
    other = []

    for commit in commits:
        if commit.startswith("feat"):
            features.append(commit)
        elif commit.startswith("fix"):
            fixes.append(commit)
        elif commit.startswith("docs"):
            docs.append(commit)
        else:
            other.append(commit)

    # Generate changelog content
    changelog_path = Path(output_file)
    if changelog_path.exists():
        existing_content = changelog_path.read_text()
    else:
        existing_content = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"

    new_version = get_current_version()
    date = datetime.now().strftime("%Y-%m-%d")

    new_entry = f"\n## [{new_version}] - {date}\n\n"

    if features:
        new_entry += "### Added\n"
        for feat in features:
            new_entry += f"- {feat}\n"
        new_entry += "\n"

    if fixes:
        new_entry += "### Fixed\n"
        for fix in fixes:
            new_entry += f"- {fix}\n"
        new_entry += "\n"

    if docs:
        new_entry += "### Documentation\n"
        for doc in docs:
            new_entry += f"- {doc}\n"
        new_entry += "\n"

    # Insert new entry after the header
    lines = existing_content.split("\n")
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith("## [") or line.startswith("## Version"):
            header_end = i
            break
        if i > 10:  # Safety: assume header is within first 10 lines
            header_end = 3
            break

    updated_content = "\n".join(lines[:header_end]) + new_entry + "\n".join(lines[header_end:])
    changelog_path.write_text(updated_content)
    print(f"✓ Generated changelog entry in {output_file}")


def create_git_tag(version: str, message: str = None):
    """Create and push a git tag."""
    tag_name = f"v{version}"

    if message is None:
        message = f"Release {version}"

    try:
        # Create annotated tag
        subprocess.run(
            ["git", "tag", "-a", tag_name, "-m", message],
            check=True
        )
        print(f"✓ Created tag {tag_name}")

        # Push tag
        subprocess.run(
            ["git", "push", "origin", tag_name],
            check=True
        )
        print(f"✓ Pushed tag {tag_name}")

    except subprocess.CalledProcessError as e:
        print(f"✗ Error creating/pushing tag: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ACHA Release Automation")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # bump command
    bump_parser = subparsers.add_parser("bump", help="Bump version number")
    bump_parser.add_argument(
        "part",
        choices=["major", "minor", "patch"],
        default="patch",
        nargs="?",
        help="Version part to bump (default: patch)"
    )
    bump_parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Don't commit the version bump"
    )

    # changelog command
    changelog_parser = subparsers.add_parser("changelog", help="Generate changelog")
    changelog_parser.add_argument(
        "--since",
        help="Generate changelog since this tag"
    )

    # tag command
    tag_parser = subparsers.add_parser("tag", help="Create release tag")
    tag_parser.add_argument(
        "--message",
        "-m",
        help="Tag message"
    )

    # release command (bump + changelog + tag)
    release_parser = subparsers.add_parser("release", help="Full release (bump + changelog + tag)")
    release_parser.add_argument(
        "part",
        choices=["major", "minor", "patch"],
        default="patch",
        nargs="?",
        help="Version part to bump (default: patch)"
    )

    args = parser.parse_args()

    if args.command == "bump":
        current_version = get_current_version()
        new_version = bump_version(current_version, args.part)

        print(f"Bumping version: {current_version} → {new_version}")

        # Update pyproject.toml
        update_version_in_file(Path("pyproject.toml"), current_version, new_version)

        if not args.no_commit:
            subprocess.run(["git", "add", "pyproject.toml"])
            subprocess.run(["git", "commit", "-m", f"chore: bump version to {new_version}"])
            print(f"✓ Committed version bump")

    elif args.command == "changelog":
        generate_changelog(since_tag=args.since)

    elif args.command == "tag":
        version = get_current_version()
        create_git_tag(version, args.message)

    elif args.command == "release":
        # Full release workflow
        current_version = get_current_version()
        new_version = bump_version(current_version, args.part)

        print(f"\n🚀 Starting release: {current_version} → {new_version}\n")

        # 1. Bump version
        update_version_in_file(Path("pyproject.toml"), current_version, new_version)

        # 2. Generate changelog
        generate_changelog()

        # 3. Commit changes
        subprocess.run(["git", "add", "pyproject.toml", "CHANGELOG.md"])
        subprocess.run(["git", "commit", "-m", f"chore: release {new_version}"])

        # 4. Create tag
        create_git_tag(new_version, f"Release {new_version}")

        print(f"\n✓ Release {new_version} complete!")
        print(f"\nNext steps:")
        print(f"  1. Push changes: git push")
        print(f"  2. Create GitHub release from tag v{new_version}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
