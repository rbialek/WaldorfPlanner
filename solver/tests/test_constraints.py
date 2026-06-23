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
    soft_avoid_slot0,
    soft_no_student_gaps,
    soft_early_finish,
    soft_demanding_early,
    soft_no_teacher_gaps,
    soft_compact_teacher_schedule,
    soft_avoid_single_lessons,
    HARD_PENALTY,
    HARD_REWARD,
)

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"


@pytest.fixture(scope="module")
def data():
    return parse_all(DATA_DIR)


@pytest.fixture(scope="module")
def solved(data):
    result = build_model(data, timeout_seconds=120)
    assert result is not None
    return result["schedule"], data


# =============================================================================
# HARD CONSTRAINTS - valid solution returns +100
# =============================================================================

class TestHardOnValidSolution:
    def test_no_student_conflict(self, solved):
        schedule, data = solved
        assert hard_no_student_conflict(schedule, data) == HARD_REWARD

    def test_no_teacher_conflict(self, solved):
        schedule, data = solved
        assert hard_no_teacher_conflict(schedule, data) == HARD_REWARD

    def test_max_lessons_per_day(self, solved):
        schedule, data = solved
        assert hard_max_lessons_per_day(schedule, data) == HARD_REWARD

    def test_teacher_unavailable(self, solved):
        schedule, data = solved
        assert hard_teacher_unavailable(schedule, data) == HARD_REWARD

    def test_epoch_slots(self, solved):
        schedule, data = solved
        assert hard_epoch_slots(schedule, data) == HARD_REWARD


# =============================================================================
# HARD CONSTRAINTS - synthetic violations return negative
# =============================================================================

class TestHardDetectsViolations:
    def test_teacher_conflict_detected(self, data):
        bad = {
            ("kl9", "pn", 3): ("matematyka", "n1"),
            ("kl10", "pn", 3): ("fizyka", "n1"),
        }
        assert hard_no_teacher_conflict(bad, data) == HARD_PENALTY

    def test_max_lessons_exceeded(self, data):
        bad = {("kl9", "pn", s): ("matematyka", "n1") for s in range(10)}
        assert hard_max_lessons_per_day(bad, data) < 0

    def test_teacher_unavailable_detected(self, data):
        teacher_with_constraint = None
        for t in data.teachers:
            if t.unavailable:
                teacher_with_constraint = t
                break
        if teacher_with_constraint is None:
            pytest.skip("No teachers with unavailability constraints")
        day, sf, _ = teacher_with_constraint.unavailable[0]
        bad = {("kl9", day, sf): ("biologia", teacher_with_constraint.id)}
        assert hard_teacher_unavailable(bad, data) == HARD_PENALTY

    def test_epoch_missing_detected(self, data):
        bad = {("kl9", "pn", 1): ("matematyka", "n1")}
        assert hard_epoch_slots(bad, data) < 0

    def test_epoch_correct(self, data):
        good = {}
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                for s in (1, 2):
                    good[(cls_id, d, s)] = ("l_glowna", "-")
        assert hard_epoch_slots(good, data) == HARD_REWARD


# =============================================================================
# SOFT CONSTRAINTS - valid solution returns positive, capped at weight
# =============================================================================

class TestSoftOnValidSolution:
    def test_avoid_slot0(self, solved):
        schedule, data = solved
        score = soft_avoid_slot0(schedule, data)
        assert 0 < score <= 100

    def test_no_student_gaps(self, solved):
        schedule, data = solved
        score = soft_no_student_gaps(schedule, data)
        assert 0 < score <= 50

    def test_early_finish(self, solved):
        schedule, data = solved
        score = soft_early_finish(schedule, data)
        assert 0 < score <= 30

    def test_demanding_early(self, solved):
        schedule, data = solved
        score = soft_demanding_early(schedule, data)
        assert 0 < score <= 25

    def test_no_teacher_gaps(self, solved):
        schedule, data = solved
        score = soft_no_teacher_gaps(schedule, data)
        assert 0 < score <= 20

    def test_compact_teacher_schedule(self, solved):
        schedule, data = solved
        score = soft_compact_teacher_schedule(schedule, data)
        assert 0 <= score <= 10

    def test_avoid_single_lessons(self, solved):
        schedule, data = solved
        score = soft_avoid_single_lessons(schedule, data)
        assert 0 < score <= 5


# =============================================================================
# SOFT CONSTRAINTS - synthetic best/worst cases
# =============================================================================

class TestSoftEdgeCases:
    def test_no_slot0_gives_max(self, data):
        good = {(c.id, "pn", 3): ("matematyka", "n1") for c in data.classes}
        assert soft_avoid_slot0(good, data) == 100

    def test_all_slot0_gives_near_zero(self, data):
        bad = {}
        for cls in data.classes:
            for d in data.rules.days:
                bad[(cls.id, d, 0)] = ("matematyka", "n1")
                if cls.id in data.rules.epoch_classes:
                    for s in (1, 2):
                        bad[(cls.id, d, s)] = ("l_glowna", "-")
        assert soft_avoid_slot0(bad, data) < 10

    def test_no_gaps_gives_max(self, data):
        good = {}
        for cls in data.classes:
            for d in data.rules.days:
                for s in range(1, 5):
                    good[(cls.id, d, s)] = ("matematyka", "n1")
        assert soft_no_student_gaps(good, data) == 50


# =============================================================================
# FULL EVALUATION
# =============================================================================

class TestEvaluation:
    def test_valid_solution_positive_total(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert result["hard_total"] > 0
        assert result["soft_total"] > 0
        assert result["total"] > 0

    def test_hard_total_500(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert result["hard_total"] == 500  # 5 * HARD_REWARD

    def test_soft_max_240(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert 0 < result["soft_total"] <= 240

    def test_details_count(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        assert len(result["details"]) == 12  # 5 hard + 7 soft

    def test_all_soft_ids_present(self, solved):
        schedule, data = solved
        result = evaluate_schedule(schedule, data)
        names = [name for name, _, _ in result["details"]]
        assert "avoid_slot0" in names
        assert "no_student_gaps" in names
        assert "compact_teacher_schedule" in names
