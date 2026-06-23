"""Genetic Algorithm solver for school timetable optimization.

Uses constraint functions from constraints.py as fitness evaluation.
"""

import random
import copy
from dataclasses import dataclass, field

from .data_model import SchoolData
from .constraints import evaluate_schedule, Schedule


@dataclass
class GAConfig:
    population_size: int = 100
    generations: int = 200
    tournament_size: int = 5
    crossover_rate: float = 0.8
    mutation_rate: float = 0.3
    elite_count: int = 5
    seed: int | None = None


@dataclass
class Individual:
    schedule: Schedule
    fitness: float = 0.0
    hard_violations: float = 0.0


def build_ga_model(data: SchoolData, config: GAConfig | None = None) -> dict | None:
    """Run GA to find optimal timetable.

    Returns same format as model.build_model() for compatibility.
    """
    if config is None:
        config = GAConfig()
    if config.seed is not None:
        random.seed(config.seed)

    ctx = _PlanningContext(data)

    # Initialize population
    population = []
    for _ in range(config.population_size):
        schedule = _generate_random_schedule(ctx)
        ind = _evaluate(schedule, data)
        population.append(ind)

    best_ever = max(population, key=lambda x: x.fitness)
    stagnation = 0

    for gen in range(config.generations):
        new_pop = []

        # Elitism: keep best individuals
        population.sort(key=lambda x: x.fitness, reverse=True)
        for i in range(config.elite_count):
            new_pop.append(population[i])

        # Fill rest with crossover + mutation
        while len(new_pop) < config.population_size:
            p1 = _tournament_select(population, config.tournament_size)
            p2 = _tournament_select(population, config.tournament_size)

            if random.random() < config.crossover_rate:
                child_sched = _crossover(p1.schedule, p2.schedule, ctx)
            else:
                child_sched = copy.deepcopy(p1.schedule)

            if random.random() < config.mutation_rate:
                child_sched = _mutate(child_sched, ctx)

            child = _evaluate(child_sched, data)
            new_pop.append(child)

        population = new_pop
        current_best = max(population, key=lambda x: x.fitness)

        if current_best.fitness > best_ever.fitness:
            best_ever = copy.deepcopy(current_best)
            stagnation = 0
        else:
            stagnation += 1

        # Adaptive mutation: increase if stagnating
        if stagnation > 20:
            config.mutation_rate = min(0.9, config.mutation_rate + 0.05)
        elif stagnation == 0:
            config.mutation_rate = max(0.1, config.mutation_rate - 0.02)

        if gen % 20 == 0 or gen == config.generations - 1:
            print(
                f"  Gen {gen:4d}: best={best_ever.fitness:.1f} "
                f"(hard={best_ever.hard_violations:.0f}) "
                f"avg={sum(i.fitness for i in population)/len(population):.1f} "
                f"mut={config.mutation_rate:.2f}"
            )

    if best_ever.hard_violations < 0:
        print(f"  WARNING: best solution has hard violations: {best_ever.hard_violations}")

    return {
        "schedule": best_ever.schedule,
        "language_slots": _extract_language_slots(best_ever.schedule, data),
        "assignments": [],
        "status": "GA_OPTIMAL" if best_ever.hard_violations >= 0 else "GA_VIOLATIONS",
        "objective": best_ever.fitness,
    }


# =============================================================================
# Internal helpers
# =============================================================================

