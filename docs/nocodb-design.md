# NocoDB Integration Design

## Goal

Enable Claude to add and edit historical data (persons, events) without requiring the full CSV files in context, while providing a user-friendly web interface for human editing with navigable links between related items.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Claude Code   │────▶│  Python Script  │────▶│     NocoDB      │
│   (via Skill)   │     │  (REST client)  │     │   (SQLite DB)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │    Web UI       │
                                                │  (human editing)│
                                                └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │   CSV Export    │
                                                │  (for Anki)     │
                                                └─────────────────┘
```

## Workflow Options

NocoDB is **optional**. Contributors can choose their preferred workflow:

### Option A: CSV-only (current workflow)
Edit `src/data/*.csv` directly. No NocoDB required. This remains fully supported.

### Option B: NocoDB locally (enhanced workflow)
1. Run `nocodb.py import` to populate local NocoDB from CSVs
2. Edit via Web UI or Claude (via script)
3. Run `nocodb.py export` to write back to CSVs
4. Commit CSVs via jj

### Option C: Central NocoDB (future)
A shared NocoDB instance could serve as the single source of truth, with periodic CSV exports for Anki generation. Not implemented yet.

**CSVs are the versioned source of truth.** When in doubt, CSV wins. The user explicitly chooses the sync direction:
- `import` overwrites NocoDB with CSV data
- `export` overwrites CSVs with NocoDB data

## Components

### 1. NocoDB Instance

- **Deployment**: Docker, local only
- **Database**: SQLite backend (simple, file-based)
- **Tables**: `person`, `event`, `tag`, `qa`, `cloze`, plus junction tables
- **Relationships**: Link columns replacing text-based "related person/event" fields
- **Media**: Mount `src/media/` into container for image storage

### 2. Python Script (`scripts/nocodb.py`)

Commands:
```
nocodb.py import                      # Import CSVs → NocoDB (overwrites NocoDB)
nocodb.py export                      # Export NocoDB → CSVs (overwrites CSVs)
nocodb.py search <table> <query>      # Find records by name/content
nocodb.py get <table> <id>            # Get single record with resolved links
nocodb.py add <table> --field=value   # Create new record
nocodb.py update <table> <id> --field=value  # Update existing record
nocodb.py link <table> <id> <field> <target_id>  # Add relationship
```

Configuration via environment or `.env`:
- `NOCODB_URL` (default: `http://localhost:8080`)
- `NOCODB_API_TOKEN`
- `NOCODB_BASE_ID`

### 3. Claude Skill (`.claude/skills/nocodb.md`)

Provides usage instructions so Claude knows how to use the script for common operations like searching, adding persons/events, and managing relationships.

## Schema

### Main Tables

```
person:
  - id (auto)
  - guid (text, unique, for Anki sync)
  - name (text)
  - known_for (text)
  - date_of_birth (text)
  - date_of_death (text)
  - picture (attachment)
  - notes (text)
  - source_license (text)

event:
  - id (auto)
  - guid (text, unique)
  - name (text)
  - summary (text)
  - start_date (text)
  - end_date (text)
  - notes (text)
  - source_license (text)

qa:
  - id (auto)
  - guid (text, unique)
  - question (text)
  - answer (text)
  - notes (text)
  - source_license (text)

cloze:
  - id (auto)
  - guid (text, unique)
  - text (text)
  - notes (text)
  - source_license (text)
```

### Tags Table

Tags are stored in a separate table and linked via many-to-many relationships to all note types.

```
tag:
  - id (auto)
  - name (text, unique, e.g. "UH::Period::19th_Century")
```

Tag junction tables (one per note type):
```
person_tags:  { person_id, tag_id }
event_tags:   { event_id, tag_id }
qa_tags:      { qa_id, tag_id }
cloze_tags:   { cloze_id, tag_id }
```

On export, tags are reconstructed as comma-separated string: `"UH::Period::19th_Century, UH::Region::Europe"`

### Relationships

Relationships are **directed**. If A relates to B and B relates to A, that requires two separate relationship records. Each relationship has a description from the source's perspective.

Example:
- Alexander II → Alexander III: "son and successor who reversed many of Alexander II's reforms"
- Alexander III → Alexander II: "father whose assassination shaped Alexander III's conservative outlook"

All four note types (person, event, qa, cloze) can have relationships to persons and events.

#### Junction Tables

Person and Event can relate to each other and themselves:
```
person_person_links:  { source_person_id, target_person_id, description, slot }
person_event_links:   { person_id, event_id, description, slot }
event_person_links:   { event_id, person_id, description, slot }
event_event_links:    { source_event_id, target_event_id, description, slot }
```

QA can relate to persons and events:
```
qa_person_links:      { qa_id, person_id, description, slot }
qa_event_links:       { qa_id, event_id, description, slot }
```

Cloze can relate to persons and events:
```
cloze_person_links:   { cloze_id, person_id, description, slot }
cloze_event_links:    { cloze_id, event_id, description, slot }
```

All junction tables have an auto-increment `id` field (not shown above for brevity).

### Personal Fields

CSV columns prefixed with `personal` (e.g., `personal related person 1`, `personal notes`) are for individual Anki users to add their own data. These fields:
- Are **not imported** into NocoDB
- Must always be empty in the exported CSV
- Should never be edited by Claude or via NocoDB

### Images

Images are fully supported with NocoDB attachments.

Current CSV format:
```
picture: "<img alt=\"description\" src=\"uh_napoleon-bonaparte.jpg\">"
```

#### Storage

- Mount `src/media/` as volume in NocoDB container at `/app/data/media/`
- NocoDB stores attachments with metadata (filename, alt text, path)

#### Import

1. Parse `<img>` tag from CSV
2. Extract `src` (filename) and `alt` (description)
3. Create NocoDB attachment record pointing to file in mounted volume

#### Export

1. Read attachment metadata from NocoDB
2. Reconstruct `<img alt="..." src="...">` tag
3. Write to CSV

#### Adding New Images

1. Via NocoDB UI: Upload image, saved to mounted `src/media/` directory
2. Via Claude/script: Place file in `src/media/`, then reference in add/update command

## Implementation Phases

### Phase 1: NocoDB Setup
1. Create `docker-compose.yml` with SQLite backend and `src/media/` volume mount
2. Document startup instructions
3. Generate API token

### Phase 2: Schema Design
1. Create main tables via NocoDB UI or API
2. Create `tag` table and tag junction tables
3. Create relationship junction tables
4. Configure Link columns

### Phase 3: Import Script
1. Write `nocodb.py import` to read CSVs
2. Parse relationship text: "Name (dates): description" → link + description + slot
3. Parse tags string → individual tag records + links
4. Parse `<img>` tags → attachment records
5. Match/update existing records by GUID

### Phase 4: CRUD Commands
1. Implement search (fuzzy match on name/content)
2. Implement get (resolve links, show related items and tags)
3. Implement add/update (with validation)
4. Implement link (create junction table entries)

### Phase 5: Export Script
1. Write `nocodb.py export` to generate CSVs
2. Reconstruct relationship text from junction tables: "Name (dates): description"
3. Reconstruct tags as comma-separated string
4. Reconstruct `<img>` tags from attachment metadata
5. Preserve GUIDs for Anki sync
6. Write to `src/data/*.csv` with correct formatting (QUOTE_ALL, etc.)

### Phase 6: Claude Skill
1. Write `.claude/skills/nocodb.md` with examples
2. Test: search person, add person, link to event, add tags, export

### Phase 7: Integration
1. Add `nocodb-import` and `nocodb-export` commands to `main.py`
2. Update README with optional NocoDB workflow
