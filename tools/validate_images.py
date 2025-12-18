#!/usr/bin/env python3
"""Validate and fix image references and filenames."""

import argparse
import csv
import re
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path

from utils import get_data_dir
from validation_common import ValidationError


class ImgTagParser(HTMLParser):
    """Extract src attribute from img tags."""

    def __init__(self):
        super().__init__()
        self.src = None

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            for attr, value in attrs:
                if attr == "src":
                    self.src = value


def normalize_name(name: str) -> str:
    """Convert name to lowercase with hyphens."""
    # Remove punctuation and extra spaces
    name = re.sub(r"[^\w\s-]", "", name)
    # Convert to lowercase and replace spaces with hyphens
    name = name.lower().strip().replace(" ", "-")
    # Remove consecutive hyphens
    name = re.sub(r"-+", "-", name)
    return name


def extract_image_filename(picture_html: str) -> str | None:
    """Extract filename from img tag HTML."""
    if not picture_html or "<img" not in picture_html:
        return None

    parser = ImgTagParser()
    parser.feed(picture_html)
    return parser.src


def is_valid_image_filename(filename: str, person_name: str) -> bool:
    """Check if filename follows the uh_name-name.ext format."""
    if not filename:
        return False

    # Must start with uh_
    if not filename.startswith("uh_"):
        return False

    # Must have a valid image extension
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif"}:
        return False

    # Extract the name part (between uh_ and extension)
    name_part = filename[3 : -len(ext)]

    # Should match normalized person name
    expected_name = normalize_name(person_name)
    return name_part == expected_name


class ImageValidator:
    def __init__(self, data_dir: Path, auto_fix: bool = False):
        self.data_dir = data_dir
        self.media_dir = data_dir.parent / "media"
        self.auto_fix = auto_fix
        self.errors: list[ValidationError] = []

    def validate_all(self):
        """Validate all image references in Person CSV."""
        csv_file = self.data_dir / "Ultimate History | Person.csv"
        if not csv_file.exists():
            print(f"Error: {csv_file} not found")
            return

        self.validate_csv(csv_file)

    def validate_csv(self, csv_file: Path):
        """Validate image references in a CSV file."""
        csv_name = csv_file.name

        # Read CSV
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if fieldnames is None:
                raise ValueError(f"No fieldnames found in {csv_file}")

            rows = list(reader)

        # Get all image files in media directory
        image_files = {
            f.name
            for f in self.media_dir.glob("*")
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}
        }

        # Track referenced images
        referenced_images = set()

        # Check each row
        for row_num, row in enumerate(rows, start=2):
            name = row.get("name", "")
            picture_html = row.get("picture", "")

            image_filename = extract_image_filename(picture_html)

            if not image_filename:
                # No image reference - skip
                continue

            referenced_images.add(image_filename)

            # Check if image exists
            if image_filename not in image_files:
                self.errors.append(
                    ValidationError(
                        csv_file=csv_name,
                        row_num=row_num,
                        column="picture",
                        error_type="missing_file",
                        message=f"Image file '{image_filename}' referenced but not found in {self.media_dir}",
                        current_value=image_filename,
                        suggested_fix=None,
                    )
                )

            # Check if filename follows convention
            if not is_valid_image_filename(image_filename, name):
                expected_ext = Path(image_filename).suffix if image_filename else ".jpg"
                expected_filename = f"uh_{normalize_name(name)}{expected_ext}"

                self.errors.append(
                    ValidationError(
                        csv_file=csv_name,
                        row_num=row_num,
                        column="picture",
                        error_type="invalid_format",
                        message=f"Image filename '{image_filename}' does not follow naming convention",
                        current_value=image_filename,
                        suggested_fix=expected_filename,
                    )
                )

        # Check for unreferenced images in media directory
        unreferenced = image_files - referenced_images
        # Filter out font files and other non-image files
        unreferenced = {f for f in unreferenced if not f.endswith(".ttf")}

        for filename in sorted(unreferenced):
            self.errors.append(
                ValidationError(
                    csv_file=csv_name,
                    row_num=0,
                    column="picture",
                    error_type="unreferenced_file",
                    message=f"Image file '{filename}' exists in {self.media_dir} but is not referenced in CSV",
                    current_value=filename,
                    suggested_fix=None,
                )
            )

        # Apply fixes if requested
        if self.auto_fix:
            self.fix_images(csv_file, rows, fieldnames)

    def fix_images(self, csv_file: Path, rows: list[dict], fieldnames: Sequence[str]):
        """Fix image references and filenames."""
        rename_map = {}  # old_filename -> new_filename
        updated_rows = []

        print("\nApplying fixes...")

        for row in rows:
            name = row.get("name", "")
            picture_html = row.get("picture", "")

            old_filename = extract_image_filename(picture_html)
            if not old_filename:
                updated_rows.append(row)
                continue

            ext = Path(old_filename).suffix
            expected_filename = f"uh_{normalize_name(name)}{ext}"

            # Check if we need to rename
            if old_filename != expected_filename:
                rename_map[old_filename] = expected_filename

            updated_rows.append(row)

        # Rename physical files
        if rename_map:
            print(f"\nRenaming {len(rename_map)} files...")
            for old_name, new_name in rename_map.items():
                old_path = self.media_dir / old_name
                new_path = self.media_dir / new_name

                if old_path.exists():
                    old_path.rename(new_path)
                    print(f"  Renamed: {old_name} -> {new_name}")
                else:
                    print(f"  Warning: File not found: {old_name}")

        # Update CSV with new filenames
        if rename_map:
            print("\nUpdating CSV references...")
            for row in updated_rows:
                picture_html = row.get("picture", "")
                old_filename = extract_image_filename(picture_html)

                if old_filename and old_filename in rename_map:
                    new_filename = rename_map[old_filename]
                    row["picture"] = picture_html.replace(old_filename, new_filename)
                    print(f"  Updated reference: {old_filename} -> {new_filename}")

            # Write updated CSV
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
                writer.writerows(updated_rows)

            print(f"\nFixed {len(rename_map)} image references")

    def print_errors(self):
        """Print all validation errors."""
        if not self.errors:
            print("✓ All image references are valid!")
            return

        print(f"\nFound {len(self.errors)} validation error(s):\n")

        # Group by error type
        by_type = {}
        for error in self.errors:
            by_type.setdefault(error.error_type, []).append(error)

        for error_type, errors in sorted(by_type.items()):
            print(f"{error_type.upper().replace('_', ' ')} ({len(errors)}):")
            for error in errors:
                if error.row_num > 0:
                    print(f"  Row {error.row_num}: {error.message}")
                else:
                    print(f"  {error.message}")

                if error.suggested_fix:
                    print(f"    Suggested fix: {error.suggested_fix}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate and optionally fix image references and filenames"
    )
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically fix image filename issues",
    )

    args = parser.parse_args()

    data_dir = get_data_dir()
    validator = ImageValidator(data_dir, auto_fix=args.auto_fix)

    print(f"Validating images in {data_dir}...")
    validator.validate_all()

    if not args.auto_fix:
        validator.print_errors()

        if validator.errors:
            print("\nRun with --auto-fix to automatically fix these issues")
            exit(1)
    else:
        # After fixing, validate again to show remaining issues
        validator.errors = []
        validator.auto_fix = False
        validator.validate_all()
        validator.print_errors()

        if validator.errors:
            exit(1)


if __name__ == "__main__":
    main()
