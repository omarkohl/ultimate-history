#!/usr/bin/env python3
"""Query and modify Neo4j database for exploring and creating entities.

This script provides a CLI for the Neo4j graph database to:
- List all tags
- List all persons/events/qa/cloze
- Find entities by name (fuzzy search)
- Get relationships for an entity
- Find potential relationships for a new entity
- Create new persons, events, QA, cloze, and relationships
"""

import argparse
import os
import re
import sys
import uuid
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def get_driver():
    """Get Neo4j driver from environment variables."""
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        print(
            "Error: Set NEO4J_URI and NEO4J_PASSWORD environment variables",
            file=sys.stderr,
        )
        sys.exit(1)

    return GraphDatabase.driver(uri, auth=(username, password))


def list_tags(driver, limit: int = 100):
    """List all tags in the database."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (t:Tag)<-[:HAS_TAG]-(n)
            RETURN t.name AS tag, count(n) AS count
            ORDER BY count DESC, tag
            LIMIT $limit
            """,
            limit=limit,
        )
        tags = result.data()

    if not tags:
        print("No tags found.")
        return

    print(f"{'Tag':<50} {'Count':>6}")
    print("-" * 58)
    for t in tags:
        print(f"{t['tag']:<50} {t['count']:>6}")


def list_entities(driver, entity_type: str, limit: int = 50):
    """List entities of a given type."""
    label = entity_type.capitalize()
    if label not in ("Person", "Event", "Qa", "Cloze"):
        if label == "Qa":
            label = "QA"
        else:
            print(f"Unknown entity type: {entity_type}", file=sys.stderr)
            sys.exit(1)

    with driver.session() as session:
        if label == "Person":
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.name AS name, n.birth AS start, n.death AS end
                ORDER BY n.name
                LIMIT $limit
                """,
                limit=limit,
            )
        elif label == "Event":
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.name AS name, n.start_date AS start, n.end_date AS end
                ORDER BY n.name
                LIMIT $limit
                """,
                limit=limit,
            )
        elif label == "QA":
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.question AS name, null AS start, null AS end
                ORDER BY n.question
                LIMIT $limit
                """,
                limit=limit,
            )
        else:  # Cloze
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.text AS name, null AS start, null AS end
                ORDER BY n.text
                LIMIT $limit
                """,
                limit=limit,
            )

        entities = result.data()

    if not entities:
        print(f"No {label}s found.")
        return

    print(f"{'Name':<60} {'Dates':<20}")
    print("-" * 82)
    for e in entities:
        name = (e["name"] or "")[:58]
        dates = ""
        if e["start"] and e["end"]:
            dates = f"{e['start']}–{e['end']}"
        elif e["start"]:
            dates = str(e["start"])
        print(f"{name:<60} {dates:<20}")


def search_entities(driver, search_term: str, limit: int = 20):
    """Search for entities by name (case-insensitive contains)."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event OR n:QA OR n:Cloze)
              AND (toLower(n.name) CONTAINS toLower($search_term)
                   OR toLower(n.question) CONTAINS toLower($search_term)
                   OR toLower(n.text) CONTAINS toLower($search_term))
            RETURN
                labels(n)[0] AS type,
                coalesce(n.name, n.question, n.text) AS name,
                n.guid AS guid,
                coalesce(n.birth, n.start_date) AS start,
                coalesce(n.death, n.end_date) AS end
            ORDER BY name
            LIMIT $limit
            """,
            search_term=search_term,
            limit=limit,
        )
        entities = result.data()

    if not entities:
        print(f"No entities found matching '{search_term}'.")
        return

    print(f"{'Type':<8} {'Name':<55} {'Dates':<20}")
    print("-" * 85)
    for e in entities:
        name = (e["name"] or "")[:53]
        dates = ""
        if e["start"] and e["end"]:
            dates = f"{e['start']}–{e['end']}"
        elif e["start"]:
            dates = str(e["start"])
        print(f"{e['type']:<8} {name:<55} {dates:<20}")


