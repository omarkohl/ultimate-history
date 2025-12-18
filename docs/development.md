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

3. Tag the release:
   ```bash
   jj tag set v0.99.0 -r @-
   ```

4. Start Anki with the release account:
   ```bash
   anki -b anki_release_dir
   ```

5. Import the latest version via CrowdAnki plugin

6. Run maintenance tasks in Anki:
   - Tools → Check Media
   - Tools → Empty Cards

7. Sync with AnkiWeb

8. Export the deck as `.apkg` file

9. Publish a new release on GitHub and upload the `.apkg` file
