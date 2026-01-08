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


def parse_date(date_str: str) -> tuple[int | None, bool | None]:
    """Parse a date string into (year, is_approximate).

    Handles formats like:
    - "1842" -> (1842, False)
    - "c. 1760" -> (1760, True)
    - "c. 1,700,000 BCE" -> (-1700000, True)
    - "" -> (None, None)
    """
    if not date_str or not date_str.strip():
        return None, None

    date_str = date_str.strip()
    approximate = date_str.startswith("c. ")
    if approximate:
        date_str = date_str[3:]

    # Remove thousand separators
    date_str = date_str.replace(",", "")

    # Check for BCE
    bce = date_str.endswith(" BCE")
    if bce:
        date_str = date_str[:-4]

    year = int(date_str)
    if bce:
        year = -year

    return year, approximate


def format_date(year: int | None, approximate: bool | None) -> str:
    """Format year and approximate flag back to display string.

    - (1842, False) -> "1842"
    - (1760, True) -> "c. 1760"
    - (-1700000, True) -> "c. 1,700,000 BCE"
    - (None, None) -> ""
    """
    if year is None:
        return ""

    bce = year < 0
    abs_year = abs(year)

    # Only use thousand separators for large numbers (5+ digits)
    if abs_year >= 10000:
        year_str = f"{abs_year:,}"
    else:
        year_str = str(abs_year)

    if bce:
        year_str = f"{year_str} BCE"

    if approximate:
        year_str = f"c. {year_str}"

    return year_str


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
                RETURN n.name AS name,
                       n.birth_year AS start_year, n.birth_approximate AS start_approx,
                       n.death_year AS end_year, n.death_approximate AS end_approx
                ORDER BY n.name
                LIMIT $limit
                """,
                limit=limit,
            )
        elif label == "Event":
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.name AS name,
                       n.start_year AS start_year, n.start_approximate AS start_approx,
                       n.end_year AS end_year, n.end_approximate AS end_approx
                ORDER BY n.name
                LIMIT $limit
                """,
                limit=limit,
            )
        elif label == "QA":
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.question AS name,
                       null AS start_year, null AS start_approx,
                       null AS end_year, null AS end_approx
                ORDER BY n.question
                LIMIT $limit
                """,
                limit=limit,
            )
        else:  # Cloze
            result = session.run(
                f"""
                MATCH (n:{label})
                RETURN n.text AS name,
                       null AS start_year, null AS start_approx,
                       null AS end_year, null AS end_approx
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
        start = format_date(e["start_year"], e["start_approx"])
        end = format_date(e["end_year"], e["end_approx"])
        if start and end:
            dates = f"{start}–{end}"
        elif start:
            dates = start
        else:
            dates = ""
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
                coalesce(n.birth_year, n.start_year) AS start_year,
                coalesce(n.birth_approximate, n.start_approximate) AS start_approx,
                coalesce(n.death_year, n.end_year) AS end_year,
                coalesce(n.death_approximate, n.end_approximate) AS end_approx
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
        start = format_date(e["start_year"], e["start_approx"])
        end = format_date(e["end_year"], e["end_approx"])
        if start and end:
            dates = f"{start}–{end}"
        elif start:
            dates = start
        else:
            dates = ""
        print(f"{e['type']:<8} {name:<55} {dates:<20}")


