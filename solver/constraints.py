"""Constraint and optimization functions for timetable evaluation.

Convention:
- Positive score = good (preferred state)
- Negative score = bad (violation or unwanted state)
- Each function returns a WEIGHTED score (raw_score * weight from zasady.md)
- Hard constraints: +weight if satisfied, -1000 per violation
- Soft constraints: +weight if perfect, 0 if worst, scaled proportionally

Generated from dane/2026-27/zasady.md.
Regenerate with /wygeneruj_wagi command.
"""

from .data_model import SchoolData

Schedule = dict[tuple[str, str, int], tuple[str, str]]

HARD_PENALTY = -1000
DEMANDING_SUBJECTS = {"matematyka", "fizyka", "informatyka", "chemia", "biologia"}


# =============================================================================
# HARD CONSTRAINTS
# Return +weight if fully satisfied, -1000 * violations if not.
# =============================================================================

def hard_no_student_conflict(schedule: Schedule, data: SchoolData) -> float:
    """Uczen nie moze miec dwoch lekcji w tym samym czasie.
    Weight: HARD (satisfied=+100, violation=-1000 each)
    """
    weight = 100
    # Schedule keys are unique (class, day, slot) so no intra-class conflicts.
    # Check cross-class language group conflicts:
    lang_subjects = {lg.language for lg in data.language_groups}
    violations = 0
    for lg in data.language_groups:
        classes_in_group = sorted(set(st.class_id for st in lg.students))
        for (cls_id, d, s), (subj, _) in schedule.items():
            if subj == lg.language and cls_id in classes_in_group:
                for other_cls in classes_in_group:
                    if other_cls == cls_id:
                        continue
                    other_key = (other_cls, d, s)
                    if other_key in schedule and schedule[other_key][0] != subj:
                        violations += 1
    if violations > 0:
        return violations * HARD_PENALTY
    return weight


def hard_no_teacher_conflict(schedule: Schedule, data: SchoolData) -> float:
    """Nauczyciel nie moze prowadzic dwoch lekcji w tym samym czasie.
    Weight: HARD (satisfied=+100, violation=-1000 each)
    """
    weight = 100
    lang_subjects = {lg.language for lg in data.language_groups}
    teacher_slots: dict[tuple[str, str, int], list[tuple[str, str]]] = {}
    for (cls_id, d, s), (subj, teacher) in schedule.items():
        key = (teacher, d, s)
        teacher_slots.setdefault(key, []).append((cls_id, subj))

    violations = 0
    for (teacher, d, s), entries in teacher_slots.items():
        if len(entries) <= 1:
            continue
        if teacher == "-":
            continue
        subjects = set(subj for _, subj in entries)
        if len(subjects) == 1 and subjects.pop() in lang_subjects:
            continue
        violations += len(entries) - 1

    if violations > 0:
        return violations * HARD_PENALTY
    return weight


def hard_max_lessons_per_day(schedule: Schedule, data: SchoolData) -> float:
    """Maksymalnie 9 lekcji dziennie na klase.
    Weight: HARD (satisfied=+100, violation=-1000 per excess)
    """
    weight = 100
    max_allowed = data.rules.max_lessons_per_day
    class_day_count: dict[tuple[str, str], int] = {}
    for (cls_id, d, s) in schedule:
        key = (cls_id, d)
        class_day_count[key] = class_day_count.get(key, 0) + 1

    violations = 0
    for count in class_day_count.values():
        if count > max_allowed:
            violations += count - max_allowed

    if violations > 0:
        return violations * HARD_PENALTY
    return weight


def hard_teacher_unavailable(schedule: Schedule, data: SchoolData) -> float:
    """Uwzglednic ograniczenia dostepnosci nauczycieli.
    Weight: HARD (satisfied=+100, violation=-1000 each)
    """
    weight = 100
    unavail_set: set[tuple[str, str, int]] = set()
    for teacher in data.teachers:
        for day, slot_from, slot_to in teacher.unavailable:
            for s in range(slot_from, slot_to + 1):
                unavail_set.add((teacher.id, day, s))

    violations = 0
    for (cls_id, d, s), (subj, teacher) in schedule.items():
        if (teacher, d, s) in unavail_set:
            violations += 1

    if violations > 0:
        return violations * HARD_PENALTY
    return weight