class _PlanningContext:
    """Precomputed data for fast schedule generation."""

    def __init__(self, data: SchoolData):
        self.data = data
        self.days = data.rules.days
        self.all_slots = sorted(s[0] for s in data.rules.slots)
        self.max_slot = max(self.all_slots)
        self.class_ids = [c.id for c in data.classes]

        # Epoch subjects
        self.epoch_subject_ids = set()
        for epoch in data.rules.epochs:
            for subj in epoch.assignments.values():
                self.epoch_subject_ids.add(subj)

        # Build assignments list (same logic as model.py)
        self.assignments = []  # (class_id, subject, teacher, hours)
        for entry in data.matrix:
            for cls_id, hours in entry.hours.items():
                if hours > 0:
                    if cls_id in data.rules.epoch_classes and entry.subject in self.epoch_subject_ids:
                        continue
                    self.assignments.append((cls_id, entry.subject, entry.teacher, hours))

        # Group assignments by class
        self.class_assignments: dict[str, list[tuple[str, str, int]]] = {}
        for cls_id, subj, teacher, hours in self.assignments:
            self.class_assignments.setdefault(cls_id, []).append((subj, teacher, hours))

        # Language groups
        self.lang_groups = data.language_groups
        self.lang_class_map: dict[str, set[str]] = {}
        for lg in self.lang_groups:
            classes = set(st.class_id for st in lg.students)
            self.lang_class_map[lg.language] = classes

        # Teacher unavailability as set for fast lookup
        self.unavail: set[tuple[str, str, int]] = set()
        for t in data.teachers:
            for day, sf, st in t.unavailable:
                for s in range(sf, st + 1):
                    self.unavail.add((t.id, day, s))

        # Slots available per class per day (excluding epoch slots 1-2)
        self.available_slots: dict[str, list[int]] = {}
        for cls_id in self.class_ids:
            if cls_id in data.rules.epoch_classes:
                self.available_slots[cls_id] = [s for s in self.all_slots if s not in (1, 2)]
            else:
                self.available_slots[cls_id] = list(self.all_slots)


def _evaluate(schedule: Schedule, data: SchoolData) -> Individual:
    result = evaluate_schedule(schedule, data)
    return Individual(
        schedule=schedule,
        fitness=result["total"],
        hard_violations=result["hard_total"],
    )


def _generate_random_schedule(ctx: _PlanningContext) -> Schedule:
    """Generate a random schedule trying to respect hard constraints."""
    schedule: Schedule = {}
    teacher_used: set[tuple[str, str, int]] = set()  # (teacher, day, slot)
    class_used: set[tuple[str, str, int]] = set()  # (class, day, slot)

    # Place epoch slots first (fixed)
    for cls_id in ctx.data.rules.epoch_classes:
        for d in ctx.days:
            for s in (1, 2):
                schedule[(cls_id, d, s)] = ("l_glowna", "-")
                class_used.add((cls_id, d, s))

    # Place language groups (2 consecutive hours, same day for all classes in group)
    for lg in ctx.lang_groups:
        classes_in_group = sorted(ctx.lang_class_map.get(lg.language, set()))
        placed = False
        days_shuffled = list(ctx.days)
        random.shuffle(days_shuffled)

        for d in days_shuffled:
            if placed:
                break
            # Find consecutive slot pair available for all classes in group AND teacher
            available_starts = []
            for s in ctx.all_slots:
                if s + 1 > ctx.max_slot:
                    continue
                ok = True
                for cls_id in classes_in_group:
                    if (cls_id, d, s) in class_used or (cls_id, d, s + 1) in class_used:
                        ok = False
                        break
                if lg.teacher:
                    if (lg.teacher, d, s) in teacher_used or (lg.teacher, d, s + 1) in teacher_used:
                        ok = False
                    if (lg.teacher, d, s) in ctx.unavail or (lg.teacher, d, s + 1) in ctx.unavail:
                        ok = False
                if ok:
                    available_starts.append(s)

            if available_starts:
                s = random.choice(available_starts)
                for cls_id in classes_in_group:
                    schedule[(cls_id, d, s)] = (lg.language, lg.teacher)
                    schedule[(cls_id, d, s + 1)] = (lg.language, lg.teacher)
                    class_used.add((cls_id, d, s))
                    class_used.add((cls_id, d, s + 1))
                if lg.teacher:
                    teacher_used.add((lg.teacher, d, s))
                    teacher_used.add((lg.teacher, d, s + 1))
                placed = True

        if not placed:
            # Force place even with conflicts
            d = random.choice(ctx.days)
            s = random.choice([sl for sl in ctx.all_slots if sl + 1 <= ctx.max_slot])
            for cls_id in classes_in_group:
                schedule[(cls_id, d, s)] = (lg.language, lg.teacher)
                schedule[(cls_id, d, s + 1)] = (lg.language, lg.teacher)

    # Place regular assignments per class
    for cls_id, assignments in ctx.class_assignments.items():
        for subj, teacher, hours in assignments:
            slots_needed = hours
            placed = 0
            attempts = 0
            max_attempts = slots_needed * 50

            while placed < slots_needed and attempts < max_attempts:
                attempts += 1
                d = random.choice(ctx.days)
                avail = ctx.available_slots[cls_id]
                s = random.choice(avail)

                if (cls_id, d, s) in class_used:
                    continue
                if (teacher, d, s) in teacher_used:
                    continue
                if (teacher, d, s) in ctx.unavail:
                    continue

                schedule[(cls_id, d, s)] = (subj, teacher)
                class_used.add((cls_id, d, s))
                teacher_used.add((teacher, d, s))
                placed += 1

            # If couldn't place all, force remaining
            while placed < slots_needed:
                d = random.choice(ctx.days)
                s = random.choice(ctx.available_slots[cls_id])
                if (cls_id, d, s) not in class_used:
                    schedule[(cls_id, d, s)] = (subj, teacher)
                    class_used.add((cls_id, d, s))
                    placed += 1

    return schedule


