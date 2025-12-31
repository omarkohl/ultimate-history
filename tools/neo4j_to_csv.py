#!/usr/bin/env python3
"""Export Neo4j data back to CSV format."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from utils import format_reference, get_data_dir, make_csv_writer


load_dotenv()


def format_date(year: int | None, approximate: bool | None) -> str:
    """Format year and approximate flag back to CSV date string.

    Inverse of parse_date():
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


PERSON_FIELDNAMES = [
    "guid",
    "name",
    "known for",
    "date of birth",
    "date of death",
    "picture",
    "related person 1",
    "related person 2",
    "related person 3",
    "related person 4",
    "related person 5",
    "personal related person 1",
    "personal related person 2",
    "personal related person 3",
    "related event 1",
    "related event 2",
    "related event 3",
    "related event 4",
    "related event 5",
    "personal related event 1",
    "personal related event 2",
    "personal related event 3",
    "notes",
    "personal notes",
    "source & license",
    "tags",
]

EVENT_FIELDNAMES = [
    "guid",
    "name",
    "summary",
    "start date",
    "end date",
    "related person 1",
    "related person 2",
    "related person 3",
    "related person 4",
    "related person 5",
    "personal related person 1",
    "personal related person 2",
    "personal related person 3",
    "related event 1",
    "related event 2",
    "related event 3",
    "related event 4",
    "related event 5",
    "personal related event 1",
    "personal related event 2",
    "personal related event 3",
    "notes",
    "personal notes",
    "source & license",
    "tags",
]

QA_FIELDNAMES = [
    "guid",
    "question",
    "answer",
    "related person 1",
    "related person 2",
    "related person 3",
    "related person 4",
    "related person 5",
    "related event 1",
    "related event 2",
    "related event 3",
    "related event 4",
    "related event 5",
    "notes",
    "personal notes",
    "source & license",
    "tags",
]

CLOZE_FIELDNAMES = [
    "guid",
    "text",
    "related person 1",
    "related person 2",
    "related person 3",
    "related person 4",
    "related person 5",
    "related event 1",
    "related event 2",
    "related event 3",
    "related event 4",
    "related event 5",
    "notes",
    "personal notes",
    "source & license",
    "tags",
]


def get_persons(session) -> list[dict]:
    """Fetch all Person nodes with their relationships."""
    result = session.run(
        """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[rp:RELATED_TO_PERSON]->(target_p:Person)
        OPTIONAL MATCH (p)-[re:RELATED_TO_EVENT]->(target_e:Event)
        OPTIONAL MATCH (p)-[:HAS_TAG]->(t:Tag)
        RETURN p,
               collect(DISTINCT {name: target_p.name, birth_year: target_p.birth_year, birth_approximate: target_p.birth_approximate, death_year: target_p.death_year, death_approximate: target_p.death_approximate, description: rp.description}) as related_persons,
               collect(DISTINCT {name: target_e.name, start_year: target_e.start_year, start_approximate: target_e.start_approximate, end_year: target_e.end_year, end_approximate: target_e.end_approximate, description: re.description}) as related_events,
               collect(DISTINCT t.name) as tags
        ORDER BY LOWER(p.name) ASC;
        """
    )

    persons = []
    for record in result:
        p = record["p"]
        related_persons = sorted(
            [rp for rp in record["related_persons"] if rp["name"] is not None],
            key=lambda x: x["name"],
        )
        related_events = sorted(
            [re for re in record["related_events"] if re["name"] is not None],
            key=lambda x: x["name"],
        )
        tags = [t for t in record["tags"] if t is not None]

        row = {
            "guid": p["guid"],
            "name": p["name"],
            "known for": p["known_for"],
            "date of birth": format_date(p["birth_year"], p["birth_approximate"]),
            "date of death": format_date(p["death_year"], p["death_approximate"]),
            "picture": p["picture"],
            "notes": p["notes"],
            "personal notes": "",
            "source & license": p["source_license"],
            "tags": ", ".join(sorted(tags)),
        }

        # Add related persons
        for i in range(5):
            if i < len(related_persons):
                rp = related_persons[i]
                row[f"related person {i + 1}"] = format_reference(
                    rp["name"],
                    format_date(rp["birth_year"], rp["birth_approximate"]),
                    format_date(rp["death_year"], rp["death_approximate"]),
                    rp["description"],
                )
            else:
                row[f"related person {i + 1}"] = ""

        # Add personal related persons (always empty)
        for i in range(3):
            row[f"personal related person {i + 1}"] = ""

        # Add related events
        for i in range(5):
            if i < len(related_events):
                re = related_events[i]
                row[f"related event {i + 1}"] = format_reference(
                    re["name"],
                    format_date(re["start_year"], re["start_approximate"]),
                    format_date(re["end_year"], re["end_approximate"]),
                    re["description"],
                )
            else:
                row[f"related event {i + 1}"] = ""

        # Add personal related events (always empty)
        for i in range(3):
            row[f"personal related event {i + 1}"] = ""

        persons.append(row)

    return persons