def get_relationships(driver, name: str):
    """Get all relationships for an entity by name."""
    with driver.session() as session:
        # Find the entity
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event)
              AND toLower(n.name) = toLower($name)
            RETURN n, labels(n)[0] AS type
            LIMIT 1
            """,
            name=name,
        )
        record = result.single()

        if not record:
            print(f"Entity '{name}' not found.", file=sys.stderr)
            return

        node = record["n"]
        entity_type = record["type"]
        print(f"\n{entity_type}: {node['name']}")
        if entity_type == "Person":
            print(
                f"  Birth: {node.get('birth', 'N/A')}, Death: {node.get('death', 'N/A')}"
            )
        else:
            print(
                f"  Start: {node.get('start_date', 'N/A')}, End: {node.get('end_date', 'N/A')}"
            )

        # Get outgoing relationships to persons
        result = session.run(
            """
            MATCH (n)-[r:RELATED_TO_PERSON]->(p:Person)
            WHERE toLower(n.name) = toLower($name)
            RETURN p.name AS target, r.description AS description,
                   p.birth AS start, p.death AS end
            ORDER BY p.name
            """,
            name=name,
        )
        persons = result.data()

        # Get outgoing relationships to events
        result = session.run(
            """
            MATCH (n)-[r:RELATED_TO_EVENT]->(e:Event)
            WHERE toLower(n.name) = toLower($name)
            RETURN e.name AS target, r.description AS description,
                   e.start_date AS start, e.end_date AS end
            ORDER BY e.name
            """,
            name=name,
        )
        events = result.data()

        # Get incoming relationships from other entities
        result = session.run(
            """
            MATCH (other)-[r]->(n)
            WHERE toLower(n.name) = toLower($name)
              AND type(r) IN ['RELATED_TO_PERSON', 'RELATED_TO_EVENT']
            RETURN labels(other)[0] AS type,
                   coalesce(other.name, other.question, other.text) AS source,
                   r.description AS description
            ORDER BY source
            """,
            name=name,
        )
        incoming = result.data()

        # Get tags
        result = session.run(
            """
            MATCH (n)-[:HAS_TAG]->(t:Tag)
            WHERE toLower(n.name) = toLower($name)
            RETURN t.name AS tag
            ORDER BY tag
            """,
            name=name,
        )
        tags = [r["tag"] for r in result.data()]

        print(f"\nTags: {', '.join(tags) if tags else 'None'}")

        if persons:
            print(f"\nRelated Persons ({len(persons)}):")
            for p in persons:
                dates = f" ({p['start']}–{p['end']})" if p["start"] else ""
                desc = f": {p['description']}" if p["description"] else ""
                print(f"  → {p['target']}{dates}{desc}")

        if events:
            print(f"\nRelated Events ({len(events)}):")
            for e in events:
                dates = f" ({e['start']}–{e['end']})" if e["start"] else ""
                desc = f": {e['description']}" if e["description"] else ""
                print(f"  → {e['target']}{dates}{desc}")

        if incoming:
            print(f"\nReferenced By ({len(incoming)}):")
            for i in incoming:
                desc = f": {i['description']}" if i["description"] else ""
                source = (i["source"] or "")[:60]
                print(f"  ← [{i['type']}] {source}{desc}")


def find_related(
    driver,
    name: str,
    time_start: Optional[str],
    time_end: Optional[str],
    tags: Optional[list[str]],
    limit: int = 20,
):
    """Find potentially related entities based on time period and tags."""
    with driver.session() as session:
        # Build a query to find entities with overlapping time periods or matching tags
        conditions = []
        params: dict[str, int | str | list[str]] = {"limit": limit}

        if time_start and time_end:
            # Find entities whose time range overlaps
            conditions.append(
                """
                (
                    (n:Person AND n.birth IS NOT NULL AND n.death IS NOT NULL
                     AND toInteger(n.birth) <= toInteger($time_end)
                     AND toInteger(n.death) >= toInteger($time_start))
                    OR
                    (n:Event AND n.start_date IS NOT NULL AND n.end_date IS NOT NULL
                     AND toInteger(n.start_date) <= toInteger($time_end)
                     AND toInteger(n.end_date) >= toInteger($time_start))
                )
                """
            )
            params["time_start"] = time_start
            params["time_end"] = time_end

        if tags:
            conditions.append(
                """
                EXISTS {
                    MATCH (n)-[:HAS_TAG]->(t:Tag)
                    WHERE t.name IN $tags
                }
                """
            )
            params["tags"] = tags

        where_clause = " AND ".join(conditions) if conditions else "true"

        result = session.run(
            f"""
            MATCH (n)
            WHERE (n:Person OR n:Event)
              AND n.name <> $name
              AND {where_clause}
            OPTIONAL MATCH (n)-[:HAS_TAG]->(t:Tag)
            WITH n, labels(n)[0] AS type, collect(t.name) AS tags
            RETURN type,
                   n.name AS name,
                   coalesce(n.birth, n.start_date) AS start,
                   coalesce(n.death, n.end_date) AS end,
                   tags
            ORDER BY start, name
            LIMIT $limit
            """,
            name=name,
            **params,
        )
        entities = result.data()

    if not entities:
        print("No related entities found with the given criteria.")
        return

    print(f"Potentially related entities for '{name}':")
    print(f"{'Type':<8} {'Name':<45} {'Dates':<15} {'Tags'}")
    print("-" * 100)
    for e in entities:
        ename = (e["name"] or "")[:43]
        dates = ""
        if e["start"] and e["end"]:
            dates = f"{e['start']}–{e['end']}"
        elif e["start"]:
            dates = str(e["start"])
        etags = ", ".join(e["tags"][:3]) if e["tags"] else ""
        if len(e["tags"]) > 3:
            etags += "..."
        print(f"{e['type']:<8} {ename:<45} {dates:<15} {etags}")


def run_cypher(driver, query: str):
    """Run an arbitrary Cypher query."""
    with driver.session() as session:
        result = session.run(query)
        records = result.data()

    if not records:
        print("No results.")
        return

    # Print as simple table
    if records:
        keys = list(records[0].keys())
        print(" | ".join(keys))
        print("-" * (len(" | ".join(keys)) + 10))
        for r in records[:50]:  # Limit output
            values = [str(r.get(k, ""))[:50] for k in keys]
            print(" | ".join(values))
        if len(records) > 50:
            print(f"... and {len(records) - 50} more rows")


def generate_guid() -> str:
    """Generate a short unique ID similar to existing guids."""
    # Use base64-like encoding for compact representation
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz+/=[]{}()<>*&^%$#@!~"
    uid = uuid.uuid4().bytes
    result = []
    for i in range(0, 10):
        idx = uid[i] % len(chars)
        result.append(chars[idx])
    return "".join(result)


def create_person(
    driver,
    name: str,
    known_for: str,
    birth: str,
    death: str,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
):
    """Create a new Person node."""
    validate_entity_tags(tags)
    guid = generate_guid()

    with driver.session() as session:
        # Check if person already exists
        result = session.run(
            "MATCH (p:Person) WHERE toLower(p.name) = toLower($name) RETURN p.name",
            name=name,
        )
        if result.single():
            print(f"Error: Person '{name}' already exists.", file=sys.stderr)
            sys.exit(1)

        # Create person
        session.run(
            """
            CREATE (p:Person {
                guid: $guid,
                name: $name,
                known_for: $known_for,
                birth: $birth,
                death: $death,
                notes: $notes,
                source_license: $source,
                picture: ''
            })
            """,
            guid=guid,
            name=name,
            known_for=known_for,
            birth=birth,
            death=death,
            notes=notes or "",
            source=source or "",
        )

        # Create tags
        if tags:
            for tag in tags:
                # Create tag if it doesn't exist
                session.run(
                    "MERGE (t:Tag {name: $tag})",
                    tag=tag,
                )
                # Link person to tag
                session.run(
                    """
                    MATCH (p:Person {guid: $guid}), (t:Tag {name: $tag})
                    CREATE (p)-[:HAS_TAG]->(t)
                    """,
                    guid=guid,
                    tag=tag,
                )

    print(f"Created Person: {name} (guid: {guid})")
    if tags:
        print(f"  Tags: {', '.join(tags)}")


def create_event(
    driver,
    name: str,
    summary: str,
    start_date: str,
    end_date: str,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
):
    """Create a new Event node."""
    validate_entity_tags(tags)
    guid = generate_guid()

    with driver.session() as session:
        # Check if event already exists
        result = session.run(
            "MATCH (e:Event) WHERE toLower(e.name) = toLower($name) RETURN e.name",
            name=name,
        )
        if result.single():
            print(f"Error: Event '{name}' already exists.", file=sys.stderr)
            sys.exit(1)

        # Create event
        session.run(
            """
            CREATE (e:Event {
                guid: $guid,
                name: $name,
                summary: $summary,
                start_date: $start_date,
                end_date: $end_date,
                notes: $notes,
                source_license: $source
            })
            """,
            guid=guid,
            name=name,
            summary=summary,
            start_date=start_date,
            end_date=end_date,
            notes=notes or "",
            source=source or "",
        )

        # Create tags
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (e:Event {guid: $guid}), (t:Tag {name: $tag})
                    CREATE (e)-[:HAS_TAG]->(t)
                    """,
                    guid=guid,
                    tag=tag,
                )

    print(f"Created Event: {name} (guid: {guid})")
    if tags:
        print(f"  Tags: {', '.join(tags)}")


