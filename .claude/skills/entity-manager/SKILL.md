---
name: entity-manager
description: Create and edit historical entities (persons, events, QA cards, cloze cards) in the Neo4j database. Use when the user wants to add a new person, event, QA, or cloze, create relationships between entities, or explore existing entities to find related content.
allowed-tools: Bash, Read, Grep, Glob
---

# Entity Manager Skill

Manage historical entities (persons, events, QA, cloze) in the Neo4j graph database.

## Prerequisites

Environment variables must be set:
- `NEO4J_URI` - Database connection URI
- `NEO4J_PASSWORD` - Database password

**NEVER read the `.env` file** - credentials are loaded from environment.

**NEVER read the CSV files in `src/data/`** - always use Neo4j queries to look up entity data.

## CLI Tool

All commands use: `uv run tools/neo4j_query.py <command>`

### Query Commands

```bash
# List all tags with usage counts
uv run tools/neo4j_query.py tags

# List entities by type
uv run tools/neo4j_query.py list person
uv run tools/neo4j_query.py list event
uv run tools/neo4j_query.py list qa
uv run tools/neo4j_query.py list cloze

# Search entities (fuzzy, case-insensitive)
uv run tools/neo4j_query.py search "napoleon"

# Show all properties of an entity (name, dates, known_for/summary, notes, source, tags)
uv run tools/neo4j_query.py show "Napoleon Bonaparte"

# Get all relationships for an entity
uv run tools/neo4j_query.py relations "Napoleon Bonaparte"

# Find potentially related entities by time period and tags
uv run tools/neo4j_query.py find-related "New Entity" --start 1789 --end 1815 --tag "UH::Region::Europe"
```

### Create Commands

```bash
# Create a person
uv run tools/neo4j_query.py create-person "Otto von Bismarck" \
  --known-for "German chancellor who unified Germany" \
  --birth 1815 --death 1898 \
  --tag "UH::Region::Europe::Central" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::Politics"

# Create an event
uv run tools/neo4j_query.py create-event "Franco-Prussian War" \
  --summary "War between France and Prussia leading to German unification" \
  --start 1870 --end 1871 \
  --tag "UH::Region::Europe::Western" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::War"

# Create a QA card
uv run tools/neo4j_query.py create-qa "What triggered the Franco-Prussian War?" \
  --answer "The Ems Dispatch, a telegram edited by Bismarck to provoke France" \
  --tag "UH::Region::Europe" \
  --tag "UH::Period::19th_Century"

# Create a Cloze card (must have valid {{c1::deletion}} syntax)
uv run tools/neo4j_query.py create-cloze \
  "The {{c1::Franco-Prussian War}} (1870-1871) led to {{c2::German unification}}." \
  --tag "UH::Region::Europe" \
  --tag "UH::Period::19th_Century"

# Create a new Region or Period tag
uv run tools/neo4j_query.py create-tag "UH::Region::Europe::Central"
uv run tools/neo4j_query.py create-tag "UH::Period::19th_Century"

# Add relationship between entities
uv run tools/neo4j_query.py add-rel "Otto von Bismarck" "Franco-Prussian War" \
  "orchestrated the war to complete German unification"

# Delete a relationship between entities
uv run tools/neo4j_query.py delete-rel "Otto von Bismarck" "Franco-Prussian War"

# Delete an entity
uv run tools/neo4j_query.py delete "Some Entity"
```

### Update Commands

Update existing entities (only specified fields are modified):

```bash
# Update a person
uv run tools/neo4j_query.py update-person "Otto von Bismarck" \
  --known-for "Unified Germany through diplomacy and war" \
  --death 1898

# Update an event
uv run tools/neo4j_query.py update-event "Franco-Prussian War" \
  --summary "War that unified Germany" \
  --end 1871

# Update a QA card
uv run tools/neo4j_query.py update-qa "What triggered the Franco-Prussian War?" \
  --answer "The Ems Dispatch provoked France into declaring war"

# Update a Cloze card
uv run tools/neo4j_query.py update-cloze "The {{c1::Franco-Prussian War}}..." \
  --notes "Updated context"

# Rename an entity
uv run tools/neo4j_query.py update-person "Old Name" --new-name "New Name"
uv run tools/neo4j_query.py update-event "Old Event" --new-name "New Event Name"
```

## Tagging System

**Every card needs at least one Region and one Period tag.** Theme tags are optional.

### Region Tags (Hierarchical, 2 levels)

Format: `UH::Region::<Continent>` or `UH::Region::<Continent>::<SubRegion>`