def show_entity(driver, name: str):
    """Show all properties of an entity by name."""
    with driver.session() as session:
        # Find the entity (Person, Event, QA, or Cloze)
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Person OR n:Event OR n:QA OR n:Cloze)
              AND (toLower(n.name) = toLower($name)
                   OR toLower(n.question) = toLower($name)
                   OR toLower(n.text) = toLower($name))
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

        # Get tags
        result = session.run(
            """
            MATCH (n)-[:HAS_TAG]->(t:Tag)
            WHERE (n:Person OR n:Event OR n:QA OR n:Cloze)
              AND (toLower(n.name) = toLower($name)
                   OR toLower(n.question) = toLower($name)
                   OR toLower(n.text) = toLower($name))
            RETURN t.name AS tag
            ORDER BY tag
            """,
            name=name,
        )
        tags = [r["tag"] for r in result.data()]

        print(
            f"\n{entity_type}: {node.get('name') or node.get('question') or node.get('text')}"
        )
        print(f"  GUID: {node.get('guid', 'N/A')}")

        if entity_type == "Person":
            birth = format_date(node.get("birth_year"), node.get("birth_approximate"))
            death = format_date(node.get("death_year"), node.get("death_approximate"))
            print(f"  Birth: {birth or 'N/A'}")
            print(f"  Death: {death or 'N/A'}")
            print(f"  Known for: {node.get('known_for') or 'N/A'}")
            if node.get("picture"):
                print(f"  Picture: {node.get('picture')}")
        elif entity_type == "Event":
            start = format_date(node.get("start_year"), node.get("start_approximate"))
            end = format_date(node.get("end_year"), node.get("end_approximate"))
            print(f"  Start: {start or 'N/A'}")
            print(f"  End: {end or 'N/A'}")
            print(f"  Summary: {node.get('summary') or 'N/A'}")
        elif entity_type == "QA":
            print(f"  Question: {node.get('question') or 'N/A'}")
            print(f"  Answer: {node.get('answer') or 'N/A'}")
        elif entity_type == "Cloze":
            print(f"  Text: {node.get('text') or 'N/A'}")

        print(f"  Notes: {node.get('notes') or 'N/A'}")
        print(f"  Source: {node.get('source_license') or 'N/A'}")
        print(f"  Tags: {', '.join(tags) if tags else 'None'}")


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
            birth = format_date(node.get("birth_year"), node.get("birth_approximate"))
            death = format_date(node.get("death_year"), node.get("death_approximate"))
            print(f"  Birth: {birth or 'N/A'}, Death: {death or 'N/A'}")
        else:
            start = format_date(node.get("start_year"), node.get("start_approximate"))
            end = format_date(node.get("end_year"), node.get("end_approximate"))
            print(f"  Start: {start or 'N/A'}, End: {end or 'N/A'}")

        # Get outgoing relationships to persons
        result = session.run(
            """
            MATCH (n)-[r:RELATED_TO_PERSON]->(p:Person)
            WHERE toLower(n.name) = toLower($name)
            RETURN p.name AS target, r.description AS description,
                   p.birth_year AS start_year, p.birth_approximate AS start_approx,
                   p.death_year AS end_year, p.death_approximate AS end_approx
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
                   e.start_year AS start_year, e.start_approximate AS start_approx,
                   e.end_year AS end_year, e.end_approximate AS end_approx
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
                start = format_date(p["start_year"], p["start_approx"])
                end = format_date(p["end_year"], p["end_approx"])
                dates = f" ({start}–{end})" if start else ""
                desc = f": {p['description']}" if p["description"] else ""
                print(f"  → {p['target']}{dates}{desc}")

        if events:
            print(f"\nRelated Events ({len(events)}):")
            for e in events:
                start = format_date(e["start_year"], e["start_approx"])
                end = format_date(e["end_year"], e["end_approx"])
                dates = f" ({start}–{end})" if start else ""
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
        params: dict[str, int | None | list[str]] = {"limit": limit}

        if time_start and time_end:
            # Parse the input dates to get integer years
            start_year, _ = parse_date(time_start)
            end_year, _ = parse_date(time_end)
            # Find entities whose time range overlaps
            conditions.append(
                """
                (
                    (n:Person AND n.birth_year IS NOT NULL AND n.death_year IS NOT NULL
                     AND n.birth_year <= $time_end
                     AND n.death_year >= $time_start)
                    OR
                    (n:Event AND n.start_year IS NOT NULL AND n.end_year IS NOT NULL
                     AND n.start_year <= $time_end
                     AND n.end_year >= $time_start)
                )
                """
            )
            params["time_start"] = start_year
            params["time_end"] = end_year

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
                   coalesce(n.birth_year, n.start_year) AS start_year,
                   coalesce(n.birth_approximate, n.start_approximate) AS start_approx,
                   coalesce(n.death_year, n.end_year) AS end_year,
                   coalesce(n.death_approximate, n.end_approximate) AS end_approx,
                   tags
            ORDER BY start_year, name
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
        start = format_date(e["start_year"], e["start_approx"])
        end = format_date(e["end_year"], e["end_approx"])
        if start and end:
            dates = f"{start}–{end}"
        elif start:
            dates = start
        else:
            dates = ""
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
            values = [str(r.get(k, ""))[:200] for k in keys]
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
    picture: Optional[str] = None,
):
    """Create a new Person node."""
    validate_entity_tags(tags)
    guid = generate_guid()

    # Parse dates
    birth_year, birth_approximate = parse_date(birth)
    death_year, death_approximate = parse_date(death)

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
                birth_year: $birth_year,
                birth_approximate: $birth_approximate,
                death_year: $death_year,
                death_approximate: $death_approximate,
                notes: $notes,
                source_license: $source,
                picture: $picture
            })
            """,
            guid=guid,
            name=name,
            known_for=known_for,
            birth_year=birth_year,
            birth_approximate=birth_approximate,
            death_year=death_year,
            death_approximate=death_approximate,
            notes=notes or "",
            source=source or "",
            picture=picture or "",
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

    # Parse dates
    start_year, start_approximate = parse_date(start_date)
    end_year, end_approximate = parse_date(end_date)

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
                start_year: $start_year,
                start_approximate: $start_approximate,
                end_year: $end_year,
                end_approximate: $end_approximate,
                notes: $notes,
                source_license: $source
            })
            """,
            guid=guid,
            name=name,
            summary=summary,
            start_year=start_year,
            start_approximate=start_approximate,
            end_year=end_year,
            end_approximate=end_approximate,
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


def delete_relationship(
    driver,
    source_name: str,
    target_name: str,
):
    """Delete a relationship between two entities (Person or Event)."""
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

        # Check if relationship exists
        result = session.run(
            f"""
            MATCH (s:{source_type})-[r:{rel_type}]->(t:{target_type})
            WHERE toLower(s.name) = toLower($source) AND toLower(t.name) = toLower($target)
            RETURN r.description AS description
            """,
            source=source_name,
            target=target_name,
        )
        record = result.single()
        if not record:
            print(
                f"Error: No relationship found from '{source_name}' to '{target_name}'.",
                file=sys.stderr,
            )
            sys.exit(1)

        description = record["description"]

        # Delete relationship
        session.run(
            f"""
            MATCH (s:{source_type})-[r:{rel_type}]->(t:{target_type})
            WHERE toLower(s.name) = toLower($source) AND toLower(t.name) = toLower($target)
            DELETE r
            """,
            source=source_name,
            target=target_name,
        )

    print(f"Deleted relationship: {source_name} -> {target_name}")
    print(f"  Was: {description}")


def update_person(
    driver,
    name: str,
    new_name: Optional[str] = None,
    known_for: Optional[str] = None,
    birth: Optional[str] = None,
    death: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    picture: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    """Update an existing Person node. Only provided fields are updated."""
    if tags:
        validate_entity_tags(tags)

    with driver.session() as session:
        # Find person
        result = session.run(
            "MATCH (p:Person) WHERE toLower(p.name) = toLower($name) RETURN p",
            name=name,
        )
        record = result.single()
        if not record:
            print(f"Error: Person '{name}' not found.", file=sys.stderr)
            sys.exit(1)

        # Build SET clauses for provided fields
        set_clauses = []
        params: dict = {"name": name}

        if new_name is not None:
            set_clauses.append("p.name = $new_name")
            params["new_name"] = new_name
        if known_for is not None:
            set_clauses.append("p.known_for = $known_for")
            params["known_for"] = known_for
        if birth is not None:
            birth_year, birth_approximate = parse_date(birth)
            set_clauses.append("p.birth_year = $birth_year")
            set_clauses.append("p.birth_approximate = $birth_approximate")
            params["birth_year"] = birth_year
            params["birth_approximate"] = birth_approximate
        if death is not None:
            death_year, death_approximate = parse_date(death)
            set_clauses.append("p.death_year = $death_year")
            set_clauses.append("p.death_approximate = $death_approximate")
            params["death_year"] = death_year
            params["death_approximate"] = death_approximate
        if notes is not None:
            set_clauses.append("p.notes = $notes")
            params["notes"] = notes
        if source is not None:
            set_clauses.append("p.source_license = $source")
            params["source"] = source
        if picture is not None:
            set_clauses.append("p.picture = $picture")
            params["picture"] = picture

        if not set_clauses and not tags:
            print("No fields to update.", file=sys.stderr)
            sys.exit(1)

        if set_clauses:
            query = f"""
            MATCH (p:Person) WHERE toLower(p.name) = toLower($name)
            SET {", ".join(set_clauses)}
            """
            session.run(query, **params)

        # Add new tags (existing tags are preserved)
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (p:Person) WHERE toLower(p.name) = toLower($name)
                    MATCH (t:Tag {name: $tag})
                    MERGE (p)-[:HAS_TAG]->(t)
                    """,
                    name=name,
                    tag=tag,
                )

    print(f"Updated Person: {new_name or name}")
    if tags:
        print(f"  Added tags: {', '.join(tags)}")