def _tournament_select(population: list[Individual], k: int) -> Individual:
    candidates = random.sample(population, min(k, len(population)))
    return max(candidates, key=lambda x: x.fitness)


def _crossover(p1: Schedule, p2: Schedule, ctx: _PlanningContext) -> Schedule:
    """Day-based crossover: for each class, randomly pick days from p1 or p2."""
    child: Schedule = {}
    for cls_id in ctx.class_ids:
        for d in ctx.days:
            source = p1 if random.random() < 0.5 else p2
            for s in ctx.all_slots:
                key = (cls_id, d, s)
                if key in source:
                    child[key] = source[key]
    return child


def _mutate(schedule: Schedule, ctx: _PlanningContext) -> Schedule:
    """Mutation: swap two lessons within a class's day, or move a lesson to empty slot."""
    schedule = copy.deepcopy(schedule)

    cls_id = random.choice(ctx.class_ids)
    d = random.choice(ctx.days)

    # Get all lessons this class has on this day
    day_lessons = []
    day_empty = []
    for s in ctx.all_slots:
        key = (cls_id, d, s)
        if key in schedule:
            subj, teacher = schedule[key]
            if subj != "l_glowna":  # Don't touch epoch slots
                day_lessons.append((s, subj, teacher))
        else:
            # Check if slot is available (not epoch reserved)
            if cls_id in ctx.data.rules.epoch_classes and s in (1, 2):
                continue
            day_empty.append(s)

    if not day_lessons:
        return schedule

    mutation_type = random.choice(["swap", "move", "swap_days"])

    if mutation_type == "swap" and len(day_lessons) >= 2:
        # Swap two lessons in the day
        i, j = random.sample(range(len(day_lessons)), 2)
        s_i, subj_i, t_i = day_lessons[i]
        s_j, subj_j, t_j = day_lessons[j]
        schedule[(cls_id, d, s_i)] = (subj_j, t_j)
        schedule[(cls_id, d, s_j)] = (subj_i, t_i)

    elif mutation_type == "move" and day_empty:
        # Move a lesson to an empty slot
        idx = random.randrange(len(day_lessons))
        s_old, subj, teacher = day_lessons[idx]
        s_new = random.choice(day_empty)
        del schedule[(cls_id, d, s_old)]
        schedule[(cls_id, d, s_new)] = (subj, teacher)

    elif mutation_type == "swap_days":
        # Swap all lessons between two days for this class
        d2 = random.choice([x for x in ctx.days if x != d])
        lessons_d1 = {}
        lessons_d2 = {}
        for s in ctx.all_slots:
            k1 = (cls_id, d, s)
            k2 = (cls_id, d2, s)
            if k1 in schedule and schedule[k1][0] != "l_glowna":
                lessons_d1[s] = schedule.pop(k1)
            if k2 in schedule and schedule[k2][0] != "l_glowna":
                lessons_d2[s] = schedule.pop(k2)
        for s, val in lessons_d1.items():
            schedule[(cls_id, d2, s)] = val
        for s, val in lessons_d2.items():
            schedule[(cls_id, d, s)] = val

    return schedule


def _extract_language_slots(schedule: Schedule, data: SchoolData) -> dict:
    """Extract language group slots from schedule for compatibility."""
    lang_result = {}
    for gi, lg in enumerate(data.language_groups):
        slots = []
        for (cls_id, d, s), (subj, _) in schedule.items():
            if subj == lg.language:
                slot_key = (d, s)
                if slot_key not in slots:
                    slots.append(slot_key)
        if slots:
            lang_result[gi] = slots
    return lang_result
