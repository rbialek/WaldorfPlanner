"""Tests for constraint evaluation functions."""

import pytest
from pathlib import Path

from solver.parser import parse_all
from solver.model import build_model
from solver.constraints import (
    evaluate_schedule,
    hard_no_student_conflict,
    hard_no_teacher_conflict,
    hard_max_lessons_per_day,
    hard_teacher_unavailable,
    hard_epoch_slots,
    soft_unikaj_slot0,
    soft_brak_okienek_uczniow,
    soft_wczesne_konczenie,
    soft_trudne_wczesniej,
    soft_min_okienek_nauczycieli,
    soft_kompaktowy_plan,
    soft_unikaj_pojedynczych,
    HARD_PENALTY,
)

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"


@pytest.fixture(scope="module")
def solved():
    data = parse_all(DATA_DIR)
    result = build_model(data, timeout_seconds=120)
    assert result is not None
    return result["schedule"], data


@pytest.fixture(scope="module")
def data_only():
    return parse_all(DATA_DIR)


# =============================================================================
# HARD CONSTRAINTS - valid solution should return +100 (positive)
# =============================================================================

class TestHardOnValidSolution:
    def test_no_student_conflict_positive(self, solved):
        schedule, data = solved
        score = hard_no_student_conflict(schedule, data)
        assert score == 100, f"Expected +100, got {score}"

    def test_no_teacher_conflict_positive(self, solved):
        schedule, data = solved
        score = hard_no_teacher_conflict(schedule, data)
        assert score == 100, f"Expected +100, got {score}"

    def test_max_lessons_positive(self, solved):
        schedule, data = solved
        score = hard_max_lessons_per_day(schedule, data)
        assert score == 100, f"Expected +100, got {score}"

    def test_teacher_unavailable_positive(self, solved):
        schedule, data = solved
        score = hard_teacher_unavailable(schedule, data)
        assert score == 100, f"Expected +100, got {score}"

    def test_epoch_slots_positive(self, solved):
        schedule, data = solved
        score = hard_epoch_slots(schedule, data)
        assert score == 100, f"Expected +100, got {score}"


# =============================================================================
# HARD CONSTRAINTS - synthetic violations should return negative
# =============================================================================

class TestHardDetectsViolations:
    def test_teacher_conflict_negative(self, data_only):
        bad = {
            ("kl9", "pn", 3): ("matematyka", "n1"),
            ("kl10", "pn", 3): ("fizyka", "n1"),  # n1 double-booked
        }
        score = hard_no_teacher_conflict(bad, data_only)
        assert score == HARD_PENALTY, f"Expected {HARD_PENALTY}, got {score}"

    def test_max_lessons_exceeded_negative(self, data_only):
        bad = {("kl9", "pn", s): ("matematyka", "n1") for s in range(10)}
        score = hard_max_lessons_per_day(bad, data_only)
        assert score < 0, f"Expected negative, got {score}"

    def test_teacher_unavailable_negative(self, data_only):
        # Find a teacher with unavailability, if any
        teacher_with_constraint = None
        for t in data_only.teachers:
            if t.unavailable:
                teacher_with_constraint = t
                break
        if teacher_with_constraint is None:
            pytest.skip("No teachers with unavailability constraints")
        day, sf, st = teacher_with_constraint.unavailable[0]
        bad = {("kl9", day, sf): ("biologia", teacher_with_constraint.id)}
        score = hard_teacher_unavailable(bad, data_only)
        assert score == HARD_PENALTY, f"Expected {HARD_PENALTY}, got {score}"

    def test_epoch_missing_negative(self, data_only):
        # kl9 slot 1 Mon should be l_glowna
        bad = {("kl9", "pn", 1): ("matematyka", "n1")}
        score = hard_epoch_slots(bad, data_only)
        assert score < 0, f"Expected negative, got {score}"

    def test_epoch_correct_positive(self, data_only):
        # Build correct epoch schedule for all epoch classes
        good = {}
        for cls_id in data_only.rules.epoch_classes:
            for d in data_only.rules.days:
                for s in (1, 2):
                    good[(cls_id, d, s)] = ("l_glowna", "-")
        score = hard_epoch_slots(good, data_only)
        assert score == 100, f"Expected +100, got {score}"


