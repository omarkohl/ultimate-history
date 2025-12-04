"""Shared data models for Ultimate History notes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Relationship:
    """A relationship to another note."""

    target_name: str
    target_guid: Optional[str]
    description: Optional[str]


@dataclass
class Note(ABC):
    """Base class for all note types."""

    guid: str
    related_persons: list[Relationship] = field(default_factory=list)
    related_events: list[Relationship] = field(default_factory=list)

    @abstractmethod
    def get_display_name(self) -> str:
        """Get the name/content for display purposes."""
        pass

    @abstractmethod
    def get_note_type(self) -> str:
        """Get the note type name (Person, Event, QA, Cloze)."""
        pass

    def get_all_outgoing_relationships(self) -> list[Relationship]:
        """Get all outgoing relationships (persons + events)."""
        return self.related_persons + self.related_events

    def total_relationships(self, incoming_count: int) -> int:
        """Get total relationship count (outgoing + incoming)."""
        return len(self.get_all_outgoing_relationships()) + incoming_count


@dataclass
class Person(Note):
    """A Person note."""

    name: str = ""
    birth: Optional[str] = None
    death: Optional[str] = None

    def get_display_name(self) -> str:
        return self.name

    def get_note_type(self) -> str:
        return "Person"


@dataclass
class Event(Note):
    """An Event note."""

    name: str = ""
    start: Optional[str] = None
    end: Optional[str] = None

    def get_display_name(self) -> str:
        return self.name

    def get_note_type(self) -> str:
        return "Event"


@dataclass
class QA(Note):
    """A QA (Question-Answer) note."""

    question: str = ""
    answer: str = ""

    def get_display_name(self) -> str:
        return self.question

    def get_note_type(self) -> str:
        return "QA"


@dataclass
class Cloze(Note):
    """A Cloze deletion note."""

    text: str = ""

    def get_display_name(self) -> str:
        return self.text

    def get_note_type(self) -> str:
        return "Cloze"