def validate_cloze_text(text: str) -> tuple[bool, str]:
    """Validate that cloze text contains valid Anki cloze deletions.

    Returns (is_valid, error_message).
    """
    # Find all cloze patterns like {{c1::text}} or {{c1::text::hint}}
    pattern = r"\{\{c(\d+)::([^}]+)\}\}"
    matches = re.findall(pattern, text)

    if not matches:
        return False, "No cloze deletions found. Use {{c1::text}} format."

    # Check that cloze numbers start at 1 and are sequential (with gaps allowed)
    cloze_numbers = sorted(set(int(m[0]) for m in matches))

    if cloze_numbers[0] != 1:
        return False, f"Cloze numbers must start at 1, found: {cloze_numbers[0]}"

    # Check for empty cloze content
    for num, content in matches:
        # Content might have hint like "text::hint", extract just the text
        actual_text = content.split("::")[0].strip()
        if not actual_text:
            return False, f"Cloze {{{{c{num}::}}}} has empty content."

    return True, ""


def create_qa(
    driver,
    question: str,
    answer: str,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
):
    """Create a new QA node."""
    validate_entity_tags(tags)
    guid = generate_guid()

    with driver.session() as session:
        # Check if QA already exists with same question
        result = session.run(
            "MATCH (q:QA) WHERE toLower(q.question) = toLower($question) RETURN q.question",
            question=question,
        )
        if result.single():
            print("Error: QA with this question already exists.", file=sys.stderr)
            sys.exit(1)

        # Create QA
        session.run(
            """
            CREATE (q:QA {
                guid: $guid,
                question: $question,
                answer: $answer,
                notes: $notes,
                source_license: $source
            })
            """,
            guid=guid,
            question=question,
            answer=answer,
            notes=notes or "",
            source=source or "",
        )

        # Create tags
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (q:QA {guid: $guid}), (t:Tag {name: $tag})
                    CREATE (q)-[:HAS_TAG]->(t)
                    """,
                    guid=guid,
                    tag=tag,
                )

    print(f"Created QA: {question[:60]}... (guid: {guid})")
    if tags:
        print(f"  Tags: {', '.join(tags)}")


def create_cloze(
    driver,
    text: str,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
):
    """Create a new Cloze node."""
    validate_entity_tags(tags)

    # Validate cloze text
    is_valid, error_msg = validate_cloze_text(text)
    if not is_valid:
        print(f"Error: Invalid cloze text. {error_msg}", file=sys.stderr)
        sys.exit(1)

    guid = generate_guid()

    with driver.session() as session:
        # Check if Cloze already exists with same text
        result = session.run(
            "MATCH (c:Cloze) WHERE toLower(c.text) = toLower($text) RETURN c.text",
            text=text,
        )
        if result.single():
            print("Error: Cloze with this text already exists.", file=sys.stderr)
            sys.exit(1)

        # Create Cloze
        session.run(
            """
            CREATE (c:Cloze {
                guid: $guid,
                text: $text,
                notes: $notes,
                source_license: $source
            })
            """,
            guid=guid,
            text=text,
            notes=notes or "",
            source=source or "",
        )

        # Create tags
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (c:Cloze {guid: $guid}), (t:Tag {name: $tag})
                    CREATE (c)-[:HAS_TAG]->(t)
                    """,
                    guid=guid,
                    tag=tag,
                )

    # Show preview of cloze (first 60 chars)
    preview = text[:60].replace("\n", " ")
    print(f"Created Cloze: {preview}... (guid: {guid})")
    if tags:
        print(f"  Tags: {', '.join(tags)}")


