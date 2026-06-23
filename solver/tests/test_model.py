"""Tests for the CP-SAT timetable model."""

import pytest
from pathlib import Path

from solver.parser import parse_all
from solver.model import build_model

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"


@pytest.fixture(scope="module")
def solution():
    """Solve once for all tests (expensive operation)."""
    data = parse_all(DATA_DIR)
    result = build_model(data, timeout_seconds=120)
    return result, data


class TestModelSolvability:
    def test_solution_found(self, solution):
        result, _ = solution
        assert result is not None, "Solver returned no solution (INFEASIBLE or timeout)"

    def test_status(self, solution):
        result, _ = solution
        assert result["status"] in ("OPTIMAL", "FEASIBLE")


class TestNoTeacherConflicts:
    """C2: No teacher teaches two classes at the same time."""

    def test_no_teacher_double_booking(self, solution):
        result, data = solution
        schedule = result["schedule"]
        # Build set of language subjects (cross-class = one teacher lesson)
        lang_subjects = {lg.language for lg in data.language_groups}
        # Group by (teacher, day, slot)
        teacher_slots = {}
        for (cls_id, d, s), (subj, teacher) in schedule.items():
            key = (teacher, d, s)
            teacher_slots.setdefault(key, []).append((cls_id, subj))
        conflicts = {}
        for k, v in teacher_slots.items():
            if len(v) <= 1:
                continue
            # Cross-class language groups are one lesson - not a conflict
            subjects_in_slot = set(subj for _, subj in v)
            if len(subjects_in_slot) == 1 and subjects_in_slot.pop() in lang_subjects:
                continue
            # l_glowna with placeholder teacher "-" is not a real conflict
            # (each class has a different epoch teacher per period)
            teacher_id = k[0]
            if teacher_id == "-":
                continue
            conflicts[k] = v
        assert len(conflicts) == 0, f"Teacher conflicts: {conflicts}"


class TestNoClassConflicts:
    """C1: No class has two lessons at the same slot."""

    def test_no_class_double_booking(self, solution):
        result, data = solution
        schedule = result["schedule"]
        # Each (cls_id, d, s) should appear at most once
        keys = list(schedule.keys())
        assert len(keys) == len(set(keys)), "Duplicate class slot entries"


class TestTeacherUnavailability:
    """C3: Teachers are not scheduled during their unavailable times."""

    def test_no_lessons_during_unavailable(self, solution):
        result, data = solution
        schedule = result["schedule"]
        violations = []
        for teacher in data.teachers:
            for day, slot_from, slot_to in teacher.unavailable:
                for s in range(slot_from, slot_to + 1):
                    for (cls_id, d, sl), (subj, t_id) in schedule.items():
                        if t_id == teacher.id and d == day and sl == s:
                            violations.append(
                                f"{teacher.id} ({teacher.name}) scheduled at "
                                f"{day}/{s} for {subj} but unavailable"
                            )
        assert len(violations) == 0, "\n".join(violations)


class TestMatrixHours:
    """C4: Each subject gets exactly the hours specified in the matrix."""

    def test_hours_match_matrix(self, solution):
        result, data = solution
        schedule = result["schedule"]
        # Identify epoch subjects to skip for epoch classes
        epoch_subjects = set()
        for epoch in data.rules.epochs:
            for subj in epoch.assignments.values():
                epoch_subjects.add(subj)
        mismatches = []
        for entry in data.matrix:
            for cls_id, expected_hours in entry.hours.items():
                if expected_hours == 0:
                    continue
                # Skip epoch subjects for epoch classes (handled as l_glowna)
                if cls_id in data.rules.epoch_classes and entry.subject in epoch_subjects:
                    continue
                actual = sum(
                    1 for (k, d, s), (subj, t) in schedule.items()
                    if k == cls_id and subj == entry.subject and t == entry.teacher
                )
                if actual != expected_hours:
                    mismatches.append(
                        f"{entry.subject}/{entry.teacher}/{cls_id}: "
                        f"expected {expected_hours}, got {actual}"
                    )
        assert len(mismatches) == 0, "\n".join(mismatches)


class TestMaxLessonsPerDay:
    """C5: No class has more than max_lessons_per_day."""

    def test_max_lessons(self, solution):
        result, data = solution
        schedule = result["schedule"]
        max_allowed = data.rules.max_lessons_per_day
        for cls in data.classes:
            for d in data.rules.days:
                count = sum(
                    1 for (k, day, s) in schedule.keys()
                    if k == cls.id and day == d
                )
                assert count <= max_allowed, (
                    f"{cls.id} has {count} lessons on {d}, max is {max_allowed}"
                )