def hard_epoch_slots(schedule: Schedule, data: SchoolData) -> float:
    """Epoki (l. glowna) musza byc w slotach 1-2 dla klas epokowych.
    Weight: HARD (satisfied=+100, violation=-1000 each)
    """
    weight = 100
    violations = 0
    for cls_id in data.rules.epoch_classes:
        for d in data.rules.days:
            for s in (1, 2):
                key = (cls_id, d, s)
                if key not in schedule:
                    violations += 1
                elif schedule[key][0] != "l_glowna":
                    violations += 1

    if violations > 0:
        return violations * HARD_PENALTY
    return weight


# =============================================================================
# SOFT CONSTRAINTS
# Return +weight (perfect) to 0 (worst), scaled proportionally.
# Weight comes from zasady.md optimization table.
# =============================================================================

def soft_unikaj_slot0(schedule: Schedule, data: SchoolData) -> float:
    """Lekcje zaczynaja sie od lekcji 1 (8:15). Lekcja 0 tylko wyjatkowo.
    Weight: 100. Returns +100 (no slot 0) to 0 (every class uses slot 0 daily).
    """
    weight = 100
    max_possible = len(data.classes) * len(data.rules.days)
    if max_possible == 0:
        return weight
    slot0_count = sum(1 for (_, _, s) in schedule if s == 0)
    ratio_good = 1.0 - (slot0_count / max_possible)
    return weight * ratio_good


def soft_brak_okienek_uczniow(schedule: Schedule, data: SchoolData) -> float:
    """Lekcje uczniow w jednym ciagu bez przerw.
    Weight: 50. Returns +50 (no gaps) to 0 (many gaps).
    """
    weight = 50
    total_gaps = 0
    total_spans = 0
    for cls in data.classes:
        for d in data.rules.days:
            slots = sorted(s for (k, day, s) in schedule if k == cls.id and day == d)
            if len(slots) >= 2:
                span = slots[-1] - slots[0] + 1
                gaps = span - len(slots)
                total_gaps += gaps
                total_spans += span
    if total_spans == 0:
        return weight
    ratio_good = 1.0 - (total_gaps / total_spans)
    return weight * ratio_good


def soft_wczesne_konczenie(schedule: Schedule, data: SchoolData) -> float:
    """Uczniowie koncza lekcje jak najwczesniej.
    Weight: 30. Returns +30 (all finish by slot 4) to 0 (all finish at slot 9).
    """
    weight = 30
    total_late = 0
    count = 0
    for cls in data.classes:
        for d in data.rules.days:
            slots = [s for (k, day, s) in schedule if k == cls.id and day == d]
            if slots:
                last = max(slots)
                if last > 4:
                    total_late += last - 4
                count += 1
    if count == 0:
        return weight
    max_late = 5 * count  # worst: finish at slot 9
    ratio_good = 1.0 - (total_late / max_late)
    return weight * ratio_good


def soft_trudne_wczesniej(schedule: Schedule, data: SchoolData) -> float:
    """Przedmioty wymagajace we wczesnych godzinach, po nich lzejsze.
    Weight: 25. Returns +25 (all demanding before slot 5) to 0 (all late).
    """
    weight = 25
    late_demanding = 0
    total_demanding = 0
    for (cls_id, d, s), (subj, _) in schedule.items():
        if subj in DEMANDING_SUBJECTS:
            total_demanding += 1
            if s >= 5:
                late_demanding += 1
    if total_demanding == 0:
        return weight
    ratio_good = 1.0 - (late_demanding / total_demanding)
    return weight * ratio_good