# Valid tag structure
# Regions: 2-level hierarchy (continent::sub-region)
VALID_REGIONS = {
    "Europe": ["Western", "Eastern", "Northern", "Southern", "Central"],
    "Asia": ["East", "Southeast", "South", "Central", "West"],
    "Africa": ["North", "West", "East", "Central", "Southern"],
    "Americas": ["North", "Central", "South", "Caribbean"],
    "Oceania": ["Australia", "Pacific"],
    "Global": [],  # No sub-regions
}

# Themes: curated list (new themes require discussion)
VALID_THEMES = [
    "War",
    "Politics",
    "Economy",
    "Society",
    "Culture",
    "Science",
    "Religion",
]


def validate_tag(tag_name: str) -> tuple[bool, str]:
    """Validate a tag against the allowed structure.

    Returns (is_valid, error_message).
    """
    if not tag_name.startswith("UH::"):
        return False, "Tag must start with 'UH::'"

    parts = tag_name.split("::")
    if len(parts) < 3:
        return False, "Tag must have at least 3 parts (e.g., UH::Region::Europe)"

    category = parts[1]

    if category == "Region":
        if len(parts) < 3 or len(parts) > 4:
            return (
                False,
                "Region tags must be UH::Region::<continent> or UH::Region::<continent>::<sub-region>",
            )
        continent = parts[2]
        if continent not in VALID_REGIONS:
            return (
                False,
                f"Unknown continent '{continent}'. Valid: {', '.join(VALID_REGIONS.keys())}",
            )
        if len(parts) == 4:
            sub_region = parts[3]
            valid_subs = VALID_REGIONS[continent]
            if not valid_subs:
                return False, f"'{continent}' has no sub-regions"
            if sub_region not in valid_subs:
                return (
                    False,
                    f"Unknown sub-region '{sub_region}' for {continent}. Valid: {', '.join(valid_subs)}",
                )
        return True, ""

    elif category == "Period":
        if len(parts) != 3:
            return False, "Period tags must be UH::Period::<period>"
        period = parts[2]
        # Allow: Prehistory, centuries (1st_Century, 19th_Century, 5th_Century_BCE), millennia
        if period == "Prehistory":
            return True, ""
        if "_Millennium_BCE" in period or "_Century" in period:
            return True, ""
        return (
            False,
            f"Invalid period '{period}'. Use format like '19th_Century', '5th_Century_BCE', or 'Prehistory'",
        )

    elif category == "Theme":
        if len(parts) != 3:
            return False, "Theme tags must be UH::Theme::<theme>"
        theme = parts[2]
        if theme not in VALID_THEMES:
            return (
                False,
                f"Unknown theme '{theme}'. Valid: {', '.join(VALID_THEMES)}. New themes require discussion.",
            )
        return True, ""

    else:
        return False, f"Unknown category '{category}'. Valid: Region, Period, Theme"