def get_events(session) -> list[dict]:
    """Fetch all Event nodes with their relationships."""
    result = session.run(
        """
        MATCH (e:Event)
        OPTIONAL MATCH (e)-[rp:RELATED_TO_PERSON]->(target_p:Person)
        OPTIONAL MATCH (e)-[re:RELATED_TO_EVENT]->(target_e:Event)
        OPTIONAL MATCH (e)-[:HAS_TAG]->(t:Tag)
        RETURN e,
               collect(DISTINCT {name: target_p.name, birth_year: target_p.birth_year, birth_approximate: target_p.birth_approximate, death_year: target_p.death_year, death_approximate: target_p.death_approximate, description: rp.description}) as related_persons,
               collect(DISTINCT {name: target_e.name, start_year: target_e.start_year, start_approximate: target_e.start_approximate, end_year: target_e.end_year, end_approximate: target_e.end_approximate, description: re.description}) as related_events,
               collect(DISTINCT t.name) as tags
        ORDER BY LOWER(e.name) ASC;
        """
    )

    events = []
    for record in result:
        e = record["e"]
        related_persons = sorted(
            [rp for rp in record["related_persons"] if rp["name"] is not None],
            key=lambda x: x["name"],
        )
        related_events = sorted(
            [re for re in record["related_events"] if re["name"] is not None],
            key=lambda x: x["name"],
        )
        tags = [t for t in record["tags"] if t is not None]

        row = {
            "guid": e["guid"],
            "name": e["name"],
            "summary": e["summary"],
            "start date": format_date(e["start_year"], e["start_approximate"]),
            "end date": format_date(e["end_year"], e["end_approximate"]),
            "notes": e["notes"],
            "personal notes": "",
            "source & license": e["source_license"],
            "tags": ", ".join(sorted(tags)),
        }

        # Add related persons
        for i in range(5):
            if i < len(related_persons):
                rp = related_persons[i]
                row[f"related person {i + 1}"] = format_reference(
                    rp["name"],
                    format_date(rp["birth_year"], rp["birth_approximate"]),
                    format_date(rp["death_year"], rp["death_approximate"]),
                    rp["description"],
                )
            else:
                row[f"related person {i + 1}"] = ""

        # Add personal related persons (always empty)
        for i in range(3):
            row[f"personal related person {i + 1}"] = ""

        # Add related events
        for i in range(5):
            if i < len(related_events):
                re = related_events[i]
                row[f"related event {i + 1}"] = format_reference(
                    re["name"],
                    format_date(re["start_year"], re["start_approximate"]),
                    format_date(re["end_year"], re["end_approximate"]),
                    re["description"],
                )
            else:
                row[f"related event {i + 1}"] = ""

        # Add personal related events (always empty)
        for i in range(3):
            row[f"personal related event {i + 1}"] = ""

        events.append(row)

    return events


def get_qas(session) -> list[dict]:
    """Fetch all QA nodes with their relationships."""
    result = session.run(
        """
        MATCH (q:QA)
        OPTIONAL MATCH (q)-[rp:RELATED_TO_PERSON]->(target_p:Person)
        OPTIONAL MATCH (q)-[re:RELATED_TO_EVENT]->(target_e:Event)
        OPTIONAL MATCH (q)-[:HAS_TAG]->(t:Tag)
        RETURN q,
               collect(DISTINCT {name: target_p.name, birth_year: target_p.birth_year, birth_approximate: target_p.birth_approximate, death_year: target_p.death_year, death_approximate: target_p.death_approximate, description: rp.description}) as related_persons,
               collect(DISTINCT {name: target_e.name, start_year: target_e.start_year, start_approximate: target_e.start_approximate, end_year: target_e.end_year, end_approximate: target_e.end_approximate, description: re.description}) as related_events,
               collect(DISTINCT t.name) as tags
        ORDER BY LOWER(q.question) ASC;
        """
    )

    qas = []
    for record in result:
        q = record["q"]
        related_persons = sorted(
            [rp for rp in record["related_persons"] if rp["name"] is not None],
            key=lambda x: x["name"],
        )
        related_events = sorted(
            [re for re in record["related_events"] if re["name"] is not None],
            key=lambda x: x["name"],
        )
        tags = [t for t in record["tags"] if t is not None]

        row = {
            "guid": q["guid"],
            "question": q["question"],
            "answer": q["answer"],
            "notes": q["notes"],
            "personal notes": "",
            "source & license": q["source_license"],
            "tags": ", ".join(sorted(tags)),
        }

        # Add related persons
        for i in range(5):
            if i < len(related_persons):
                rp = related_persons[i]
                row[f"related person {i + 1}"] = format_reference(
                    rp["name"],
                    format_date(rp["birth_year"], rp["birth_approximate"]),
                    format_date(rp["death_year"], rp["death_approximate"]),
                    rp["description"],
                )
            else:
                row[f"related person {i + 1}"] = ""

        # Add related events
        for i in range(5):
            if i < len(related_events):
                re = related_events[i]
                row[f"related event {i + 1}"] = format_reference(
                    re["name"],
                    format_date(re["start_year"], re["start_approximate"]),
                    format_date(re["end_year"], re["end_approximate"]),
                    re["description"],
                )
            else:
                row[f"related event {i + 1}"] = ""

        qas.append(row)

    return qas


