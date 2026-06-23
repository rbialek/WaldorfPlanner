"""Constraint and optimization functions for timetable evaluation.

Single source of truth for scoring schedules. Used by both GA and CP-SAT.
Weights are read from data.rules.optimization (parsed from zasady.md).

Convention:
- Positive score = good (preferred state)
- Negative score = bad (violation or unwanted state)
- Hard constraints: +100 if satisfied, -1000 per violation
- Soft constraints: +weight if perfect, 0 if worst (weight from zasady.md)

Regenerate with /wygeneruj_wagi command.
"""

from .data_model import SchoolData

Schedule = dict[tuple[str, str, int], tuple[str, str]]

HARD_PENALTY = -1000
HARD_REWARD = 100
DEMANDING_SUBJECTS = {"matematyka", "fizyka", "informatyka", "chemia", "biologia"}


def _get_weight(data: SchoolData, rule_id: str) -> float:
    """Look up soft constraint weight from parsed zasady.md. Returns 0 if not found."""
    for r in data.rules.optimization:
        if r.id == rule_id:
            return float(r.weight)
    return 0.0


# =============================================================================
# HARD CONSTRAINTS
# Each returns +100 if fully satisfied, -1000 * violation_count if not.
# =============================================================================

def hard_no_student_conflict(schedule: Schedule, data: SchoolData) -> float:
    """No student may have two lessons at the same time."""
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
    return HARD_PENALTY * violations if violations else HARD_REWARD


def hard_no_teacher_conflict(schedule: Schedule, data: SchoolData) -> float:
    """No teacher may teach two lessons at the same time."""
    lang_subjects = {lg.language for lg in data.language_groups}
    teacher_slots: dict[tuple[str, str, int], list[tuple[str, str]]] = {}
    for (cls_id, d, s), (subj, teacher) in schedule.items():
        key = (teacher, d, s)
        teacher_slots.setdefault(key, []).append((cls_id, subj))

    violations = 0
    for (teacher, d, s), entries in teacher_slots.items():
        if len(entries) <= 1 or teacher == "-":
            continue
        subjects = set(subj for _, subj in entries)
        if len(subjects) == 1 and subjects.pop() in lang_subjects:
            continue
        violations += len(entries) - 1
    return HARD_PENALTY * violations if violations else HARD_REWARD


def hard_max_lessons_per_day(schedule: Schedule, data: SchoolData) -> float:
    """No class may exceed the maximum lessons per day (from zasady.md)."""
    max_allowed = data.rules.max_lessons_per_day
    class_day_count: dict[tuple[str, str], int] = {}
    for (cls_id, d, s) in schedule:
        key = (cls_id, d)
        class_day_count[key] = class_day_count.get(key, 0) + 1

    violations = sum(
        count - max_allowed
        for count in class_day_count.values()
        if count > max_allowed
    )
    return HARD_PENALTY * violations if violations else HARD_REWARD


def hard_teacher_unavailable(schedule: Schedule, data: SchoolData) -> float:
    """No lesson may be scheduled during a teacher's unavailable time."""
    unavail_set: set[tuple[str, str, int]] = set()
    for teacher in data.teachers:
        for day, slot_from, slot_to in teacher.unavailable:
            for s in range(slot_from, slot_to + 1):
                unavail_set.add((teacher.id, day, s))

    violations = sum(
        1 for (_, d, s), (_, teacher) in schedule.items()
        if (teacher, d, s) in unavail_set
    )
    return HARD_PENALTY * violations if violations else HARD_REWARD


def hard_epoch_slots(schedule: Schedule, data: SchoolData) -> float:
    """Epoch classes must have l. glowna in slots 1-2 every day."""
    violations = 0
    for cls_id in data.rules.epoch_classes:
        for d in data.rules.days:
            for s in (1, 2):
                key = (cls_id, d, s)
                if key not in schedule or schedule[key][0] != "l_glowna":
                    violations += 1
    return HARD_PENALTY * violations if violations else HARD_REWARD


# =============================================================================
# SOFT CONSTRAINTS
# Each reads its weight from data.rules.optimization (zasady.md).
# Returns +weight (perfect) to 0 (worst), scaled by quality ratio.
# If weight is 0 in zasady.md, constraint is disabled (returns 0).
# =============================================================================

