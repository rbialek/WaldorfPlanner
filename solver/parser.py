"""Parser for school timetable .md data files."""

import re
from pathlib import Path

from .data_model import (
    ClassGroup,
    Epoch,
    LanguageGroup,
    MatrixEntry,
    OptimizationRule,
    Rules,
    SchoolData,
    Student,
    Subject,
    Teacher,
)


def parse_md_table(text: str) -> list[dict[str, str]]:
    """Parse a markdown table into a list of dicts keyed by header names."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    table_lines = [l for l in lines if l.startswith("|")]
    if len(table_lines) < 3:
        return []
    header_line = table_lines[0]
    headers = [h.strip() for h in header_line.split("|") if h.strip()]
    rows = []
    for line in table_lines[2:]:  # skip header and separator
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= len(headers):
            rows.append(dict(zip(headers, cells[: len(headers)])))
        elif cells:
            # Pad with empty strings
            padded = cells + [""] * (len(headers) - len(cells))
            rows.append(dict(zip(headers, padded)))
    return rows


def extract_section(text: str, heading: str) -> str:
    """Extract text under a heading that starts with the given string."""
    # Find heading line that contains the search string
    for match in re.finditer(r"^(#{2,3})\s+(.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        if title.startswith(heading) or heading in title:
            start = match.end()
            # Find next heading of same or higher level
            next_heading = re.search(rf"^#{{{1},{level}}}\s", text[start:], re.MULTILINE)
            if next_heading:
                return text[start : start + next_heading.start()]
            return text[start:]
    return ""


DAY_MAP = {
    "poniedzialek": "pn",
    "poniedzialki": "pn",
    "poniedzialku": "pn",
    "wtorek": "wt",
    "wtorki": "wt",
    "wtorku": "wt",
    "wtorkow": "wt",
    "sroda": "sr",
    "srody": "sr",
    "srode": "sr",
    "czwartek": "cz",
    "czwartki": "cz",
    "czwartku": "cz",
    "czwartkow": "cz",
    "piatek": "pt",
    "piatki": "pt",
    "piatku": "pt",
    "piatkow": "pt",
}

DAYS = ["pn", "wt", "sr", "cz", "pt"]


def _parse_time_to_slot(hour: float, slots: list[tuple[int, str]]) -> int:
    """Convert hour (e.g. 10.0) to the closest slot number."""
    for slot_nr, time_range in slots:
        start_str = time_range.split("-")[0].strip()
        h, m = start_str.replace(".", ":").split(":")
        slot_start = int(h) + int(m) / 60
        end_str = time_range.split("-")[1].strip()
        h2, m2 = end_str.replace(".", ":").split(":")
        slot_end = int(h2) + int(m2) / 60
        if slot_start <= hour < slot_end:
            return slot_nr
    # If past all slots, return last slot
    return slots[-1][0] if slots else 9


def parse_unavailability(constraint_text: str, slots: list[tuple[int, str]]) -> list[tuple[str, int, int]]:
    """Parse teacher unavailability constraint text into structured data."""
    if not constraint_text or constraint_text.strip().lower() == "brak":
        return []

    result = []
    parts = [p.strip() for p in constraint_text.split(",")]

    for part in parts:
        part_lower = part.lower().strip()

        # Find which day
        day = None
        for word, day_code in DAY_MAP.items():
            if word in part_lower:
                day = day_code
                break

        if not day:
            continue

        # Check for "caly dzien"
        if "caly dzien" in part_lower:
            result.append((day, 0, 9))
            continue

        # Extract hour range like "8-10", "10-15", "13-15"
        hour_match = re.search(r"(\d{1,2})\s*-\s*(\d{1,2})", part)
        if hour_match:
            hour_from = int(hour_match.group(1))
            hour_to = int(hour_match.group(2))
            slot_from = _parse_time_to_slot(float(hour_from), slots)
            slot_to = _parse_time_to_slot(float(hour_to) - 0.01, slots)
            if slot_to < slot_from:
                slot_to = slot_from
            result.append((day, slot_from, slot_to))

    return result


def parse_teachers(text: str, slots: list[tuple[int, str]]) -> list[Teacher]:
    """Parse nauczyciele.md content."""
    rows = parse_md_table(text)
    teachers = []
    for row in rows:
        teacher_id = row.get("ID", "")
        name = row.get("Imie i nazwisko", "")
        subjects_str = row.get("Przedmioty", "")
        subjects = [s.strip() for s in subjects_str.split(",") if s.strip()]
        constraint_text = row.get("Ograniczenia dostepnosci", "")
        unavailable = parse_unavailability(constraint_text, slots)
        teachers.append(Teacher(
            id=teacher_id,
            name=name,
            subjects=subjects,
            unavailable=unavailable,
        ))
    return teachers


def parse_subjects(text: str) -> list[Subject]:
    """Parse przedmioty.md content."""
    subjects = []
    seen_ids = set()

    sections = [
        ("yearly", "Przedmioty caloroczne (obowiazkowe"),
        ("epoch", "Przedmioty epokowe"),
        ("extension", "Przedmioty rozszerzone"),
        ("language", "Jezyki obce"),
    ]

    for subj_type, heading in sections:
        section = extract_section(text, heading)
        if not section:
            continue
        rows = parse_md_table(section)
        for row in rows:
            subj_id = row.get("ID", "")
            if not subj_id or subj_id in seen_ids:
                continue
            seen_ids.add(subj_id)
            name = row.get("Nazwa", "")
            teachers_str = row.get("Nauczyciele", "")
            # Extract teacher IDs like "n1", "n12"
            teacher_ids = re.findall(r"\b(n\d+)\b", teachers_str)

            # Detect english type
            actual_type = subj_type
            if subj_id.startswith("angielski"):
                actual_type = "english"

            subjects.append(Subject(
                id=subj_id,
                name=name,
                teachers=teacher_ids,
                subject_type=actual_type,
            ))

    return subjects


def parse_classes(text: str) -> list[ClassGroup]:
    """Parse klasy.md content."""
    classes = []
    # Find all class sections
    class_pattern = re.compile(r"## Klasa (\d+) \((\d+) uczniow\)")
    matches = list(class_pattern.finditer(text))

    for i, match in enumerate(matches):
        class_num = match.group(1)
        class_id = f"kl{class_num}"
        # Extract section text
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[start:end]

        rows = parse_md_table(section)
        students = []
        for row in rows:
            nr_str = row.get("Nr", "0")
            try:
                nr = int(nr_str)
            except ValueError:
                continue
            name = row.get("Imie i nazwisko", "")
            extensions = []
            for key in ["Rozszerzenie 1", "Rozszerzenie 2", "Rozszerzenie 3"]:
                val = row.get(key, "-").strip()
                if val and val != "-":
                    extensions.append(val)
            language = row.get("Jezyk obcy", "").strip()
            english = row.get("Angielski", "").strip()
            students.append(Student(
                nr=nr,
                name=name,
                class_id=class_id,
                extensions=extensions,
                language=language,
                english_group=english,
            ))
        classes.append(ClassGroup(id=class_id, students=students))

    return classes


def parse_matrix(text: str) -> list[MatrixEntry]:
    """Parse matryca.md content."""
    entries = []

    for section_name in ["Przedmioty standardowe", "Przedmioty rozszerzone"]:
        section = extract_section(text, section_name)
        if not section:
            continue
        rows = parse_md_table(section)
        for row in rows:
            subject = row.get("Przedmiot", "")
            teacher = row.get("Nauczyciel", "")
            teacher_id = re.search(r"\b(n\d+)\b", teacher)
            if not teacher_id:
                continue
            hours = {}
            for key, val in row.items():
                km = re.match(r"kl(\d+)", key)
                if km:
                    try:
                        hours[key] = int(val)
                    except ValueError:
                        hours[key] = 0
            if subject and hours:
                entries.append(MatrixEntry(
                    subject=subject,
                    teacher=teacher_id.group(1),
                    hours=hours,
                ))

    return entries


def parse_rules(text: str) -> Rules:
    """Parse zasady.md content."""
    # Parse slots
    slots_section = extract_section(text, "Siatka godzin lekcyjnych")
    slots = []
    rows = parse_md_table(slots_section)
    for row in rows:
        nr_str = row.get("Nr lekcji", "0")
        try:
            nr = int(nr_str)
        except ValueError:
            continue
        time_range = row.get("Godziny", "")
        slots.append((nr, time_range))

    # Parse epochs
    epochs_section = extract_section(text, "System epok")
    epoch_rows = parse_md_table(epochs_section)
    epochs = []
    epoch_classes = set()
    for row in epoch_rows:
        period = row.get("Okres", "")
        assignments = {}
        for key, val in row.items():
            if key.startswith("kl"):
                assignments[key] = val.strip()
                epoch_classes.add(key)
        if period and assignments:
            epochs.append(Epoch(period=period, assignments=assignments))

    # Parse max lessons
    constraints_section = extract_section(text, "Ograniczenia planowania")
    max_lessons = 8
    ml_match = re.search(r"Maksymalnie (\d+) lekcji", constraints_section)
    if ml_match:
        max_lessons = int(ml_match.group(1))

    # Parse optimization rules
    opt_section = extract_section(text, "Optymalizacja")
    opt_rows = parse_md_table(opt_section)
    optimization = []
    for row in opt_rows:
        rule_id = row.get("ID", "")
        desc = row.get("Opis", "")
        weight_str = row.get("Waga", "0")
        try:
            weight = int(weight_str)
        except ValueError:
            weight = 0
        if rule_id:
            optimization.append(OptimizationRule(
                id=rule_id, description=desc, weight=weight,
            ))

    return Rules(
        slots=slots,
        days=DAYS,
        max_lessons_per_day=max_lessons,
        preferred_start=1,
        epochs=epochs,
        epoch_classes=sorted(epoch_classes),
        optimization=optimization,
    )


def build_language_groups(
    classes: list[ClassGroup],
    subjects: list[Subject],
) -> list[LanguageGroup]:
    """Build cross-class language groups from student data."""
    # Map language -> teacher from subjects
    lang_teacher = {}
    for subj in subjects:
        if subj.subject_type == "language" and subj.teachers:
            lang_teacher[subj.id] = subj.teachers[0]

    # Group students by language
    lang_students: dict[str, list[Student]] = {}
    for cls in classes:
        for student in cls.students:
            lang = student.language
            if lang and lang != "ZW":
                lang_students.setdefault(lang, []).append(student)

    groups = []
    for lang, students in lang_students.items():
        teacher = lang_teacher.get(lang, "")
        groups.append(LanguageGroup(
            language=lang,
            teacher=teacher,
            students=students,
            hours=2,
            consecutive=True,
        ))

    return groups


def parse_all(data_dir: str | Path) -> SchoolData:
    """Parse all data files from a directory."""
    data_dir = Path(data_dir)

    rules_text = (data_dir / "zasady.md").read_text(encoding="utf-8")
    rules = parse_rules(rules_text)

    teachers_text = (data_dir / "nauczyciele.md").read_text(encoding="utf-8")
    teachers = parse_teachers(teachers_text, rules.slots)

    subjects_text = (data_dir / "przedmioty.md").read_text(encoding="utf-8")
    subjects = parse_subjects(subjects_text)

    classes_text = (data_dir / "klasy.md").read_text(encoding="utf-8")
    classes = parse_classes(classes_text)

    matrix_text = (data_dir / "matryca.md").read_text(encoding="utf-8")
    matrix = parse_matrix(matrix_text)

    language_groups = build_language_groups(classes, subjects)

    return SchoolData(
        teachers=teachers,
        subjects=subjects,
        classes=classes,
        matrix=matrix,
        rules=rules,
        language_groups=language_groups,
    )
