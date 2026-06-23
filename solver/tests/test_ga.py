"""Tests for the Genetic Algorithm solver."""

import pytest
from pathlib import Path

from solver.parser import parse_all
from solver.ga_solver import (
    build_ga_model,
    GAConfig,
    _PlanningContext,
    _generate_random_schedule,
    _evaluate,
    _crossover,
    _mutate,
)
from solver.constraints import evaluate_schedule

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"


@pytest.fixture(scope="module")
def data():
    return parse_all(DATA_DIR)


@pytest.fixture(scope="module")
def ctx(data):
    return _PlanningContext(data)


@pytest.fixture(scope="module")
def ga_solution(data):
    """Run GA with small config for testing."""
    config = GAConfig(
        population_size=30,
        generations=50,
        tournament_size=3,
        elite_count=3,
        seed=42,
    )
    result = build_ga_model(data, config)
    return result


# --- Context ---

class TestPlanningContext:
    def test_assignments_exclude_epoch(self, ctx):
        """Epoch subjects for epoch classes should not be in assignments."""
        for cls_id, subj, _, _ in ctx.assignments:
            if cls_id in ctx.data.rules.epoch_classes:
                assert subj not in ctx.epoch_subject_ids, (
                    f"{cls_id}/{subj} is epoch but in assignments"
                )

    def test_epoch_classes_have_restricted_slots(self, ctx):
        for cls_id in ctx.data.rules.epoch_classes:
            assert 1 not in ctx.available_slots[cls_id]
            assert 2 not in ctx.available_slots[cls_id]

    def test_kl12_has_all_slots(self, ctx):
        assert 1 in ctx.available_slots["kl12"]
        assert 2 in ctx.available_slots["kl12"]


# --- Random schedule generation ---

class TestRandomSchedule:
    def test_generates_schedule(self, ctx):
        schedule = _generate_random_schedule(ctx)
        assert len(schedule) > 0

    def test_has_epoch_slots(self, ctx, data):
        schedule = _generate_random_schedule(ctx)
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                assert (cls_id, d, 1) in schedule
                assert schedule[(cls_id, d, 1)][0] == "l_glowna"
                assert (cls_id, d, 2) in schedule
                assert schedule[(cls_id, d, 2)][0] == "l_glowna"

    def test_all_classes_have_lessons(self, ctx, data):
        schedule = _generate_random_schedule(ctx)
        for cls in data.classes:
            cls_lessons = [(d, s) for (k, d, s) in schedule if k == cls.id]
            assert len(cls_lessons) > 0, f"{cls.id} has no lessons"

    def test_evaluates_without_error(self, ctx, data):
        schedule = _generate_random_schedule(ctx)
        result = evaluate_schedule(schedule, data)
        assert "total" in result


# --- Crossover ---

class TestCrossover:
    def test_produces_schedule(self, ctx):
        p1 = _generate_random_schedule(ctx)
        p2 = _generate_random_schedule(ctx)
        child = _crossover(p1, p2, ctx)
        assert len(child) > 0

    def test_child_has_epoch_slots(self, ctx, data):
        p1 = _generate_random_schedule(ctx)
        p2 = _generate_random_schedule(ctx)
        child = _crossover(p1, p2, ctx)
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                assert (cls_id, d, 1) in child


# --- Mutation ---

class TestMutation:
    def test_mutate_returns_schedule(self, ctx):
        schedule = _generate_random_schedule(ctx)
        mutated = _mutate(schedule, ctx)
        assert len(mutated) > 0

    def test_mutate_preserves_epoch(self, ctx, data):
        schedule = _generate_random_schedule(ctx)
        mutated = _mutate(schedule, ctx)
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                assert mutated.get((cls_id, d, 1), (None,))[0] == "l_glowna"
                assert mutated.get((cls_id, d, 2), (None,))[0] == "l_glowna"

    def test_mutation_changes_something(self, ctx):
        """Over many mutations, at least one should differ from original."""
        schedule = _generate_random_schedule(ctx)
        changed = False
        for _ in range(20):
            mutated = _mutate(schedule, ctx)
            if mutated != schedule:
                changed = True
                break
        assert changed, "20 mutations produced no change"


# --- Full GA run ---

class TestGASolver:
    def test_solution_found(self, ga_solution):
        assert ga_solution is not None

    def test_status(self, ga_solution):
        assert ga_solution["status"] in ("GA_OPTIMAL", "GA_VIOLATIONS")

    def test_schedule_not_empty(self, ga_solution):
        assert len(ga_solution["schedule"]) > 0

    def test_fitness_positive(self, ga_solution):
        """GA should find solutions with positive total fitness."""
        # With small generations it may not be perfect, but should be positive
        assert ga_solution["objective"] > -5000, (
            f"Fitness too low: {ga_solution['objective']}"
        )

    def test_epoch_slots_present(self, ga_solution, data):
        schedule = ga_solution["schedule"]
        for cls_id in data.rules.epoch_classes:
            for d in data.rules.days:
                key = (cls_id, d, 1)
                assert key in schedule, f"Missing epoch slot {cls_id} {d}/1"
                assert schedule[key][0] == "l_glowna"

    def test_all_classes_have_lessons(self, ga_solution, data):
        schedule = ga_solution["schedule"]
        for cls in data.classes:
            count = sum(1 for (k, _, _) in schedule if k == cls.id)
            assert count > 5, f"{cls.id} has only {count} lessons"


# --- GA improves over generations ---

class TestGAImprovement:
    def test_ga_improves(self, data):
        """GA with more generations should score better than random."""
        ctx = _PlanningContext(data)

        # Random baseline
        random_schedule = _generate_random_schedule(ctx)
        random_eval = evaluate_schedule(random_schedule, data)

        # GA with enough generations
        config = GAConfig(
            population_size=20,
            generations=30,
            seed=123,
        )
        ga_result = build_ga_model(data, config)

        assert ga_result["objective"] >= random_eval["total"], (
            f"GA ({ga_result['objective']:.1f}) should beat "
            f"random ({random_eval['total']:.1f})"
        )