# =============================================================================
# SOFT CONSTRAINTS - positive = good, closer to 0 = bad
# Valid solution should return positive weighted scores
# =============================================================================

class TestSoftPositive:
    """Valid solver solution should score positively on soft constraints."""

    def test_unikaj_slot0_positive(self, solved):
        schedule, data = solved
        score = soft_unikaj_slot0(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 100, f"Max is weight=100, got {score}"

    def test_brak_okienek_positive(self, solved):
        schedule, data = solved
        score = soft_brak_okienek_uczniow(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 50

    def test_wczesne_konczenie_positive(self, solved):
        schedule, data = solved
        score = soft_wczesne_konczenie(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 30

    def test_trudne_wczesniej_positive(self, solved):
        schedule, data = solved
        score = soft_trudne_wczesniej(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 25

    def test_min_okienek_positive(self, solved):
        schedule, data = solved
        score = soft_min_okienek_nauczycieli(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 20

    def test_kompaktowy_positive(self, solved):
        schedule, data = solved
        score = soft_kompaktowy_plan(schedule, data)
        assert score >= 0, f"Expected non-negative, got {score}"
        assert score <= 10

    def test_pojedyncze_positive(self, solved):
        schedule, data = solved
        score = soft_unikaj_pojedynczych(schedule, data)
        assert score > 0, f"Expected positive, got {score}"
        assert score <= 5


# =============================================================================
# SOFT CONSTRAINTS - synthetic worst case should return near 0
# =============================================================================

class TestSoftWorstCase:
    def test_slot0_all_used_near_zero(self, data_only):
        """If every class uses slot 0 every day, score should be near 0."""
        bad = {}
        for cls in data_only.classes:
            for d in data_only.rules.days:
                bad[(cls.id, d, 0)] = ("matematyka", "n1")
                # Need at least l_glowna for epoch classes
                if cls.id in data_only.rules.epoch_classes:
                    for s in (1, 2):
                        bad[(cls.id, d, s)] = ("l_glowna", "-")
        score = soft_unikaj_slot0(bad, data_only)
        assert score < 10, f"Expected near 0, got {score}"

    def test_no_slot0_perfect(self, data_only):
        """If no slot 0 used, score should be max weight (100)."""
        good = {}
        for cls in data_only.classes:
            for d in data_only.rules.days:
                good[(cls.id, d, 3)] = ("matematyka", "n1")
        score = soft_unikaj_slot0(good, data_only)
        assert score == 100, f"Expected 100, got {score}"

    def test_no_gaps_perfect(self, data_only):
        """Continuous lessons should give max score."""
        good = {}
        for cls in data_only.classes:
            for d in data_only.rules.days:
                for s in range(1, 5):
                    good[(cls.id, d, s)] = ("matematyka", "n1")
        score = soft_brak_okienek_uczniow(good, data_only)
        assert score == 50, f"Expected 50 (weight), got {score}"


# =============================================================================
# FULL EVALUATION
# =============================================================================

class TestEvaluation:
    def test_total_positive_for_valid(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert result["hard_total"] > 0, "Hard constraints should all pass"
        assert result["soft_total"] > 0, "Soft score should be positive"
        assert result["total"] > 0, "Total should be positive"

    def test_details_count(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        # 5 hard + 7 soft = 12
        assert len(result["details"]) == 12

    def test_hard_total_is_500_for_valid(self, solved):
        """5 hard constraints * +100 each = +500."""
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert result["hard_total"] == 500

    def test_soft_max_is_240(self, solved):
        """Max soft = 100+50+30+25+20+10+5 = 240."""
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert 0 < result["soft_total"] <= 240
