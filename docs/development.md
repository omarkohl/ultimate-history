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

## Neo4j Graph Database

The project uses Neo4j AuraDB as a graph database to store and query entities and their relationships. This provides a more powerful way to explore connections between historical figures and events compared to flat CSV files. **This is entirely optional and working with CSV files only is fine!**

You need to create your own Neo4j AuraDB instance. There is a free tier available. See [here](https://console-preview.neo4j.io/).

### Graph Schema

**Node types:**
- `Person` - historical figures (name, known_for, birth/death years)
- `Event` - historical events (name, summary, start/end years)
- `QA` - question/answer cards
- `Cloze` - cloze deletion cards
- `Tag` - hierarchical tags (Region, Period, Theme)

**Relationship types:**
- `RELATED_TO_PERSON` - links entities to persons
- `RELATED_TO_EVENT` - links entities to events
- `HAS_TAG` - links entities to tags

### Syncing Between CSV and Neo4j

```bash
# Import CSV data into Neo4j (overwrites existing data)
uv run tools/csv_to_neo4j.py

# Export Neo4j data back to CSV
uv run tools/neo4j_to_csv.py
```

The CSV files in `src/data/` remain the source of truth for version control. Neo4j is used for:
- Exploring relationships between entities
- Finding related content when adding new entities
- AI-assisted entity creation via Claude Code

### Querying the Database

Use `uv run tools/neo4j_query.py` for ad-hoc queries:

```bash
# List all tags with usage counts
uv run tools/neo4j_query.py tags

# Search entities
uv run tools/neo4j_query.py search "napoleon"

# Show entity details
uv run tools/neo4j_query.py show "Napoleon Bonaparte"

# Get relationships
uv run tools/neo4j_query.py relations "Napoleon Bonaparte"

# Find related entities by time period
uv run tools/neo4j_query.py find-related "Napoleon Bonaparte" --start 1789 --end 1815
```

### Environment Variables

Set these in `.env` (never commit this file):
- `NEO4J_URI` - Connection URI (e.g., `neo4j+s://xxxx.databases.neo4j.io`)
- `NEO4J_PASSWORD` - Database password
- `NEO4J_USERNAME` - Optional, defaults to `neo4j`

## Claude Code Integration

Claude Code can create and edit entities directly in the Neo4j database using the `entity-manager` skill. This provides an AI-assisted workflow for adding and editing historical content. **It is imperative that you validate such content for example by cross-checking with Wikipedia!**

### Using the Entity Manager

Invoke the skill by asking Claude to add entities:
- "Add Napoleon Bonaparte to the database"
- "Create a QA card about the French Revolution"
- "Link Bismarck to the Franco-Prussian War"

Or explicitly: `/entity-manager`

### What Claude Can Do

- **Search** existing entities to avoid duplicates
- **Create** persons, events, QA cards, and cloze cards with proper tags
- **Add relationships** between entities with descriptive context
- **Update** existing entities
- **Find related** entities by time period and tags

### Workflow

1. Claude searches for existing content to avoid duplicates
2. Claude finds related entities using time periods and tags
3. Claude creates the entity with appropriate tags (Region, Period, Theme)
4. Claude adds relationships to related persons/events
5. Claude verifies the creation

### Exporting Changes

After using Claude to create entities, export to CSV:

```bash
uv run tools/neo4j_to_csv.py
uv run main.py sync
```

Then commit the updated CSV and build files.