def get_clozes(session) -> list[dict]:
    """Fetch all Cloze nodes with their relationships."""
    result = session.run(
        """
        MATCH (c:Cloze)
        OPTIONAL MATCH (c)-[rp:RELATED_TO_PERSON]->(target_p:Person)
        OPTIONAL MATCH (c)-[re:RELATED_TO_EVENT]->(target_e:Event)
        OPTIONAL MATCH (c)-[:HAS_TAG]->(t:Tag)
        RETURN c,
               collect(DISTINCT {name: target_p.name, birth_year: target_p.birth_year, birth_approximate: target_p.birth_approximate, death_year: target_p.death_year, death_approximate: target_p.death_approximate, description: rp.description}) as related_persons,
               collect(DISTINCT {name: target_e.name, start_year: target_e.start_year, start_approximate: target_e.start_approximate, end_year: target_e.end_year, end_approximate: target_e.end_approximate, description: re.description}) as related_events,
               collect(DISTINCT t.name) as tags
        ORDER BY LOWER(c.text) ASC;
        """
    )

    clozes = []
    for record in result:
        c = record["c"]
        related_persons = sorted(
            [rp for rp in record["related_persons"] if rp["name"] is not None],
            key=lambda x: x["name"],
        )
        related_events = sorted(
            [re for re in record["related_events"] if re["name"] is not None],
            key=lambda x: x["name"],
        )
        tags = [t for t in record["tags"] if t is not None]

        row = {
            "guid": c["guid"],
            "text": c["text"],
            "notes": c["notes"],
            "personal notes": "",
            "source & license": c["source_license"],
            "tags": ", ".join(sorted(tags)),
        }

        # Add related persons
        for i in range(5):
            if i < len(related_persons):
                rp = related_persons[i]
                row[f"related person {i + 1}"] = format_reference(
                    rp["name"],
                    format_date(rp["birth_year"], rp["birth_approximate"]),
                    format_date(rp["death_year"], rp["death_approximate"]),
                    rp["description"],
                )
            else:
                row[f"related person {i + 1}"] = ""

        # Add related events
        for i in range(5):
            if i < len(related_events):
                re = related_events[i]
                row[f"related event {i + 1}"] = format_reference(
                    re["name"],
                    format_date(re["start_year"], re["start_approximate"]),
                    format_date(re["end_year"], re["end_approximate"]),
                    re["description"],
                )
            else:
                row[f"related event {i + 1}"] = ""

        clozes.append(row)

    return clozes


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    """Write rows to CSV with standard settings."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = make_csv_writer(f, fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    # Get connection details from environment
    uri = os.environ.get("NEO4J_URI")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not uri or not password:
        print(
            "Error: Set NEO4J_URI and NEO4J_PASSWORD environment variables",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir = get_data_dir()

    # Connect to Neo4j AuraDB
    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        print("Fetching persons...")
        persons = get_persons(session)

        print("Fetching events...")
        events = get_events(session)

        print("Fetching QAs...")
        qas = get_qas(session)

        print("Fetching clozes...")
        clozes = get_clozes(session)

    driver.close()

    print(f"Writing {len(persons)} persons to person.csv...")
    write_csv(data_dir / "person.csv", PERSON_FIELDNAMES, persons)

    print(f"Writing {len(events)} events to event.csv...")
    write_csv(data_dir / "event.csv", EVENT_FIELDNAMES, events)

    print(f"Writing {len(qas)} QAs to qa.csv...")
    write_csv(data_dir / "qa.csv", QA_FIELDNAMES, qas)

    print(f"Writing {len(clozes)} clozes to cloze.csv...")
    write_csv(data_dir / "cloze.csv", CLOZE_FIELDNAMES, clozes)

    print("Done.")


if __name__ == "__main__":
    main()
