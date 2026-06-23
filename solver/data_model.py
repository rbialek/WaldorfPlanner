"""Dataclasses for school timetable data."""

from dataclasses import dataclass, field


@dataclass
class Teacher:
    id: str
    name: str
    subjects: list[str]
    unavailable: list[tuple[str, int, int]] = field(default_factory=list)
    # Each tuple: (day, slot_from, slot_to) inclusive
    # day: "pn", "wt", "sr", "cz", "pt"


@dataclass
class Subject:
    id: str
    name: str
    teachers: list[str]
    subject_type: str  # "yearly", "epoch", "extension", "language", "english"


@dataclass
class Student:
    nr: int
    name: str
    class_id: str
    extensions: list[str]
    language: str  # "j_hiszpanski", "ZW", etc.
    english_group: str  # "angielski1" or "angielski2"


@dataclass
class ClassGroup:
    id: str
    students: list[Student]


@dataclass
class MatrixEntry:
    subject: str
    teacher: str
    hours: dict[str, int]  # {"kl9": 4, "kl10": 0, ...}


@dataclass
class Epoch:
    period: str
    assignments: dict[str, str]  # {"kl9": "informatyka", ...}


@dataclass
class LanguageGroup:
    language: str
    teacher: str
    students: list[Student]
    hours: int = 2
    consecutive: bool = True


@dataclass
class OptimizationRule:
    id: str
    description: str
    weight: int


@dataclass
class Rules:
    slots: list[tuple[int, str]]  # [(0, "7:25 - 8:10"), ...]
    days: list[str]  # ["pn", "wt", "sr", "cz", "pt"]
    max_lessons_per_day: int
    preferred_start: int  # slot number
    epochs: list[Epoch]
    epoch_classes: list[str]
    optimization: list[OptimizationRule]


@dataclass
class SchoolData:
    """Complete parsed school data."""
    teachers: list[Teacher]
    subjects: list[Subject]
    classes: list[ClassGroup]
    matrix: list[MatrixEntry]
    rules: Rules
    language_groups: list[LanguageGroup]
