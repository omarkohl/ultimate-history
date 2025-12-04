"""Shared utilities for Ultimate History tools."""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


def parse_reference(
    value: str,
) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Parse a reference in format 'NAME (DATE[ - DATE]): RELATIONSHIP'.

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


def fuzzy_match(name: str, candidates: dict, threshold: float = 0.8) -> Optional[str]:
    """Find the best fuzzy match for a name among candidates.

    Args:
        name: The name to match
        candidates: Dictionary with candidate names as keys
        threshold: Minimum similarity ratio (0.0 to 1.0)

    Returns:
        Best matching candidate name, or None if no match above threshold
    """
    best_match = None
    best_ratio = 0.0

    for candidate in candidates.keys():
        ratio = SequenceMatcher(None, name.lower(), candidate.lower()).ratio()
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = candidate

    return best_match


def get_data_dir() -> Path:
    """Get the data directory path (src/data from project root)."""
    # Assumes utils.py is in tools/
    return Path(__file__).parent.parent / "src" / "data"
