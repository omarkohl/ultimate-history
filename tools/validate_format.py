#!/usr/bin/env python3
"""Validate and fix CSV file formatting issues."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from utils import get_data_dir
from validation_common import ValidationError


class FormatValidator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.errors: list[ValidationError] = []

    def validate_all_csvs(self):
        """Validate all CSV files in the data directory."""
        csv_files = list(self.data_dir.glob("*.csv"))

        for csv_file in csv_files:
            self.validate_csv(csv_file)

    def validate_csv(self, csv_file: Path):
        """Validate a single CSV file for formatting issues."""
        csv_name = csv_file.name

        # Check quoting by reading raw file
        self.check_quoting(csv_file)

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise ValueError(f"No fieldnames found in {csv_file}")

            rows = list(reader)

        # Check for duplicates in specific columns
        self.check_duplicates(csv_name, rows)

        # Check each row for formatting issues
        for row_num, row in enumerate(rows, start=2):
            self.check_tags_ordering(csv_name, row_num, row)
            self.check_whitespace(csv_name, row_num, row)

    def check_quoting(self, csv_file: Path):
        """Check if all fields in the CSV are properly quoted."""
        csv_name = csv_file.name

        with open(csv_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return

        # Check if all lines (including header) have all fields quoted
        # A properly quoted CSV should have fields separated by ","
        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            # Parse the line to check quoting
            # Check if all fields are quoted
            in_quote = False
            field_start = True
            has_unquoted_field = False
            i = 0

            while i < len(stripped):
                char = stripped[i]

                if char == '"':
                    if field_start:
                        # Field starts with quote - good!
                        in_quote = True
                        field_start = False
                    elif in_quote:
                        # Check if this is an escaped quote
                        if i + 1 < len(stripped) and stripped[i + 1] == '"':
                            # Escaped quote, skip the next quote
                            i += 1
                        else:
                            # End of quoted field
                            in_quote = False
                    i += 1
                elif char == "," and not in_quote:
                    # Field separator - next field should start with quote
                    field_start = True
                    i += 1
                elif field_start and char != '"' and not char.isspace():
                    # Field doesn't start with a quote (and it's not whitespace)
                    has_unquoted_field = True
                    break
                else:
                    if field_start and char.isspace():
                        # Skip leading whitespace before checking for quote
                        i += 1
                        continue
                    field_start = False
                    i += 1

            if has_unquoted_field:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_name,
                        row_num=line_num,
                        column="*",
                        error_type="quoting",
                        message="Row has unquoted fields (should use QUOTE_ALL)",
                        current_value=stripped[:80],
                        suggested_fix="Run with --auto-fix to apply QUOTE_ALL",
                    )
                )
                break  # Only report once per file

    def check_tags_ordering(self, csv_name: str, row_num: int, row: dict):
        """Check if tags are comma-separated and alphabetically ordered."""
        if "tags" not in row:
            return

        tags_value = row["tags"]
        if not tags_value or not tags_value.strip():
            return

        # Split tags and clean them
        tags = [tag.strip() for tag in tags_value.split(",")]
        sorted_tags = sorted(tags)

        if tags != sorted_tags:
            suggested_fix = ", ".join(sorted_tags)
            self.errors.append(
                ValidationError(
                    csv_file=csv_name,
                    row_num=row_num,
                    column="tags",
                    error_type="tags_not_sorted",
                    message="Tags are not alphabetically sorted",
                    current_value=tags_value,
                    suggested_fix=suggested_fix,
                )
            )

    def check_whitespace(self, csv_name: str, row_num: int, row: dict):
        """Check for leading/trailing whitespace in fields."""
        for column, value in row.items():
            if value != value.strip():
                self.errors.append(
                    ValidationError(
                        csv_file=csv_name,
                        row_num=row_num,
                        column=column,
                        error_type="whitespace",
                        message="Field has leading or trailing whitespace",
                        current_value=value,
                        suggested_fix=value.strip(),
                    )
                )

    def check_duplicates(self, csv_name: str, rows: list[dict]):
        """Check for duplicate values in specific columns."""
        # Define which columns to check for duplicates in each CSV type
        duplicate_columns = {
            "event.csv": ["name", "summary"],
            "person.csv": ["name", "known for"],
            "qa.csv": [],  # No duplicate checks for QA
            "cloze.csv": [],  # No duplicate checks for Cloze
        }

        columns_to_check = duplicate_columns.get(csv_name, [])

        for column in columns_to_check:
            if column not in rows[0]:
                continue

            seen = defaultdict(list)
            for row_num, row in enumerate(rows, start=2):
                value = row[column].strip()
                if value:  # Only check non-empty values
                    seen[value].append(row_num)

            # Report duplicates
            for value, row_nums in seen.items():
                if len(row_nums) > 1:
                    for row_num in row_nums:
                        self.errors.append(
                            ValidationError(
                                csv_file=csv_name,
                                row_num=row_num,
                                column=column,
                                error_type="duplicate",
                                message=f"Duplicate value found in rows {row_nums}",
                                current_value=value,
                                suggested_fix=None,
                            )
                        )

    def print_errors(self):
        """Print all validation errors grouped by type."""
        if not self.errors:
            print("✓ No formatting issues found")
            return

        print(f"\n⚠ Found {len(self.errors)} formatting issue(s):\n")

        # Group errors by type
        errors_by_type = defaultdict(list)
        for error in self.errors:
            errors_by_type[error.error_type].append(error)

        for error_type, errors in sorted(errors_by_type.items()):
            print(f"{error_type.upper().replace('_', ' ')} ({len(errors)}):")
            for error in errors:
                print(f"  {error.csv_file}:{error.row_num} [{error.column}]")
                print(f"    {error.message}")
                print(f"    Current: {error.current_value[:100]}")
                if error.suggested_fix:
                    print(f"    Suggested: {error.suggested_fix[:100]}")
                print()

    def auto_fix(self):
        """Automatically fix all formatting issues."""
        if not self.errors:
            return

        # Collect all files that need fixing
        files_to_fix = set()
        row_fixes_by_file: dict[Path, dict[tuple[int, str], str]] = defaultdict(dict)

        for error in self.errors:
            csv_file = self.data_dir / error.csv_file
            files_to_fix.add(csv_file)

            # Collect row-level fixes (not quoting fixes)
            if error.error_type != "quoting" and error.suggested_fix is not None:
                row_fixes_by_file[csv_file][(error.row_num, error.column)] = (
                    error.suggested_fix
                )

        # Apply fixes to each file (this will also apply QUOTE_ALL)
        for csv_file in files_to_fix:
            fixes = row_fixes_by_file.get(csv_file, {})
            self.apply_fixes(csv_file, fixes)

        fixable_count = len(
            [
                e
                for e in self.errors
                if e.error_type == "quoting" or e.suggested_fix is not None
            ]
        )
        print(f"✓ Auto-fixed {fixable_count} issues")

        # Report errors that couldn't be auto-fixed
        unfixed = [
            e
            for e in self.errors
            if e.error_type != "quoting" and e.suggested_fix is None
        ]
        if unfixed:
            print(f"⚠ {len(unfixed)} issues require manual review:")
            for error in unfixed:
                print(
                    f"  {error.csv_file}:{error.row_num} [{error.column}] - {error.message}"
                )

    def apply_fixes(self, csv_file: Path, fixes: dict[tuple[int, str], str]):
        """Apply fixes to a CSV file."""
        rows = []
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise ValueError(f"No fieldnames found in {csv_file}")
            for row_num, row in enumerate(reader, start=2):
                for column in row.keys():
                    if (row_num, column) in fixes:
                        row[column] = fixes[(row_num, column)]
                rows.append(row)

        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                lineterminator="\n",
                quoting=csv.QUOTE_ALL,
                escapechar=None,
                doublequote=True,
            )
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Validate CSV file formatting (tags ordering, whitespace, duplicates)"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically fix formatting issues where possible",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data directory (default: auto-detect)",
    )
    args = parser.parse_args()

    data_dir = args.data_dir if args.data_dir else get_data_dir()
    validator = FormatValidator(data_dir)

    print(f"Validating CSV files in {data_dir}...")
    validator.validate_all_csvs()

    if args.auto_fix:
        validator.auto_fix()
    else:
        validator.print_errors()
        if validator.errors:
            print("Run with --auto-fix to automatically fix these issues")
            exit(1)


if __name__ == "__main__":
    main()