def validate_entity_tags(tags: Optional[list[str]]) -> None:
    """Validate tags for an entity, warning about invalid ones."""
    if not tags:
        return
    for tag in tags:
        is_valid, error_msg = validate_tag(tag)
        if not is_valid:
            print(f"Warning: Invalid tag '{tag}'. {error_msg}", file=sys.stderr)


def create_tag(driver, tag_name: str):
    """Create a new tag (only Region and Period tags allowed via CLI)."""
    # Theme tags cannot be created directly - they're auto-created when used
    if tag_name.startswith("UH::Theme::"):
        print(
            "Error: Theme tags cannot be created directly. They are auto-created when "
            "used on entities. To propose a new theme, open a GitHub issue.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate tag format
    is_valid, error_msg = validate_tag(tag_name)
    if not is_valid:
        print(f"Error: Invalid tag. {error_msg}", file=sys.stderr)
        sys.exit(1)

    with driver.session() as session:
        # Check if tag already exists
        result = session.run(
            "MATCH (t:Tag {name: $name}) RETURN t.name",
            name=tag_name,
        )
        if result.single():
            print(f"Error: Tag '{tag_name}' already exists.", file=sys.stderr)
            sys.exit(1)

        # Create tag
        session.run("CREATE (t:Tag {name: $name})", name=tag_name)

    print(f"Created Tag: {tag_name}")


def add_relationship(
    driver,
    source_name: str,
    target_name: str,
    description: str,
):
    """Add a relationship between two entities (Person or Event)."""
    with driver.session() as session:
        # Find source entity
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event) AND toLower(n.name) = toLower($name)
            RETURN n, labels(n)[0] AS type
            """,
            name=source_name,
        )
        source = result.single()
        if not source:
            print(f"Error: Source entity '{source_name}' not found.", file=sys.stderr)
            sys.exit(1)

        # Find target entity
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event) AND toLower(n.name) = toLower($name)
            RETURN n, labels(n)[0] AS type
            """,
            name=target_name,
        )
        target = result.single()
        if not target:
            print(f"Error: Target entity '{target_name}' not found.", file=sys.stderr)
            sys.exit(1)

        source_type = source["type"]
        target_type = target["type"]
        rel_type = f"RELATED_TO_{target_type.upper()}"

        # Check if relationship already exists
        result = session.run(
            f"""
            MATCH (s:{source_type})-[r:{rel_type}]->(t:{target_type})
            WHERE toLower(s.name) = toLower($source) AND toLower(t.name) = toLower($target)
            RETURN r
            """,
            source=source_name,
            target=target_name,
        )
        if result.single():
            print(
                f"Error: Relationship already exists from '{source_name}' to '{target_name}'.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Create relationship
        session.run(
            f"""
            MATCH (s:{source_type}), (t:{target_type})
            WHERE toLower(s.name) = toLower($source) AND toLower(t.name) = toLower($target)
            CREATE (s)-[:{rel_type} {{description: $description}}]->(t)
            """,
            source=source_name,
            target=target_name,
            description=description,
        )

    print(f"Created relationship: {source_name} -> {target_name}")
    print(f"  Type: {rel_type}")
    print(f"  Description: {description}")


def delete_entity(driver, name: str):
    """Delete an entity by name."""
    with driver.session() as session:
        # Find entity
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event OR n:QA OR n:Cloze)
              AND toLower(coalesce(n.name, n.question, n.text)) = toLower($name)
            RETURN n, labels(n)[0] AS type
            """,
            name=name,
        )
        record = result.single()
        if not record:
            print(f"Error: Entity '{name}' not found.", file=sys.stderr)
            sys.exit(1)

        entity_type = record["type"]

        # Delete entity and all its relationships
        session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event OR n:QA OR n:Cloze)
              AND toLower(coalesce(n.name, n.question, n.text)) = toLower($name)
            DETACH DELETE n
            """,
            name=name,
        )

    print(f"Deleted {entity_type}: {name}")