| Continent | Sub-regions |
|-----------|-------------|
| Europe | Western, Eastern, Northern, Southern, Central |
| Asia | East, Southeast, South, Central, West (Middle East) |
| Africa | North, West, East, Central, Southern |
| Americas | North, Central, South, Caribbean |
| Oceania | Australia, Pacific |
| Global | *(no sub-regions - for worldwide events)* |

**Always use the most specific level that applies:**
- French Revolution → `UH::Region::Europe::Western`
- Mongol Empire → Multiple tags: `UH::Region::Asia::Central`, `UH::Region::Asia::East`, `UH::Region::Europe::Eastern`
- World War II → `UH::Region::Global`

### Period Tags (Centuries)

Format: `UH::Period::<Century>`

Examples:
- `UH::Period::19th_Century`
- `UH::Period::5th_Century_BCE`
- `UH::Period::Prehistory`

**Guidelines:**
- Tag based on when the event **primarily occurred**
- For events spanning centuries, use multiple period tags
- For persons, tag based on their **active period**

### Theme Tags (Curated List)

Format: `UH::Theme::<Theme>`

| Theme | Use For |
|-------|---------|
| War | Battles, conflicts, military history |
| Politics | Governance, diplomacy, revolutions |
| Economy | Trade, industry, economic systems |
| Society | Social movements, daily life |
| Culture | Art, literature, music, architecture |
| Science | Technology, medicine, discoveries |
| Religion | Faiths, religious movements |

**Theme tags cannot be created directly** - they are auto-created when used. New themes require GitHub discussion.

## Entity Types

### Date Format

Dates support:
- Plain years: `1815`, `500`
- Approximate dates: `c. 1760` (prefix with "c. ")
- BCE dates: `500 BCE`, `c. 1,700,000 BCE`
- Empty for unknown

Examples:
- `--birth 1815` → stored as year 1815, not approximate
- `--birth "c. 500 BCE"` → stored as year -500, approximate
- `--start "c. 1760"` → stored as year 1760, approximate

### Person
- `name`: Full name
- `known_for`: Brief description of significance
- `birth`/`death`: Years (see Date Format above)
- `tags`: Required (at least Region + Period)
- `notes`: Additional context (see Notes Field below)
- `source`: Attribution

### Event
- `name`: Event name
- `summary`: Brief description
- `start_date`/`end_date`: Years (see Date Format; if same year, only specify start)
- `tags`, `notes`, `source`: Same as Person

### Notes Field

The `notes` field is valuable for adding historical context that doesn't fit elsewhere. Use it to include:
- Interesting historical details and trivia
- Context that helps understand the person/event's significance
- Explanations of unusual names, terms, or dating systems
- Key dates and specific facts worth remembering

Examples:
- For "Thermidorian Reaction": "Named after 9 Thermidor Year II in the French Republican Calendar (July 27, 1794). The Republican Calendar was adopted in 1793, replacing the Gregorian calendar with 12 months of 30 days each, named after natural phenomena."
- For "Otto von Bismarck": "Bismarck began as an outspoken conservative firebrand but became famous for his pragmatic 'Realpolitik,' often outmaneuvering rivals through alliances, timing, and controlled crises."

**Always consider adding notes** when creating or updating persons and events—they enrich the learning experience.

### Picture and Source Fields (Persons only)

Images, source URLs, and licenses are provided by the user. Do not add these fields unless the user provides the information.

When the user provides an image:
- Images are stored in `src/media/` with naming convention `uh_<name-in-lowercase-kebab-case>.jpg`
- The `--picture` field takes an HTML `<img>` tag:
  ```bash
  --picture '<img src="uh_otto-von-bismarck.jpg">'
  ```

When the user provides source/license info, use this format for the `--source` field:
```bash
--source 'Claude Sonnet 4.5<br><br>Image: <a href="https://en.wikipedia.org/wiki/...">Wikipedia</a> (Public domain)'
```

The source field has two parts separated by `<br><br>`:
1. **Data source**: Who created/verified the entity data (e.g., "Claude Sonnet 4.5")
2. **Image attribution**: Link to source and license provided by user

### QA (Question & Answer)
- `question`: The question to ask
- `answer`: The expected answer
- `tags`, `notes`, `source`: Same as above

### Cloze
- `text`: Text with Anki cloze deletions `{{c1::text}}` or `{{c1::text::hint}}`
- Must have at least one cloze deletion starting at c1
- `tags`, `notes`, `source`: Same as above

## Cloze Syntax