def update_event(
    driver,
    name: str,
    new_name: Optional[str] = None,
    summary: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    """Update an existing Event node. Only provided fields are updated."""
    if tags:
        validate_entity_tags(tags)

    with driver.session() as session:
        # Find event
        result = session.run(
            "MATCH (e:Event) WHERE toLower(e.name) = toLower($name) RETURN e",
            name=name,
        )
        record = result.single()
        if not record:
            print(f"Error: Event '{name}' not found.", file=sys.stderr)
            sys.exit(1)

        # Build SET clauses for provided fields
        set_clauses = []
        params: dict = {"name": name}

        if new_name is not None:
            set_clauses.append("e.name = $new_name")
            params["new_name"] = new_name
        if summary is not None:
            set_clauses.append("e.summary = $summary")
            params["summary"] = summary
        if start_date is not None:
            start_year, start_approximate = parse_date(start_date)
            set_clauses.append("e.start_year = $start_year")
            set_clauses.append("e.start_approximate = $start_approximate")
            params["start_year"] = start_year
            params["start_approximate"] = start_approximate
        if end_date is not None:
            end_year, end_approximate = parse_date(end_date)
            set_clauses.append("e.end_year = $end_year")
            set_clauses.append("e.end_approximate = $end_approximate")
            params["end_year"] = end_year
            params["end_approximate"] = end_approximate
        if notes is not None:
            set_clauses.append("e.notes = $notes")
            params["notes"] = notes
        if source is not None:
            set_clauses.append("e.source_license = $source")
            params["source"] = source

        if not set_clauses and not tags:
            print("No fields to update.", file=sys.stderr)
            sys.exit(1)

        if set_clauses:
            query = f"""
            MATCH (e:Event) WHERE toLower(e.name) = toLower($name)
            SET {", ".join(set_clauses)}
            """
            session.run(query, **params)

        # Add new tags (existing tags are preserved)
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (e:Event) WHERE toLower(e.name) = toLower($name)
                    MATCH (t:Tag {name: $tag})
                    MERGE (e)-[:HAS_TAG]->(t)
                    """,
                    name=name,
                    tag=tag,
                )

    print(f"Updated Event: {new_name or name}")
    if tags:
        print(f"  Added tags: {', '.join(tags)}")


def update_qa(
    driver,
    question: str,
    new_question: Optional[str] = None,
    answer: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    """Update an existing QA node. Only provided fields are updated."""
    if tags:
        validate_entity_tags(tags)

    with driver.session() as session:
        # Find QA
        result = session.run(
            "MATCH (q:QA) WHERE toLower(q.question) = toLower($question) RETURN q",
            question=question,
        )
        record = result.single()
        if not record:
            print(
                f"Error: QA with question '{question[:50]}...' not found.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Build SET clauses for provided fields
        set_clauses = []
        params: dict = {"question": question}

        if new_question is not None:
            set_clauses.append("q.question = $new_question")
            params["new_question"] = new_question
        if answer is not None:
            set_clauses.append("q.answer = $answer")
            params["answer"] = answer
        if notes is not None:
            set_clauses.append("q.notes = $notes")
            params["notes"] = notes
        if source is not None:
            set_clauses.append("q.source_license = $source")
            params["source"] = source

        if not set_clauses and not tags:
            print("No fields to update.", file=sys.stderr)
            sys.exit(1)

        if set_clauses:
            query = f"""
            MATCH (q:QA) WHERE toLower(q.question) = toLower($question)
            SET {", ".join(set_clauses)}
            """
            session.run(query, **params)

        # Add new tags (existing tags are preserved)
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (q:QA) WHERE toLower(q.question) = toLower($question)
                    MATCH (t:Tag {name: $tag})
                    MERGE (q)-[:HAS_TAG]->(t)
                    """,
                    question=question,
                    tag=tag,
                )

    print(f"Updated QA: {(new_question or question)[:60]}...")
    if tags:
        print(f"  Added tags: {', '.join(tags)}")


