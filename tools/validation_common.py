#!/usr/bin/env python3
"""Common validation utilities and classes shared across validators."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    csv_file: str
    row_num: int
    column: str
    error_type: str
    message: str
    current_value: str
    suggested_fix: Optional[str] = None