def main():
    parser = argparse.ArgumentParser(
        description="Query and modify Neo4j database for Ultimate History data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Query commands
  %(prog)s tags                         # List all tags with counts
  %(prog)s list person                  # List all persons
  %(prog)s list event --limit 100       # List 100 events
  %(prog)s search "napoleon"            # Search for entities containing "napoleon"
  %(prog)s relations "Napoleon Bonaparte"  # Get relationships for Napoleon
  %(prog)s find-related "New Entity" --start 1789 --end 1815 --tag UH::Region::Europe
  %(prog)s cypher "MATCH (n:Person) RETURN n.name LIMIT 5"

  # Create commands (tags: UH::Region::<continent>::<sub>, UH::Period::<century>, UH::Theme::<theme>)
  %(prog)s create-person "Otto von Bismarck" --known-for "German chancellor" --birth 1815 --death 1898 \\
      --tag UH::Region::Europe::Central --tag UH::Period::19th_Century --tag UH::Theme::Politics
  %(prog)s create-event "Franco-Prussian War" --summary "War between France and Prussia" --start 1870 --end 1871 \\
      --tag UH::Region::Europe::Western --tag UH::Period::19th_Century --tag UH::Theme::War
  %(prog)s create-qa "What triggered the Franco-Prussian War?" --answer "The Ems Dispatch" \\
      --tag UH::Region::Europe --tag UH::Period::19th_Century
  %(prog)s create-cloze "The {{c1::Franco-Prussian War}} led to {{c2::German unification}}." \\
      --tag UH::Region::Europe --tag UH::Period::19th_Century
  %(prog)s create-tag "UH::Region::Europe::Central"  # Only Region and Period tags can be created
  %(prog)s create-tag "UH::Period::19th_Century"
  %(prog)s add-rel "Otto von Bismarck" "Franco-Prussian War" "orchestrated the war to unify Germany"
  %(prog)s delete "Some Entity"
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # tags command
    tags_parser = subparsers.add_parser("tags", help="List all tags")
    tags_parser.add_argument("--limit", type=int, default=100, help="Max tags to show")

    # list command
    list_parser = subparsers.add_parser("list", help="List entities of a type")
    list_parser.add_argument(
        "type", choices=["person", "event", "qa", "cloze"], help="Entity type"
    )
    list_parser.add_argument(
        "--limit", type=int, default=50, help="Max entities to show"
    )

    # search command
    search_parser = subparsers.add_parser("search", help="Search entities by name")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--limit", type=int, default=20, help="Max results to show"
    )

    # relations command
    rel_parser = subparsers.add_parser(
        "relations", help="Get relationships for an entity"
    )
    rel_parser.add_argument("name", help="Entity name (exact match)")

    # find-related command
    find_parser = subparsers.add_parser(
        "find-related", help="Find potentially related entities"
    )
    find_parser.add_argument("name", help="Name of the new entity")
    find_parser.add_argument("--start", help="Start year (e.g., 1789)")
    find_parser.add_argument("--end", help="End year (e.g., 1815)")
    find_parser.add_argument(
        "--tag", action="append", dest="tags", help="Filter by tag (can repeat)"
    )
    find_parser.add_argument(
        "--limit", type=int, default=20, help="Max results to show"
    )

    # cypher command
    cypher_parser = subparsers.add_parser("cypher", help="Run arbitrary Cypher query")
    cypher_parser.add_argument("query", help="Cypher query to run")

    # create-person command
    create_person_parser = subparsers.add_parser(
        "create-person", help="Create a new Person"
    )
    create_person_parser.add_argument("name", help="Person's name")
    create_person_parser.add_argument(
        "--known-for", required=True, help="What they're known for"
    )
    create_person_parser.add_argument("--birth", required=True, help="Birth year")
    create_person_parser.add_argument("--death", required=True, help="Death year")
    create_person_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag (can repeat)"
    )
    create_person_parser.add_argument("--notes", help="Additional notes")
    create_person_parser.add_argument("--source", help="Source & license info")

    # create-event command
    create_event_parser = subparsers.add_parser(
        "create-event", help="Create a new Event"
    )
    create_event_parser.add_argument("name", help="Event name")
    create_event_parser.add_argument("--summary", required=True, help="Event summary")
    create_event_parser.add_argument("--start", required=True, help="Start year")
    create_event_parser.add_argument("--end", required=True, help="End year")
    create_event_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag (can repeat)"
    )
    create_event_parser.add_argument("--notes", help="Additional notes")
    create_event_parser.add_argument("--source", help="Source & license info")

    # create-qa command
    create_qa_parser = subparsers.add_parser("create-qa", help="Create a new QA card")
    create_qa_parser.add_argument("question", help="The question")
    create_qa_parser.add_argument("--answer", required=True, help="The answer")
    create_qa_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag (can repeat)"
    )
    create_qa_parser.add_argument("--notes", help="Additional notes")
    create_qa_parser.add_argument("--source", help="Source & license info")

    # create-cloze command
    create_cloze_parser = subparsers.add_parser(
        "create-cloze", help="Create a new Cloze card"
    )
    create_cloze_parser.add_argument("text", help="Cloze text with {{c1::deletions}}")
    create_cloze_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag (can repeat)"
    )
    create_cloze_parser.add_argument("--notes", help="Additional notes")
    create_cloze_parser.add_argument("--source", help="Source & license info")

    # create-tag command
    create_tag_parser = subparsers.add_parser(
        "create-tag", help="Create a new tag (Region or Period only)"
    )
    create_tag_parser.add_argument(
        "name", help="Tag name (must start with UH::Region:: or UH::Period::)"
    )

    # add-rel command
    add_rel_parser = subparsers.add_parser(
        "add-rel", help="Add a relationship between entities"
    )
    add_rel_parser.add_argument("source", help="Source entity name")
    add_rel_parser.add_argument("target", help="Target entity name")
    add_rel_parser.add_argument("description", help="Relationship description")

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete an entity")
    delete_parser.add_argument("name", help="Entity name to delete")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    driver = get_driver()

    try:
        if args.command == "tags":
            list_tags(driver, args.limit)
        elif args.command == "list":
            list_entities(driver, args.type, args.limit)
        elif args.command == "search":
            search_entities(driver, args.query, args.limit)
        elif args.command == "relations":
            get_relationships(driver, args.name)
        elif args.command == "find-related":
            find_related(driver, args.name, args.start, args.end, args.tags, args.limit)
        elif args.command == "cypher":
            run_cypher(driver, args.query)
        elif args.command == "create-person":
            create_person(
                driver,
                args.name,
                args.known_for,
                args.birth,
                args.death,
                args.tags,
                args.notes,
                args.source,
            )
        elif args.command == "create-event":
            create_event(
                driver,
                args.name,
                args.summary,
                args.start,
                args.end,
                args.tags,
                args.notes,
                args.source,
            )
        elif args.command == "create-qa":
            create_qa(
                driver,
                args.question,
                args.answer,
                args.tags,
                args.notes,
                args.source,
            )
        elif args.command == "create-cloze":
            create_cloze(
                driver,
                args.text,
                args.tags,
                args.notes,
                args.source,
            )
        elif args.command == "create-tag":
            create_tag(driver, args.name)
        elif args.command == "add-rel":
            add_relationship(driver, args.source, args.target, args.description)
        elif args.command == "delete":
            delete_entity(driver, args.name)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
