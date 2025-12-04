#!/usr/bin/env python3
import subprocess
import sys


def run(cmd: str) -> None:
    """Run a shell command and exit if it fails."""
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        sys.exit(result.returncode)


def source_to_anki() -> None:
    """Export source files to Anki."""
    run("uv run brainbrew run recipes/source_to_anki.yaml")


def anki_to_source() -> None:
    """Import Anki changes back to source."""
    run("uv run brainbrew run recipes/anki_to_source.yaml")


def validate() -> None:
    """Validate references in CSV files."""
    args = " ".join(sys.argv[2:])
    run(f"uv run python tools/validate_references.py {args}")


def list_relationships() -> None:
    """List relationships between notes."""
    args = " ".join(sys.argv[2:])
    run(f"uv run python tools/list_relationships.py {args}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py <command>")
        print("\nAvailable commands:")
        print("  source-to-anki      Export source files to Anki")
        print("  anki-to-source      Import Anki changes back to source")
        print("  validate            Validate references in CSV files")
        print("                      Use --auto-fix to automatically apply fixes")
        print("  list-relationships  List relationships between notes")
        print("                      Use --sort asc/desc, --search <term>, --limit <n>")
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "source-to-anki": source_to_anki,
        "anki-to-source": anki_to_source,
        "validate": validate,
        "list-relationships": list_relationships,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