def soft_avoid_slot0(schedule: Schedule, data: SchoolData) -> float:
    """Lessons should start from slot 1 (8:15). Slot 0 (7:25) only exceptionally."""
    weight = _get_weight(data, "avoid_slot0")
    if weight == 0:
        return 0.0
    max_possible = len(data.classes) * len(data.rules.days)
    if max_possible == 0:
        return weight
    slot0_count = sum(1 for (_, _, s) in schedule if s == 0)
    return weight * (1.0 - slot0_count / max_possible)


def soft_no_student_gaps(schedule: Schedule, data: SchoolData) -> float:
    """Student lessons should be consecutive with no gaps."""
    weight = _get_weight(data, "no_student_gaps")
    if weight == 0:
        return 0.0
    total_gaps = 0
    total_spans = 0
    for cls in data.classes:
        for d in data.rules.days:
            slots = sorted(s for (k, day, s) in schedule if k == cls.id and day == d)
            if len(slots) >= 2:
                span = slots[-1] - slots[0] + 1
                total_gaps += span - len(slots)
                total_spans += span
    if total_spans == 0:
        return weight
    return weight * (1.0 - total_gaps / total_spans)


def soft_early_finish(schedule: Schedule, data: SchoolData) -> float:
    """Students should finish lessons as early as possible."""
    weight = _get_weight(data, "early_finish")
    if weight == 0:
        return 0.0
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
    max_late = 5 * count
    return weight * (1.0 - total_late / max_late)


def soft_demanding_early(schedule: Schedule, data: SchoolData) -> float:
    """Demanding subjects (math, physics, etc.) should be in early slots."""
    weight = _get_weight(data, "demanding_early")
    if weight == 0:
        return 0.0
    late = 0
    total = 0
    for (_, _, s), (subj, _) in schedule.items():
        if subj in DEMANDING_SUBJECTS:
            total += 1
            if s >= 5:
                late += 1
    if total == 0:
        return weight
    return weight * (1.0 - late / total)


def soft_no_teacher_gaps(schedule: Schedule, data: SchoolData) -> float:
    """Teacher lessons on a given day should form a continuous block."""
    weight = _get_weight(data, "no_teacher_gaps")
    if weight == 0:
        return 0.0
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
                total_gaps += span - len(slots)
                total_spans += span
    if total_spans == 0:
        return weight
    return weight * (1.0 - total_gaps / total_spans)


def soft_compact_teacher_schedule(schedule: Schedule, data: SchoolData) -> float:
    """Teachers should work the fewest days possible."""
    weight = _get_weight(data, "compact_teacher_schedule")
    if weight == 0:
        return 0.0
    total_days = 0
    total_teachers = 0
    for teacher in data.teachers:
        work_days = set(
            d for (_, d, _), (_, t) in schedule.items() if t == teacher.id
        )
        if work_days:
            total_days += len(work_days)
            total_teachers += 1
    if total_teachers == 0:
        return weight
    avg_days = total_days / total_teachers
    return weight * max(0.0, 1.0 - (avg_days - 1) / 4)


def soft_avoid_single_lessons(schedule: Schedule, data: SchoolData) -> float:
    """Avoid days where a teacher has only 1 lesson."""
    weight = _get_weight(data, "avoid_single_lessons")
    if weight == 0:
        return 0.0
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
    return weight * (1.0 - singles / work_days_total)


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
    ("avoid_slot0", soft_avoid_slot0),
    ("no_student_gaps", soft_no_student_gaps),
    ("early_finish", soft_early_finish),
    ("demanding_early", soft_demanding_early),
    ("no_teacher_gaps", soft_no_teacher_gaps),
    ("compact_teacher_schedule", soft_compact_teacher_schedule),
    ("avoid_single_lessons", soft_avoid_single_lessons),
]


def evaluate_schedule(schedule: Schedule, data: SchoolData) -> dict:
    """Evaluate a schedule against all constraints.

    Single scoring function used by both GA (fitness) and CP-SAT (post-solve).
    Weights come from data.rules.optimization (zasady.md).

    Returns:
        hard_total: sum of hard scores (+100 each OK, -1000*N if violated)
        soft_total: sum of weighted soft scores (higher = better)
        total: hard_total + soft_total
        details: list of (name, type, score)
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
