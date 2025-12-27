#!/usr/bin/env python3
"""List relationships between Anki notes."""

import argparse
import csv
import html
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from model import Cloze, Event, Note, Person, QA, Relationship
from utils import parse_reference


class RelationshipAnalyzer:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.notes: dict[str, Note] = {}
        self.incoming_relationships: dict[str, list[tuple[Note, Relationship]]] = (
            defaultdict(list)
        )

    def load_notes_from_csv(
        self, csv_path: Path, note_class: type[Note], field_mapping: dict[str, str]
    ):
        """Load notes from a CSV file."""
        if not csv_path.exists():
            return

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                guid = row["guid"].strip()
                if not guid:
                    continue

                # Create note instance
                kwargs = {"guid": guid}
                for csv_field, note_field in field_mapping.items():
                    if csv_field in row:
                        kwargs[note_field] = row[csv_field].strip()

                note = note_class(**kwargs)

                # Parse relationships (exclude "personal related *" fields)
                for column, value in row.items():
                    if not value or not value.strip():
                        continue

                    if "personal" in column.lower():
                        continue

                    if "related person" in column.lower():
                        name, _, _, description = parse_reference(value)
                        if name:
                            note.related_persons.append(
                                Relationship(
                                    target_name=name,
                                    target_guid=None,
                                    description=description,
                                )
                            )
                    elif "related event" in column.lower():
                        name, _, _, description = parse_reference(value)
                        if name:
                            note.related_events.append(
                                Relationship(
                                    target_name=name,
                                    target_guid=None,
                                    description=description,
                                )
                            )

                self.notes[guid] = note

    def load_all_notes(self):
        """Load all note types from CSV files."""
        self.load_notes_from_csv(
            self.data_dir / "person.csv",
            Person,
            {"name": "name", "date of birth": "birth", "date of death": "death"},
        )

        self.load_notes_from_csv(
            self.data_dir / "event.csv",
            Event,
            {"name": "name", "start date": "start", "end date": "end"},
        )

        self.load_notes_from_csv(
            self.data_dir / "qa.csv",
            QA,
            {"question": "question", "answer": "answer"},
        )

        self.load_notes_from_csv(
            self.data_dir / "cloze.csv",
            Cloze,
            {"text": "text"},
        )

    def resolve_relationship_guids(self):
        """Resolve target names to GUIDs and build incoming relationship index."""
        # Build name -> note mapping for quick lookup
        name_to_note: dict[str, Note] = {}
        for note in self.notes.values():
            if isinstance(note, (Person, Event)):
                name_to_note[note.get_display_name()] = note

        # Resolve GUIDs and build incoming relationships
        for source_note in self.notes.values():
            for rel in source_note.get_all_outgoing_relationships():
                # Try to find the target note by name
                target_note = name_to_note.get(rel.target_name)
                if target_note:
                    rel.target_guid = target_note.guid
                    # Add to incoming relationships
                    self.incoming_relationships[target_note.guid].append(
                        (source_note, rel)
                    )

    def fuzzy_search(self, search_str: str, threshold: float = 0.8) -> list[Note]:
        """Fuzzy search notes by name/content."""
        if not search_str:
            return list(self.notes.values())

        matches = []
        search_lower = search_str.lower()

        for note in self.notes.values():
            display_name = note.get_display_name().lower()

            # Check for substring match first (always accept)
            if search_lower in display_name:
                matches.append(note)
                continue

            # Otherwise use fuzzy matching with threshold
            ratio = SequenceMatcher(None, search_lower, display_name).ratio()
            if ratio >= threshold:
                matches.append(note)

        return matches

    def strip_html(self, text: str) -> str:
        """Strip HTML tags from text but keep cloze markers."""
        # Unescape HTML entities first
        text = html.unescape(text)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max_length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def format_note_header(self, note: Note) -> str:
        """Format note header with type, name/content, GUID, and relationship count."""
        display_name = note.get_display_name()

        # Strip HTML for display
        if isinstance(note, (Cloze, QA)):
            display_name = self.strip_html(display_name)

        display_name = self.truncate(display_name, 60)

        incoming_count = len(self.incoming_relationships.get(note.guid, []))
        total = note.total_relationships(incoming_count)

        return f"[{note.get_note_type()}] {display_name} ({note.guid}) - {total} relationships"

    def format_relationship(self, rel: Relationship, target_note: Note | None) -> str:
        """Format a single relationship."""
        if target_note:
            display_name = target_note.get_display_name()
            if isinstance(target_note, (Cloze, QA)):
                display_name = self.strip_html(display_name)
            display_name = self.truncate(display_name, 60)
            note_type = target_note.get_note_type()
            result = f"[{note_type}] {display_name} ({rel.target_guid})"
        else:
            # Target not found - show name only
            result = f"{rel.target_name} (not found)"

        if rel.description:
            desc = self.truncate(rel.description, 80)
            result += f": {desc}"

        return result

    def print_relationships(
        self,
        notes: list[Note],
        sort_order: str = "desc",
        max_display: int | None = None,
    ):
        """Print notes and their relationships sorted by relationship count."""

        # Sort by relationship count, then alphabetically
        def sort_key(note: Note) -> tuple[int, str]:
            incoming_count = len(self.incoming_relationships.get(note.guid, []))
            total = note.total_relationships(incoming_count)
            display_name = note.get_display_name()
            if isinstance(note, (Cloze, QA)):
                display_name = self.strip_html(display_name)

            if sort_order == "desc":
                return (-total, display_name)
            else:
                return (total, display_name)

        sorted_notes = sorted(notes, key=sort_key)

        if max_display:
            sorted_notes = sorted_notes[:max_display]

        for note in sorted_notes:
            print(self.format_note_header(note))

            # Outgoing relationships
            outgoing = note.get_all_outgoing_relationships()
            if outgoing:
                print(f"  Outgoing ({len(outgoing)}):")
                for rel in outgoing:
                    target_note = (
                        self.notes.get(rel.target_guid) if rel.target_guid else None
                    )
                    print(f"    → {self.format_relationship(rel, target_note)}")

            # Incoming relationships
            incoming = self.incoming_relationships.get(note.guid, [])
            if incoming:
                print(f"  Incoming ({len(incoming)}):")
                for source_note, rel in incoming:
                    source_display = source_note.get_display_name()
                    if isinstance(source_note, (Cloze, QA)):
                        source_display = self.strip_html(source_display)
                    source_display = self.truncate(source_display, 60)
                    rel_desc = (
                        f": {self.truncate(rel.description, 80)}"
                        if rel.description
                        else ""
                    )
                    print(
                        f"    ← [{source_note.get_note_type()}] {source_display} ({source_note.guid}){rel_desc}"
                    )

            print()


def main():
    parser = argparse.ArgumentParser(
        description="List relationships between Anki notes"
    )
    parser.add_argument(
        "--sort",
        choices=["asc", "desc"],
        default="desc",
        help="Sort order by relationship count (default: desc)",
    )
    parser.add_argument(
        "--search", type=str, help="Fuzzy search string to filter notes"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Fuzzy match threshold (default: 0.8)",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of notes to display")
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "src" / "data"
    analyzer = RelationshipAnalyzer(data_dir)

    print("Loading notes...")
    analyzer.load_all_notes()
    print(f"Loaded {len(analyzer.notes)} notes")

    print("Resolving relationships...")
    analyzer.resolve_relationship_guids()

    # Apply search filter if provided
    notes = analyzer.fuzzy_search(args.search, args.threshold)
    if args.search:
        print(f"Found {len(notes)} notes matching '{args.search}'\n")
    else:
        print()

    analyzer.print_relationships(notes, args.sort, args.limit)


if __name__ == "__main__":
    main()
