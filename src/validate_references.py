#!/usr/bin/env python3
"""Validate and fix references between Person and Event CSV files."""

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


@dataclass
class Person:
    name: str
    birth: Optional[str]
    death: Optional[str]
    guid: str


@dataclass
class Event:
    name: str
    start: Optional[str]
    end: Optional[str]
    guid: str


@dataclass
class ValidationError:
    csv_file: str
    row_num: int
    column: str
    error_type: str
    message: str
    current_value: str
    suggested_fix: Optional[str] = None


class ReferenceValidator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.people: dict[str, Person] = {}
        self.events: dict[str, Event] = {}
        self.errors: list[ValidationError] = []
        self.fuzzy_threshold = 0.8

    def load_people(self):
        """Load all people from Person.csv."""
        person_file = self.data_dir / "Ultimate History | Person.csv"
        with open(person_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["name"].strip()
                self.people[name] = Person(
                    name=name,
                    birth=row.get("date of birth", "").strip() or None,
                    death=row.get("date of death", "").strip() or None,
                    guid=row["guid"],
                )

    def load_events(self):
        """Load all events from Event.csv."""
        event_file = self.data_dir / "Ultimate History | Event.csv"
        with open(event_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["name"].strip()
                self.events[name] = Event(
                    name=name,
                    start=row.get("start date", "").strip() or None,
                    end=row.get("end date", "").strip() or None,
                    guid=row["guid"],
                )

    def fuzzy_match(
        self, name: str, candidates: dict[str, Person | Event]
    ) -> Optional[str]:
        """Find the best fuzzy match for a name."""
        best_match = None
        best_ratio = 0.0

        for candidate in candidates.keys():
            ratio = SequenceMatcher(None, name.lower(), candidate.lower()).ratio()
            if ratio > best_ratio and ratio >= self.fuzzy_threshold:
                best_ratio = ratio
                best_match = candidate

        return best_match

    def parse_reference(
        self, value: str
    ) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Parse a reference in format 'NAME (DATE[ - DATE]): RELATIONSHIP' or 'NAME (DATE[ - DATE]) – DESCRIPTION'.

        Name can contain parentheses, e.g., "Unification of Italy (Risorgimento) (1848–1871): description"
        The dates are in the LAST set of parentheses before the separator.

        Returns: (name, date1, date2, relationship)
        If parsing fails completely, returns (original_value, None, None, None)
        """
        if not value or not value.strip():
            return "", None, None, None

        value = value.strip()

        # Strategy: Look for the separator (: or – or —) first
        # Everything before the last separator is name+dates
        # Everything after is the relationship

        # Find the last occurrence of a separator that's likely the relationship separator
        # It should be near the end or followed by descriptive text
        separator_match = None
        for sep_pattern in [r":\s*", r"[–—]\s+"]:
            matches = list(re.finditer(sep_pattern, value))
            if matches:
                # Take the last match
                separator_match = matches[-1]
                break

        if separator_match:
            before_sep = value[: separator_match.start()].strip()
            relationship = value[separator_match.end() :].strip()
        else:
            before_sep = value
            relationship = None

        # Now parse before_sep to extract name and dates
        # Dates should be in the last set of parentheses
        paren_matches = list(re.finditer(r"\(([^)]+)\)", before_sep))

        if paren_matches:
            last_paren = paren_matches[-1]
            dates_str = last_paren.group(1)
            name = before_sep[: last_paren.start()].strip()

            # Check if this looks like dates (contains digits)
            if re.search(r"\d", dates_str):
                # Parse the dates
                date_parts = re.split(r"\s*[–—-]\s*", dates_str)
                if len(date_parts) == 1:
                    date1 = date_parts[0].strip()
                    date2 = None
                elif len(date_parts) == 2:
                    date1 = date_parts[0].strip()
                    date2 = date_parts[1].strip()
                else:
                    # Too many dashes - unparseable
                    return value, None, None, None
            else:
                # Last paren doesn't contain dates, so include it in the name
                name = before_sep
                date1, date2 = None, None
        else:
            # No parentheses at all
            name = before_sep
            date1, date2 = None, None

        return name, date1, date2, relationship

    def format_reference(
        self,
        name: str,
        date1: Optional[str],
        date2: Optional[str],
        relationship: Optional[str],
    ) -> str:
        """Format a reference in standard format: NAME (DATE[ - DATE]): RELATIONSHIP."""
        result = name
        if date1:
            if date2:
                result += f" ({date1}–{date2})"
            else:
                result += f" ({date1})"
        if relationship:
            result += f": {relationship}"
        return result

    def check_format(
        self,
        value: str,
        name: str,
        date1: Optional[str],
        date2: Optional[str],
        relationship: Optional[str],
    ) -> bool:
        """Check if the reference follows the standard format."""
        expected = self.format_reference(name, date1, date2, relationship)
        # Normalize whitespace and dash characters for comparison
        normalized_value = re.sub(r"\s+", " ", value.strip())
        normalized_expected = re.sub(r"\s+", " ", expected.strip())

        # Also check if using en-dash instead of colon
        if relationship and " – " in normalized_value and ": " not in normalized_value:
            return False

        return normalized_value == normalized_expected

    def validate_person_reference(
        self, csv_file: str, row_num: int, column: str, value: str
    ) -> Optional[str]:
        """Validate a person reference and return suggested fix if needed."""
        if not value or not value.strip():
            return None

        name, date1, date2, relationship = self.parse_reference(value)
        if not name:
            return None

        # Check if this looks unparseable (has dates/relationship mixed with dashes in wrong places)
        # If name equals the full value and value has parentheses, it's likely unparseable
        if name == value and "(" in value and ")" in value:
            # Check if there's a dash separator that's not a colon
            if " – " in value or " — " in value:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="unparseable",
                        message="Cannot parse reference - please manually add colon separator",
                        current_value=value,
                        suggested_fix=None,
                    )
                )
                return None

        fix_needed = None

        # Check if person exists
        if name in self.people:
            person = self.people[name]
            # Validate dates
            expected_date1 = person.birth
            expected_date2 = person.death

            if expected_date1 != date1 or expected_date2 != date2:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="date_mismatch",
                        message=f"Dates don't match for '{name}'",
                        current_value=value,
                        suggested_fix=self.format_reference(
                            name, expected_date1, expected_date2, relationship
                        ),
                    )
                )
                fix_needed = self.format_reference(
                    name, expected_date1, expected_date2, relationship
                )
            else:
                # Check format even if data is correct
                if not self.check_format(value, name, date1, date2, relationship):
                    formatted = self.format_reference(name, date1, date2, relationship)
                    self.errors.append(
                        ValidationError(
                            csv_file=csv_file,
                            row_num=row_num,
                            column=column,
                            error_type="format_issue",
                            message=f"Format doesn't match standard for '{name}'",
                            current_value=value,
                            suggested_fix=formatted,
                        )
                    )
                    fix_needed = formatted
        else:
            # Try fuzzy match
            match = self.fuzzy_match(name, self.people)
            if match:
                person = self.people[match]
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="name_mismatch",
                        message=f"Name mismatch: '{name}' should be '{match}'",
                        current_value=value,
                        suggested_fix=self.format_reference(
                            match, person.birth, person.death, relationship
                        ),
                    )
                )
                fix_needed = self.format_reference(
                    match, person.birth, person.death, relationship
                )
            else:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="missing_person",
                        message=f"Person not found: '{name}'",
                        current_value=value,
                        suggested_fix=None,
                    )
                )

        return fix_needed

    def validate_event_reference(
        self, csv_file: str, row_num: int, column: str, value: str
    ) -> Optional[str]:
        """Validate an event reference and return suggested fix if needed."""
        if not value or not value.strip():
            return None

        name, date1, date2, relationship = self.parse_reference(value)
        if not name:
            return None

        # Check if this looks unparseable (has dates/relationship mixed with dashes in wrong places)
        # If name equals the full value and value has parentheses, it's likely unparseable
        if name == value and "(" in value and ")" in value:
            # Check if there's a dash separator that's not a colon
            if " – " in value or " — " in value:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="unparseable",
                        message="Cannot parse reference - please manually add colon separator",
                        current_value=value,
                        suggested_fix=None,
                    )
                )
                return None

        fix_needed = None

        # Check if event exists
        if name in self.events:
            event = self.events[name]
            # Validate dates
            expected_date1 = event.start
            expected_date2 = event.end

            if expected_date1 != date1 or expected_date2 != date2:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="date_mismatch",
                        message=f"Dates don't match for '{name}'",
                        current_value=value,
                        suggested_fix=self.format_reference(
                            name, expected_date1, expected_date2, relationship
                        ),
                    )
                )
                fix_needed = self.format_reference(
                    name, expected_date1, expected_date2, relationship
                )
            else:
                # Check format even if data is correct
                if not self.check_format(value, name, date1, date2, relationship):
                    formatted = self.format_reference(name, date1, date2, relationship)
                    self.errors.append(
                        ValidationError(
                            csv_file=csv_file,
                            row_num=row_num,
                            column=column,
                            error_type="format_issue",
                            message=f"Format doesn't match standard for '{name}'",
                            current_value=value,
                            suggested_fix=formatted,
                        )
                    )
                    fix_needed = formatted
        else:
            # Try fuzzy match
            match = self.fuzzy_match(name, self.events)
            if match:
                event = self.events[match]
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="name_mismatch",
                        message=f"Name mismatch: '{name}' should be '{match}'",
                        current_value=value,
                        suggested_fix=self.format_reference(
                            match, event.start, event.end, relationship
                        ),
                    )
                )
                fix_needed = self.format_reference(
                    match, event.start, event.end, relationship
                )
            else:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_file,
                        row_num=row_num,
                        column=column,
                        error_type="missing_event",
                        message=f"Event not found: '{name}'",
                        current_value=value,
                        suggested_fix=None,
                    )
                )

        return fix_needed

    def validate_csv_file(self, csv_file: Path) -> dict[tuple[int, str], str]:
        """Validate all references in a CSV file.

        Returns dict of (row_num, column) -> suggested_fix for auto-fix mode.
        """
        fixes = {}
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                for column, value in row.items():
                    if "related person" in column.lower():
                        fix = self.validate_person_reference(
                            csv_file.name, row_num, column, value
                        )
                        if fix:
                            fixes[(row_num, column)] = fix
                    elif "related event" in column.lower():
                        fix = self.validate_event_reference(
                            csv_file.name, row_num, column, value
                        )
                        if fix:
                            fixes[(row_num, column)] = fix

        return fixes

    def apply_fixes(self, csv_file: Path, fixes: dict[tuple[int, str], str]):
        """Apply fixes to a CSV file."""
        rows = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row_num, row in enumerate(reader, start=2):
                for column in row.keys():
                    if (row_num, column) in fixes:
                        row[column] = fixes[(row_num, column)]
                rows.append(row)

        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def create_missing_people(self):
        """Create new Person rows for missing references."""
        missing_people = {}
        for error in self.errors:
            if error.error_type == "missing_person":
                name, date1, date2, _ = self.parse_reference(error.current_value)
                if name and name not in missing_people:
                    missing_people[name] = (date1, date2)

        if not missing_people:
            return

        person_file = self.data_dir / "Ultimate History | Person.csv"
        with open(person_file, "a", encoding="utf-8", newline="") as f:
            with open(person_file, "r", encoding="utf-8") as rf:
                reader = csv.DictReader(rf)
                fieldnames = reader.fieldnames

            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            for name, (birth, death) in missing_people.items():
                row = {field: "" for field in fieldnames}
                row["guid"] = ""
                row["name"] = name
                if birth:
                    row["date of birth"] = birth
                if death:
                    row["date of death"] = death
                writer.writerow(row)

        print(f"\nCreated {len(missing_people)} new Person rows")

    def create_missing_events(self):
        """Create new Event rows for missing references."""
        missing_events = {}
        for error in self.errors:
            if error.error_type == "missing_event":
                name, date1, date2, _ = self.parse_reference(error.current_value)
                if name and name not in missing_events:
                    missing_events[name] = (date1, date2)

        if not missing_events:
            return

        event_file = self.data_dir / "Ultimate History | Event.csv"
        with open(event_file, "a", encoding="utf-8", newline="") as f:
            with open(event_file, "r", encoding="utf-8") as rf:
                reader = csv.DictReader(rf)
                fieldnames = reader.fieldnames

            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            for name, (start, end) in missing_events.items():
                row = {field: "" for field in fieldnames}
                row["guid"] = ""
                row["name"] = name
                if start:
                    row["start date"] = start
                if end:
                    row["end date"] = end
                writer.writerow(row)

        print(f"\nCreated {len(missing_events)} new Event rows")

    def print_errors(self):
        """Print all errors grouped by CSV file."""
        errors_by_file = defaultdict(list)
        for error in self.errors:
            errors_by_file[error.csv_file].append(error)

        if not errors_by_file:
            print("✓ No validation errors found!")
            return

        print(f"\nFound {len(self.errors)} validation errors:\n")

        for csv_file in sorted(errors_by_file.keys()):
            print(f"═══ {csv_file} ═══")
            errors = errors_by_file[csv_file]

            # Group by error type
            by_type = defaultdict(list)
            for error in errors:
                by_type[error.error_type].append(error)

            for error_type in sorted(by_type.keys()):
                type_errors = by_type[error_type]
                print(
                    f"\n  {error_type.replace('_', ' ').title()} ({len(type_errors)}):"
                )
                for error in type_errors:
                    print(f"    Row {error.row_num}, {error.column}:")
                    print(f"      {error.message}")
                    print(f"      Current: {error.current_value}")
                    if error.suggested_fix:
                        print(f"      Fix: {error.suggested_fix}")
            print()


def main():
    parser = argparse.ArgumentParser(description="Validate references in CSV files")
    parser.add_argument(
        "--auto-fix", action="store_true", help="Automatically apply fixes"
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data"
    validator = ReferenceValidator(data_dir)

    print("Loading people and events...")
    validator.load_people()
    validator.load_events()

    print(f"Loaded {len(validator.people)} people and {len(validator.events)} events")

    all_fixes = {}
    csv_files = list(data_dir.glob("*.csv"))

    print(f"\nValidating {len(csv_files)} CSV files...")
    for csv_file in csv_files:
        fixes = validator.validate_csv_file(csv_file)
        if fixes:
            all_fixes[csv_file] = fixes

    validator.print_errors()

    if args.auto_fix and (
        all_fixes
        or any(
            e.error_type in ("missing_person", "missing_event")
            for e in validator.errors
        )
    ):
        print("\nApplying fixes...")
        for csv_file, fixes in all_fixes.items():
            validator.apply_fixes(csv_file, fixes)
            print(f"  Fixed {len(fixes)} references in {csv_file.name}")

        validator.create_missing_people()
        validator.create_missing_events()

        print("\n✓ Fixes applied successfully!")
    elif args.auto_fix:
        print("\n✓ No fixes needed!")


if __name__ == "__main__":
    main()
