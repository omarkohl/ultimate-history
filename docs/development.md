# Development Guide

This guide covers the technical details for developing and maintaining the Ultimate History project.

## Architecture

This project uses [brain-brew](https://github.com/ohare93/brain-brew) to bidirectionally convert between CrowdAnki JSON format and CSV files.

- `build/` - CrowdAnki files (generated, do not edit manually)
- `src/data/` - CSV source files (edit these)
- `src/note_models/` - Note types and card templates

## Common Development Tasks

```bash
# Most common workflow: export to Anki, import back, and validate
uv run main.py sync

# Import/export between source files (CSV) and Anki (CrowdAnki JSON format)
uv run main.py source-to-anki
uv run main.py anki-to-source

# Verify and fix data
uv run main.py validate
uv run main.py validate --auto-fix

# List notes by relationship count to identify highly-connected or isolated notes
uv run main.py list-relationships
uv run main.py list-relationships --sort asc --limit 10  # Show least connected
uv run main.py list-relationships --search "Napoleon"   # Filter by search term
```

## Releasing a New Version

1. Bump the version:
   ```bash
   uv run main.py bump-version
   ```

2. Update [CHANGELOG.md](../CHANGELOG.md) with the release notes and commit the changes

3. Run `uv run main.py sync`

4. Tag the release:
   ```bash
   jj tag set v0.99.0 -r @-
   ```

5. Start Anki with the release account:
   ```bash
   anki -b anki_release_dir
   ```

6. Import the latest version via CrowdAnki plugin

7. Run maintenance tasks in Anki:
   - Tools → Check Media
   - Tools → Empty Cards

8. Sync with AnkiWeb

9. Export the deck as `.apkg` file

10. Publish a new release on GitHub and upload the `.apkg` file. Rename it to
    `Ultimate_History.apkg`. Copy the relevant changelog parts from
    [CHANGELOG.md](../CHANGELOG.md).

11. Go to https://ankiweb.net/decks and share the deck. Update the version number in the description.

12. Bump the version to the next `-dev` by repeating steps 1-3.