Valid cloze formats:
- `{{c1::answer}}` - Basic cloze
- `{{c1::answer::hint}}` - Cloze with hint
- Multiple clozes: `{{c1::first}} and {{c2::second}}`

Examples:
```
"{{c1::Napoleon}} was emperor of {{c2::France}}."
"The {{c1::Treaty of Westphalia::1648}} ended the {{c2::Thirty Years' War}}."
```

## Workflow for Adding New Entities

### 1. Research and Verify

Before creating, search to avoid duplicates:
```bash
uv run tools/neo4j_query.py search "bismarck"
```

### 2. Find Related Entities

Use time period and tags to discover relationships:
```bash
uv run tools/neo4j_query.py find-related "Otto von Bismarck" \
  --start 1815 --end 1898 \
  --tag "UH::Region::Europe"
```

### 3. Review Existing Tags

Check available tags to use consistent naming:
```bash
uv run tools/neo4j_query.py tags
```

### 4. Create the Entity

Use appropriate tags following the hierarchy. The script will warn about invalid tags.

### 5. Add Relationships

Link to related persons and events with descriptive relationships:
```bash
uv run tools/neo4j_query.py add-rel "Person A" "Person B" "was mentor to"
uv run tools/neo4j_query.py add-rel "Person A" "Event X" "led the"
```

### 6. Verify Creation

```bash
uv run tools/neo4j_query.py relations "Otto von Bismarck"
```

## Relationship Guidelines

Relationships should be:
- **Directional**: Source -> Target with a description. Consider the direction carefully—adding both directions (A -> B and B -> A) can be appropriate but is not always necessary.
- **Verbose and contextual**: Describe the relationship's historical significance, not just the connection type
- **Historical**: Focus on significant historical connections

**IMPORTANT: Write detailed, contextual relationship descriptions.** Short descriptions like "led" or "participated in" are insufficient. Instead, explain the nature and significance of the relationship.

Examples of good relationship descriptions:
- ❌ Bad: "was advisor to"
- ✅ Good: "conservative advisor who guided Alexander III's autocratic governance"

- ❌ Bad: "fought against"
- ✅ Good: "rival-turned-ally-turned-opponent whose conflicts with Russia shaped Alexander's reign"

- ❌ Bad: "participated in"
- ✅ Good: "promoted Russian industrialization through protective tariffs and initiated the Trans-Siberian Railway in 1891"

- ❌ Bad: "was father of"
- ✅ Good: "father whose assassination brought Alexander III to power and shaped his reactionary policies"

Common patterns:
- Person -> Person: "was teacher of", "married", "succeeded", "defeated"
- Person -> Event: "led", "participated in", "caused", "died during"
- Event -> Person: "resulted in rise of", "led to death of"
- Event -> Event: "caused", "preceded", "was part of"

## Complete Example

```bash
# 1. Search for existing content
uv run tools/neo4j_query.py search "bismarck"

# 2. Find related entities
uv run tools/neo4j_query.py find-related "Otto von Bismarck" --start 1815 --end 1898

# 3. Create person with proper tags
uv run tools/neo4j_query.py create-person "Otto von Bismarck" \
  --known-for "Prussian statesman who unified Germany through diplomacy and war" \
  --birth 1815 --death 1898 \
  --tag "UH::Region::Europe::Central" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::Politics"

# 4. Create related event
uv run tools/neo4j_query.py create-event "Franco-Prussian War" \
  --summary "War between France and Prussia resulting in German unification" \
  --start 1870 --end 1871 \
  --tag "UH::Region::Europe::Western" \
  --tag "UH::Region::Europe::Central" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::War"

# 5. Add relationship
uv run tools/neo4j_query.py add-rel "Otto von Bismarck" "Franco-Prussian War" \
  "orchestrated through the Ems Dispatch"

# 6. Create QA card
uv run tools/neo4j_query.py create-qa "How did Bismarck provoke France into the Franco-Prussian War?" \
  --answer "By editing and publishing the Ems Dispatch to make it appear insulting to France" \
  --tag "UH::Region::Europe" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::Politics"

# 7. Create Cloze card
uv run tools/neo4j_query.py create-cloze \
  "{{c1::Otto von Bismarck}} unified Germany through {{c2::three wars}}: against {{c3::Denmark}} (1864), {{c4::Austria}} (1866), and {{c5::France}} (1870-71)." \
  --tag "UH::Region::Europe::Central" \
  --tag "UH::Period::19th_Century" \
  --tag "UH::Theme::War"

# 8. Verify
uv run tools/neo4j_query.py relations "Otto von Bismarck"
```