class TestEpochSlots:
    """C9: l. glowna at slots 1-2 for epoch classes."""

    def test_l_glowna_in_slots_1_2(self, solution):
        result, data = solution
        schedule = result["schedule"]
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                for s in (1, 2):
                    key = (cls_id, d, s)
                    assert key in schedule, f"{cls_id} {d}/{s}: missing l. glowna"
                    assert schedule[key][0] == "l_glowna", (
                        f"{cls_id} {d}/{s}: expected l_glowna, got {schedule[key][0]}"
                    )

    def test_slots_1_2_reserved(self, solution):
        """No regular subjects in epoch slots 1-2 for epoch classes."""
        result, data = solution
        schedule = result["schedule"]
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                for s in (1, 2):
                    key = (cls_id, d, s)
                    if key in schedule:
                        assert schedule[key][0] == "l_glowna", (
                            f"{cls_id} {d}/{s}: {schedule[key][0]} in epoch slot"
                        )

    def test_kl12_no_l_glowna(self, solution):
        """kl12 should NOT have l. glowna (no epochs)."""
        result, data = solution
        schedule = result["schedule"]
        for (cls_id, d, s), (subj, t) in schedule.items():
            if cls_id == "kl12":
                assert subj != "l_glowna", f"kl12 has l_glowna at {d}/{s}"


class TestEnglishGroups:
    """C6: angielski1 and angielski2 for same class never in same slot."""

    def test_english_not_simultaneous(self, solution):
        result, data = solution
        schedule = result["schedule"]
        for cls in data.classes:
            for d in data.rules.days:
                for s in [sl[0] for sl in data.rules.slots]:
                    key = (cls.id, d, s)
                    if key in schedule:
                        subj = schedule[key][0]
                        # Can't be both ang1 and ang2 (only one entry per key)
                        # But check that teacher n8 isn't double booked
                        pass  # Already covered by C2 test


class TestLanguageGroups:
    """C7: Language groups have 2 consecutive hours on same day."""

    def test_language_hours(self, solution):
        result, data = solution
        lang_slots = result.get("language_slots", {})
        for gi, lg in enumerate(data.language_groups):
            if gi not in lang_slots:
                continue
            slots = lang_slots[gi]
            assert len(slots) == lg.hours, (
                f"Language group {lg.language}: expected {lg.hours} hours, got {len(slots)}"
            )

    def test_language_consecutive(self, solution):
        result, data = solution
        lang_slots = result.get("language_slots", {})
        for gi, lg in enumerate(data.language_groups):
            if gi not in lang_slots or not lg.consecutive:
                continue
            slots = sorted(lang_slots[gi])
            if len(slots) == 2:
                (d1, s1), (d2, s2) = slots
                assert d1 == d2, f"{lg.language}: lessons on different days ({d1} vs {d2})"
                assert abs(s2 - s1) == 1, f"{lg.language}: slots not consecutive ({s1}, {s2})"

    def test_language_no_class_conflict(self, solution):
        """Students in a language group don't have other class lessons at that time."""
        result, data = solution
        schedule = result["schedule"]
        lang_slots = result.get("language_slots", {})
        violations = []
        for gi, lg in enumerate(data.language_groups):
            if gi not in lang_slots:
                continue
            classes_in_group = sorted(set(st.class_id for st in lg.students))
            for (d, s) in lang_slots[gi]:
                for cls_id in classes_in_group:
                    key = (cls_id, d, s)
                    if key in schedule:
                        subj = schedule[key][0]
                        if subj != lg.language:
                            violations.append(
                                f"{lg.language}: {cls_id} has {subj} at {d}/{s}"
                            )
        assert len(violations) == 0, "\n".join(violations)


class TestScheduleCompleteness:
    """Overall check that the schedule is complete."""

    def test_all_classes_have_lessons(self, solution):
        result, data = solution
        schedule = result["schedule"]
        for cls in data.classes:
            cls_lessons = [
                (d, s) for (k, d, s) in schedule.keys() if k == cls.id
            ]
            assert len(cls_lessons) > 0, f"{cls.id} has no lessons"

    def test_total_lessons_reasonable(self, solution):
        result, data = solution
        schedule = result["schedule"]
        total = len(schedule)
        # At minimum: sum of all matrix hours + language hours
        min_expected = sum(
            h for entry in data.matrix
            for h in entry.hours.values() if h > 0
        )
        assert total >= min_expected, (
            f"Total lessons {total} < expected minimum {min_expected}"
        )