def update_cloze(
    driver,
    text: str,
    new_text: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[list[str]] = None,
):
    """Update an existing Cloze node. Only provided fields are updated."""
    if tags:
        validate_entity_tags(tags)

    with driver.session() as session:
        # Find Cloze
        result = session.run(
            "MATCH (c:Cloze) WHERE toLower(c.text) = toLower($text) RETURN c",
            text=text,
        )
        record = result.single()
        if not record:
            print(
                f"Error: Cloze with text '{text[:50]}...' not found.", file=sys.stderr
            )
            sys.exit(1)

        # Build SET clauses for provided fields
        set_clauses = []
        params: dict = {"text": text}

        if new_text is not None:
            # Validate new cloze text
            is_valid, error_msg = validate_cloze_text(new_text)
            if not is_valid:
                print(f"Error: Invalid cloze text. {error_msg}", file=sys.stderr)
                sys.exit(1)
            set_clauses.append("c.text = $new_text")
            params["new_text"] = new_text
        if notes is not None:
            set_clauses.append("c.notes = $notes")
            params["notes"] = notes
        if source is not None:
            set_clauses.append("c.source_license = $source")
            params["source"] = source

        if not set_clauses and not tags:
            print("No fields to update.", file=sys.stderr)
            sys.exit(1)

        if set_clauses:
            query = f"""
            MATCH (c:Cloze) WHERE toLower(c.text) = toLower($text)
            SET {", ".join(set_clauses)}
            """
            session.run(query, **params)

        # Add new tags (existing tags are preserved)
        if tags:
            for tag in tags:
                session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                session.run(
                    """
                    MATCH (c:Cloze) WHERE toLower(c.text) = toLower($text)
                    MATCH (t:Tag {name: $tag})
                    MERGE (c)-[:HAS_TAG]->(t)
                    """,
                    text=text,
                    tag=tag,
                )

    preview = (new_text or text)[:60].replace("\n", " ")
    print(f"Updated Cloze: {preview}...")
    if tags:
        print(f"  Added tags: {', '.join(tags)}")


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
  %(prog)s show "Napoleon Bonaparte"    # Show all properties of an entity
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
  %(prog)s delete-rel "Otto von Bismarck" "Franco-Prussian War"  # Delete a relationship
  %(prog)s delete "Some Entity"

  # Update commands (only specified fields are updated)
  %(prog)s update-person "Otto von Bismarck" --known-for "Unified Germany" --death 1898
  %(prog)s update-event "Franco-Prussian War" --summary "War that unified Germany" --end 1871
  %(prog)s update-qa "What triggered the Franco-Prussian War?" --answer "The Ems Dispatch provoked France"
  %(prog)s update-cloze "The {{c1::Franco-Prussian War}} led to..." --notes "Updated note"
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

    # show command
    show_parser = subparsers.add_parser("show", help="Show all properties of an entity")
    show_parser.add_argument("name", help="Entity name (exact match)")

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
    create_person_parser.add_argument(
        "--picture", help='Picture HTML (e.g., <img src="uh_name.jpg">)'
    )

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

    # delete-rel command
    delete_rel_parser = subparsers.add_parser(
        "delete-rel", help="Delete a relationship between entities"
    )
    delete_rel_parser.add_argument("source", help="Source entity name")
    delete_rel_parser.add_argument("target", help="Target entity name")

    # update-person command
    update_person_parser = subparsers.add_parser(
        "update-person", help="Update an existing Person"
    )
    update_person_parser.add_argument("name", help="Current person name")
    update_person_parser.add_argument("--new-name", help="New name")
    update_person_parser.add_argument("--known-for", help="What they're known for")
    update_person_parser.add_argument(
        "--birth", help="Birth year (e.g., 1815, c. 500 BCE)"
    )
    update_person_parser.add_argument("--death", help="Death year")
    update_person_parser.add_argument("--notes", help="Additional notes")
    update_person_parser.add_argument("--source", help="Source & license info")
    update_person_parser.add_argument(
        "--picture", help='Picture HTML (e.g., <img src="uh_name.jpg">)'
    )
    update_person_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag to add (can repeat)"
    )

    # update-event command
    update_event_parser = subparsers.add_parser(
        "update-event", help="Update an existing Event"
    )
    update_event_parser.add_argument("name", help="Current event name")
    update_event_parser.add_argument("--new-name", help="New name")
    update_event_parser.add_argument("--summary", help="Event summary")
    update_event_parser.add_argument("--start", help="Start year")
    update_event_parser.add_argument("--end", help="End year")
    update_event_parser.add_argument("--notes", help="Additional notes")
    update_event_parser.add_argument("--source", help="Source & license info")
    update_event_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag to add (can repeat)"
    )

    # update-qa command
    update_qa_parser = subparsers.add_parser("update-qa", help="Update an existing QA")
    update_qa_parser.add_argument("question", help="Current question text")
    update_qa_parser.add_argument("--new-question", help="New question text")
    update_qa_parser.add_argument("--answer", help="New answer")
    update_qa_parser.add_argument("--notes", help="Additional notes")
    update_qa_parser.add_argument("--source", help="Source & license info")
    update_qa_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag to add (can repeat)"
    )

    # update-cloze command
    update_cloze_parser = subparsers.add_parser(
        "update-cloze", help="Update an existing Cloze"
    )
    update_cloze_parser.add_argument("text", help="Current cloze text")
    update_cloze_parser.add_argument("--new-text", help="New cloze text")
    update_cloze_parser.add_argument("--notes", help="Additional notes")
    update_cloze_parser.add_argument("--source", help="Source & license info")
    update_cloze_parser.add_argument(
        "--tag", action="append", dest="tags", help="Tag to add (can repeat)"
    )

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
        elif args.command == "show":
            show_entity(driver, args.name)
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
                args.picture,
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
        elif args.command == "delete-rel":
            delete_relationship(driver, args.source, args.target)
        elif args.command == "update-person":
            update_person(
                driver,
                args.name,
                args.new_name,
                args.known_for,
                args.birth,
                args.death,
                args.notes,
                args.source,
                args.picture,
                args.tags,
            )
        elif args.command == "update-event":
            update_event(
                driver,
                args.name,
                args.new_name,
                args.summary,
                args.start,
                args.end,
                args.notes,
                args.source,
                args.tags,
            )
        elif args.command == "update-qa":
            update_qa(
                driver,
                args.question,
                args.new_question,
                args.answer,
                args.notes,
                args.source,
                args.tags,
            )
        elif args.command == "update-cloze":
            update_cloze(
                driver,
                args.text,
                args.new_text,
                args.notes,
                args.source,
                args.tags,
            )
        elif args.command == "delete":
            delete_entity(driver, args.name)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