def soft_min_okienek_nauczycieli(schedule: Schedule, data: SchoolData) -> float:
    """Lekcje nauczyciela danego dnia w spojnym bloku.
    Weight: 20. Returns +20 (no gaps) to 0 (many gaps).
    """
    weight = 20
    total_gaps = 0
    total_spans = 0
    for teacher in data.teachers:
        for d in data.rules.days:
            slots = sorted(set(
                s for (_, day, s), (_, t) in schedule.items()
                if t == teacher.id and day == d
            ))
            if len(slots) >= 2:
                span = slots[-1] - slots[0] + 1
                gaps = span - len(slots)
                total_gaps += gaps
                total_spans += span
    if total_spans == 0:
        return weight
    ratio_good = 1.0 - (total_gaps / total_spans)
    return weight * ratio_good


def soft_kompaktowy_plan(schedule: Schedule, data: SchoolData) -> float:
    """Nauczyciele w najmniejszej liczbie dni.
    Weight: 10. Returns +10 (1 day avg) to 0 (5 days avg).
    """
    weight = 10
    total_days = 0
    total_teachers = 0
    for teacher in data.teachers:
        work_days = set()
        for (_, d, _), (_, t) in schedule.items():
            if t == teacher.id:
                work_days.add(d)
        if work_days:
            total_days += len(work_days)
            total_teachers += 1
    if total_teachers == 0:
        return weight
    avg_days = total_days / total_teachers
    ratio_good = 1.0 - ((avg_days - 1) / 4)
    return weight * max(0.0, ratio_good)


def soft_unikaj_pojedynczych(schedule: Schedule, data: SchoolData) -> float:
    """Unikaj sytuacji gdy nauczyciel przychodzi na 1 lekcje w dniu.
    Weight: 5. Returns +5 (no singles) to 0 (all single-lesson days).
    """
    weight = 5
    singles = 0
    work_days_total = 0
    for teacher in data.teachers:
        day_counts: dict[str, int] = {}
        for (_, d, _), (_, t) in schedule.items():
            if t == teacher.id:
                day_counts[d] = day_counts.get(d, 0) + 1
        for count in day_counts.values():
            work_days_total += 1
            if count == 1:
                singles += 1
    if work_days_total == 0:
        return weight
    ratio_good = 1.0 - (singles / work_days_total)
    return weight * ratio_good


# =============================================================================
# REGISTRY & EVALUATION
# =============================================================================

HARD_CONSTRAINTS = [
    ("no_student_conflict", hard_no_student_conflict),
    ("no_teacher_conflict", hard_no_teacher_conflict),
    ("max_lessons_per_day", hard_max_lessons_per_day),
    ("teacher_unavailable", hard_teacher_unavailable),
    ("epoch_slots", hard_epoch_slots),
]

SOFT_CONSTRAINTS = [
    ("unikaj_slot0", soft_unikaj_slot0),
    ("brak_okienek_uczniow", soft_brak_okienek_uczniow),
    ("wczesne_konczenie", soft_wczesne_konczenie),
    ("trudne_wczesniej", soft_trudne_wczesniej),
    ("min_okienek_nauczycieli", soft_min_okienek_nauczycieli),
    ("kompaktowy_plan", soft_kompaktowy_plan),
    ("unikaj_pojedynczych", soft_unikaj_pojedynczych),
]


def evaluate_schedule(schedule: Schedule, data: SchoolData) -> dict:
    """Evaluate a complete schedule against all constraints.

    Returns dict with:
        - hard_total: sum of hard scores (+100 each if OK, -1000*N if violated)
        - soft_total: sum of weighted soft scores (higher = better)
        - total: hard_total + soft_total
        - details: list of (name, type, score) tuples
    """
    hard_total = 0.0
    soft_total = 0.0
    details = []

    for name, func in HARD_CONSTRAINTS:
        score = func(schedule, data)
        hard_total += score
        details.append((name, "HARD", score))

    for name, func in SOFT_CONSTRAINTS:
        score = func(schedule, data)
        soft_total += score
        details.append((name, "SOFT", score))

    return {
        "hard_total": hard_total,
        "soft_total": soft_total,
        "total": hard_total + soft_total,
        "details": details,
    }
