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


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py <command>")
        print("\nAvailable commands:")
        print("  source-to-anki    Export source files to Anki")
        print("  anki-to-source    Import Anki changes back to source")
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "source-to-anki": source_to_anki,
        "anki-to-source": anki_to_source,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available commands: {', '.join(commands.keys())}")
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
