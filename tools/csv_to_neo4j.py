#!/usr/bin/env python3
"""Import CSV data into Neo4j AuraDB."""

import argparse
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from utils import get_data_dir, parse_reference


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


def load_csv(path: Path) -> list[dict]:
    """Load a CSV file and return list of row dicts."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def drop_all(tx):
    """Drop all constraints, indexes, and data."""
    # Get and drop all constraints
    constraints = tx.run("SHOW CONSTRAINTS").data()
    for c in constraints:
        tx.run(f"DROP CONSTRAINT {c['name']}")

    # Get and drop all indexes
    indexes = tx.run("SHOW INDEXES").data()
    for idx in indexes:
        if idx["type"] != "LOOKUP":  # Don't drop built-in lookup indexes
            tx.run(f"DROP INDEX {idx['name']}")


def clear_database(tx):
    """Delete all nodes and relationships."""
    tx.run("MATCH (n) DETACH DELETE n")


def create_constraints(tx):
    """Create uniqueness constraints (which also create indexes)."""
    tx.run(
        "CREATE CONSTRAINT person_guid IF NOT EXISTS FOR (p:Person) REQUIRE p.guid IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT event_guid IF NOT EXISTS FOR (e:Event) REQUIRE e.guid IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT qa_guid IF NOT EXISTS FOR (q:QA) REQUIRE q.guid IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT cloze_guid IF NOT EXISTS FOR (c:Cloze) REQUIRE c.guid IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE"
    )


def create_persons(tx, persons: list[dict], person_lookup: dict):
    """Create Person nodes."""
    for row in persons:
        birth_year, birth_approximate = parse_date(row["date of birth"])
        death_year, death_approximate = parse_date(row["date of death"])
        tx.run(
            """
            CREATE (p:Person {
                name: $name,
                known_for: $known_for,
                birth_year: $birth_year,
                birth_approximate: $birth_approximate,
                death_year: $death_year,
                death_approximate: $death_approximate,
                picture: $picture,
                notes: $notes,
                source_license: $source_license,
                guid: $guid
            })
            """,
            guid=row["guid"],
            name=row["name"],
            known_for=row["known for"],
            birth_year=birth_year,
            birth_approximate=birth_approximate,
            death_year=death_year,
            death_approximate=death_approximate,
            picture=row["picture"],
            notes=row["notes"],
            source_license=row["source & license"],
        )
        person_lookup[row["name"]] = row["guid"]


def create_events(tx, events: list[dict], event_lookup: dict):
    """Create Event nodes."""
    for row in events:
        start_year, start_approximate = parse_date(row["start date"])
        end_year, end_approximate = parse_date(row["end date"])
        tx.run(
            """
            CREATE (e:Event {
                name: $name,
                summary: $summary,
                start_year: $start_year,
                start_approximate: $start_approximate,
                end_year: $end_year,
                end_approximate: $end_approximate,
                notes: $notes,
                source_license: $source_license,
                guid: $guid
            })
            """,
            guid=row["guid"],
            name=row["name"],
            summary=row["summary"],
            start_year=start_year,
            start_approximate=start_approximate,
            end_year=end_year,
            end_approximate=end_approximate,
            notes=row["notes"],
            source_license=row["source & license"],
        )
        event_lookup[row["name"]] = row["guid"]


def create_qas(tx, qas: list[dict]):
    """Create QA nodes."""
    for row in qas:
        tx.run(
            """
            CREATE (q:QA {
                question: $question,
                answer: $answer,
                notes: $notes,
                source_license: $source_license,
                guid: $guid
            })
            """,
            guid=row["guid"],
            question=row["question"],
            answer=row["answer"],
            notes=row["notes"],
            source_license=row["source & license"],
        )


def create_clozes(tx, clozes: list[dict]):
    """Create Cloze nodes."""
    for row in clozes:
        tx.run(
            """
            CREATE (c:Cloze {
                text: $text,
                notes: $notes,
                source_license: $source_license,
                guid: $guid
            })
            """,
            guid=row["guid"],
            text=row["text"],
            notes=row["notes"],
            source_license=row["source & license"],
        )


def create_tags(tx, all_rows: list[dict]):
    """Create unique Tag nodes from all entities."""
    tags = set()
    for row in all_rows:
        if row.get("tags"):
            for tag in row["tags"].split(", "):
                tag = tag.strip()
                if tag:
                    tags.add(tag)

    for tag in tags:
        tx.run("CREATE (t:Tag {name: $name})", name=tag)


def create_tag_edges(tx, rows: list[dict], label: str):
    """Create HAS_TAG edges from entities to tags."""
    for row in rows:
        if not row.get("tags"):
            continue
        for tag in row["tags"].split(", "):
            tag = tag.strip()
            if tag:
                tx.run(
                    f"""
                    MATCH (n:{label} {{guid: $guid}}), (t:Tag {{name: $tag}})
                    CREATE (n)-[:HAS_TAG]->(t)
                    """,
                    guid=row["guid"],
                    tag=tag,
                )


def create_relationship_edges(
    tx,
    rows: list[dict],
    source_label: str,
    person_lookup: dict,
    event_lookup: dict,
) -> list[str]:
    """Create RELATED_TO_PERSON and RELATED_TO_EVENT edges. Returns errors."""
    errors = []

    person_cols = [f"related person {i}" for i in range(1, 6)]
    event_cols = [f"related event {i}" for i in range(1, 6)]

    for row in rows:
        source_guid = row["guid"]

        # Person relationships
        for col in person_cols:
            if col not in row or not row[col].strip():
                continue
            name, _, _, description = parse_reference(row[col])
            if name not in person_lookup:
                errors.append(
                    f"{source_label} '{row.get('name', source_guid)}': unknown person '{name}'"
                )
                continue
            tx.run(
                f"""
                MATCH (s:{source_label} {{guid: $source_guid}}), (t:Person {{name: $target_name}})
                CREATE (s)-[:RELATED_TO_PERSON {{description: $description}}]->(t)
                """,
                source_guid=source_guid,
                target_name=name,
                description=description or "",
            )

        # Event relationships
        for col in event_cols:
            if col not in row or not row[col].strip():
                continue
            name, _, _, description = parse_reference(row[col])
            if name not in event_lookup:
                errors.append(
                    f"{source_label} '{row.get('name', source_guid)}': unknown event '{name}'"
                )
                continue
            tx.run(
                f"""
                MATCH (s:{source_label} {{guid: $source_guid}}), (t:Event {{name: $target_name}})
                CREATE (s)-[:RELATED_TO_EVENT {{description: $description}}]->(t)
                """,
                source_guid=source_guid,
                target_name=name,
                description=description or "",
            )

    return errors


def main():
    parser = argparse.ArgumentParser(description="Import CSV data into Neo4j AuraDB")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all constraints, indexes, and data before importing",
    )
    args = parser.parse_args()

    # Get connection details from environment
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        print(
            "Error: Set NEO4J_URI and NEO4J_PASSWORD environment variables",
            file=sys.stderr,
        )
        print("Example: NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io", file=sys.stderr)
        sys.exit(1)

    data_dir = get_data_dir()

    # Load CSVs
    persons = load_csv(data_dir / "person.csv")
    events = load_csv(data_dir / "event.csv")
    qas = load_csv(data_dir / "qa.csv")
    clozes = load_csv(data_dir / "cloze.csv")

    # Lookups for relationship resolution
    person_lookup: dict[str, str] = {}
    event_lookup: dict[str, str] = {}

    # Connect to Neo4j AuraDB
    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        if args.drop:
            print("Dropping all constraints and indexes...")
            session.execute_write(drop_all)

        print("Clearing existing data...")
        session.execute_write(clear_database)

        print("Creating constraints...")
        session.execute_write(create_constraints)

        print("Creating nodes...")
        session.execute_write(create_persons, persons, person_lookup)
        session.execute_write(create_events, events, event_lookup)
        session.execute_write(create_qas, qas)
        session.execute_write(create_clozes, clozes)
        session.execute_write(create_tags, persons + events + qas + clozes)

        print("Creating edges...")
        session.execute_write(create_tag_edges, persons, "Person")
        session.execute_write(create_tag_edges, events, "Event")
        session.execute_write(create_tag_edges, qas, "QA")
        session.execute_write(create_tag_edges, clozes, "Cloze")

        # Create relationship edges
        errors = []
        errors += session.execute_write(
            create_relationship_edges, persons, "Person", person_lookup, event_lookup
        )
        errors += session.execute_write(
            create_relationship_edges, events, "Event", person_lookup, event_lookup
        )
        errors += session.execute_write(
            create_relationship_edges, qas, "QA", person_lookup, event_lookup
        )
        errors += session.execute_write(
            create_relationship_edges, clozes, "Cloze", person_lookup, event_lookup
        )

    driver.close()

    if errors:
        print("Errors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Imported {len(persons)} persons, {len(events)} events, "
        f"{len(qas)} QAs, {len(clozes)} clozes"
    )


if __name__ == "__main__":
    main()
