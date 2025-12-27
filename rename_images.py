#!/usr/bin/env python3
"""Rename images to uh_name-name.jpg format and update CSV references."""

import csv
import re
from pathlib import Path
from html.parser import HTMLParser


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


def main():
    csv_path = Path("src/data/person.csv")
    media_path = Path("src/media")

    # Read CSV and build rename mapping
    rename_map = {}  # old_filename -> new_filename
    rows = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

            name = row["name"]
            picture_html = row["picture"]

            old_filename = extract_image_filename(picture_html)
            if not old_filename:
                continue

            # Get file extension
            ext = Path(old_filename).suffix

            # Create new filename
            new_filename = f"uh_{normalize_name(name)}{ext}"

            rename_map[old_filename] = new_filename
            print(f"{old_filename} -> {new_filename}")

    # Rename physical files
    print("\nRenaming files...")
    for old_name, new_name in rename_map.items():
        old_path = media_path / old_name
        new_path = media_path / new_name

        if old_path.exists():
            old_path.rename(new_path)
            print(f"Renamed: {old_name}")
        else:
            print(f"Warning: File not found: {old_name}")

    # Update CSV with new filenames
    print("\nUpdating CSV...")
    for row in rows:
        picture_html = row["picture"]
        old_filename = extract_image_filename(picture_html)

        if old_filename and old_filename in rename_map:
            new_filename = rename_map[old_filename]
            row["picture"] = picture_html.replace(old_filename, new_filename)

    # Write updated CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
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

    print(f"\nDone! Renamed {len(rename_map)} images and updated CSV.")


if __name__ == "__main__":
    main()
