"""CP-SAT model for school timetable optimization."""

from ortools.sat.python import cp_model

from .data_model import SchoolData


def build_model(data: SchoolData, timeout_seconds: int = 120) -> dict | None:
    """Build and solve the CP-SAT timetable model.

    Returns a dict mapping (class_id, day, slot) -> (subject, teacher)
    or None if infeasible.
    """
    model = cp_model.CpModel()

    days = data.rules.days
    all_slots = [s[0] for s in data.rules.slots]
    max_slot = max(all_slots)
    class_ids = [c.id for c in data.classes]
    teacher_map = {t.id: t for t in data.teachers}

    # --- Identify epoch subjects ---
    epoch_subject_ids = set()
    for epoch in data.rules.epochs:
        for cls_id, subj in epoch.assignments.items():
            epoch_subject_ids.add(subj)

    # --- Build lesson assignments from matrix ---
    # Exclude epoch subjects for epoch classes (they get fixed "l. glowna" slots 1-2)
    assignments = []  # (class_id, subject, teacher, hours)
    for entry in data.matrix:
        for cls_id, hours in entry.hours.items():
            if hours > 0:
                # Skip epoch subjects for epoch classes - handled separately
                if cls_id in data.rules.epoch_classes and entry.subject in epoch_subject_ids:
                    continue
                assignments.append((cls_id, entry.subject, entry.teacher, hours))

    # Add language group lessons (2h per group, consecutive)
    # Language groups are cross-class, so we create a "virtual" class slot per real class
    lang_class_slots = []  # (lang_group_idx, class_id, teacher, hours)
    for gi, lg in enumerate(data.language_groups):
        classes_in_group = sorted(set(s.class_id for s in lg.students))
        for cls_id in classes_in_group:
            lang_class_slots.append((gi, cls_id, lg.teacher, lg.hours))

    # --- Decision variables ---

    # lesson[k, d, s, idx] = 1 if assignment idx is placed at (k, d, s)
    lesson = {}
    for idx, (cls_id, subj, teacher, hours) in enumerate(assignments):
        for d in days:
            for s in all_slots:
                lesson[cls_id, d, s, idx] = model.new_bool_var(
                    f"lesson_{cls_id}_{d}_{s}_{subj}_{teacher}"
                )

    # lang_lesson[gi, d, s] = 1 if language group gi has lesson at (d, s)
    lang_lesson = {}
    for gi, lg in enumerate(data.language_groups):
        for d in days:
            for s in all_slots:
                lang_lesson[gi, d, s] = model.new_bool_var(
                    f"lang_{lg.language}_{d}_{s}"
                )

    # --- Hard constraints ---

    # C1: Each class has at most 1 lesson per slot (from assignments)
    for cls_id in class_ids:
        cls_assignment_indices = [
            idx for idx, (k, _, _, _) in enumerate(assignments) if k == cls_id
        ]
        for d in days:
            for s in all_slots:
                vars_in_slot = [lesson[cls_id, d, s, idx] for idx in cls_assignment_indices]
                # Also count language lessons occupying this class's slot
                lang_vars = []
                for gi, lg in enumerate(data.language_groups):
                    classes_in_group = set(st.class_id for st in lg.students)
                    if cls_id in classes_in_group:
                        lang_vars.append(lang_lesson[gi, d, s])
                model.add(sum(vars_in_slot) + sum(lang_vars) <= 1)

    # C2: Each teacher has at most 1 lesson per slot
    teacher_slots = {}  # teacher_id -> list of vars for each (d, s)
    for idx, (cls_id, subj, teacher, hours) in enumerate(assignments):
        teacher_slots.setdefault(teacher, {})
        for d in days:
            for s in all_slots:
                teacher_slots[teacher].setdefault((d, s), [])
                teacher_slots[teacher][(d, s)].append(lesson[cls_id, d, s, idx])

    # Add language lesson vars to teacher slots - ONCE per group (cross-class lesson)
    for gi, lg in enumerate(data.language_groups):
        if lg.teacher:
            teacher_slots.setdefault(lg.teacher, {})
            for d in days:
                for s in all_slots:
                    teacher_slots[lg.teacher].setdefault((d, s), [])
                    teacher_slots[lg.teacher][(d, s)].append(lang_lesson[gi, d, s])

    for teacher_id, ds_vars in teacher_slots.items():
        for (d, s), var_list in ds_vars.items():
            model.add(sum(var_list) <= 1)

    # C3: Teacher unavailability
    for teacher in data.teachers:
        for day, slot_from, slot_to in teacher.unavailable:
            if day not in days:
                continue
            for s in range(slot_from, slot_to + 1):
                if s not in all_slots:
                    continue
                for (d_key, s_key), var_list in teacher_slots.get(teacher.id, {}).items():
                    if d_key == day and s_key == s:
                        for v in var_list:
                            model.add(v == 0)

    # C4: Each assignment gets exactly the right number of hours
    for idx, (cls_id, subj, teacher, hours) in enumerate(assignments):
        total = []
        for d in days:
            for s in all_slots:
                total.append(lesson[cls_id, d, s, idx])
        model.add(sum(total) == hours)

    # C5: Max lessons per day per class
    # For epoch classes, 2 slots (l_glowna) are added post-solve, so limit is max - 2
    for cls_id in class_ids:
        cls_indices = [idx for idx, (k, _, _, _) in enumerate(assignments) if k == cls_id]
        epoch_reserve = 2 if cls_id in data.rules.epoch_classes else 0
        effective_max = data.rules.max_lessons_per_day - epoch_reserve
        for d in days:
            day_vars = []
            for s in all_slots:
                for idx in cls_indices:
                    day_vars.append(lesson[cls_id, d, s, idx])
                # Language lessons
                for gi, lg in enumerate(data.language_groups):
                    if cls_id in set(st.class_id for st in lg.students):
                        day_vars.append(lang_lesson[gi, d, s])
            model.add(sum(day_vars) <= effective_max)

    # C6: English groups - angielski1 and angielski2 for same class must be in different slots
    # (n8 teaches both, can't be simultaneous)
    for cls_id in class_ids:
        ang1_indices = [
            idx for idx, (k, subj, _, _) in enumerate(assignments)
            if k == cls_id and subj == "angielski1"
        ]
        ang2_indices = [
            idx for idx, (k, subj, _, _) in enumerate(assignments)
            if k == cls_id and subj == "angielski2"
        ]
        # This is already enforced by C2 (teacher can't be in 2 places)
        # But let's also explicitly prevent same slot
        for d in days:
            for s in all_slots:
                for i1 in ang1_indices:
                    for i2 in ang2_indices:
                        model.add(lesson[cls_id, d, s, i1] + lesson[cls_id, d, s, i2] <= 1)

    # C7: Language groups - 2 consecutive hours same day
    for gi, lg in enumerate(data.language_groups):
        # Total hours
        total_lang = []
        for d in days:
            for s in all_slots:
                total_lang.append(lang_lesson[gi, d, s])
        model.add(sum(total_lang) == lg.hours)

        if lg.consecutive and lg.hours == 2:
            # Must have exactly 2 hours on the same day, consecutive
            # day_has[d] = 1 if this language group has lessons on day d
            day_has = {}
            for d in days:
                day_has[d] = model.new_bool_var(f"lang_{gi}_day_{d}")
                day_sum = [lang_lesson[gi, d, s] for s in all_slots]
                # day_has[d] = 1 iff sum > 0
                model.add(sum(day_sum) >= 1).only_enforce_if(day_has[d])
                model.add(sum(day_sum) == 0).only_enforce_if(day_has[d].negated())

            # Exactly one day has lessons
            model.add(sum(day_has[d] for d in days) == 1)

            # On the active day, the 2 lessons must be consecutive
            for d in days:
                for s in all_slots:
                    if s + 1 <= max_slot:
                        # If lesson at s, next must be at s+1 (or this is the second of a pair)
                        pass  # Consecutive is ensured by: exactly 2 on one day
                # Stronger: the two slots must be adjacent
                # pair[d, s] = 1 if lessons are at s and s+1
                for s in all_slots:
                    if s + 1 in all_slots:
                        pair = model.new_bool_var(f"lang_{gi}_pair_{d}_{s}")
                        model.add(lang_lesson[gi, d, s] == 1).only_enforce_if(pair)
                        model.add(lang_lesson[gi, d, s + 1] == 1).only_enforce_if(pair)
                        model.add(
                            lang_lesson[gi, d, s] + lang_lesson[gi, d, s + 1] >= 2
                        ).only_enforce_if(pair)
                # All lessons on day d must form a consecutive block
                # For 2 hours: lesson[s] + lesson[s+1] = 2 for some s
                for s in all_slots:
                    if s + 1 in all_slots:
                        continue
                    # Last slot can't start a pair - if it's used, previous must be too
                    # This is handled by the "exactly 2 on one day + consecutive" logic

            # Simpler approach: for each day, if 2 lessons, they must be at s and s+1
            for d in days:
                for s in all_slots:
                    if s + 1 not in all_slots:
                        continue
                    # If lesson at s and NOT at s+1, then no lesson at s+2, s+3, ...
                    # Actually simpler: sum = 2 on a day means exists s: lesson[s]=1 AND lesson[s+1]=1
                    pass

            # Let me use a cleaner formulation:
            # consecutive_start[d, s] = 1 if the block starts at slot s on day d
            for d in days:
                starts = []
                for s in all_slots:
                    if s + 1 in all_slots:
                        start_var = model.new_bool_var(f"lang_{gi}_start_{d}_{s}")
                        # start_var => lesson at s and s+1
                        model.add(lang_lesson[gi, d, s] == 1).only_enforce_if(start_var)
                        model.add(lang_lesson[gi, d, s + 1] == 1).only_enforce_if(start_var)
                        starts.append(start_var)

                # If this day has lessons, exactly one start
                day_sum = sum(lang_lesson[gi, d, s] for s in all_slots)
                # day_has[d] => exactly one start
                if starts:
                    model.add(sum(starts) == 1).only_enforce_if(day_has[d])
                    model.add(sum(starts) == 0).only_enforce_if(day_has[d].negated())

    # C8: Cross-class groups for rozszerzenia
    # Students in extension groups from different classes can't have conflicting lessons
    # This is handled implicitly by teacher constraint (C2) since the same teacher
    # teaches the extension to all classes at the same time.
    # The matrix already defines per-class hours for extensions.

    # C9: Epoch "l. glowna" - slots 1-2 reserved for epoch classes
    # Epoch subjects are NOT in assignments (excluded above).
    # Slots 1 and 2 are completely reserved - no regular assignments there.
    for cls_id in data.rules.epoch_classes:
        cls_indices = [idx for idx, (k, _, _, _) in enumerate(assignments) if k == cls_id]
        for d in days:
            for s in (1, 2):
                # Block all regular assignments from slots 1-2
                for idx in cls_indices:
                    model.add(lesson[cls_id, d, s, idx] == 0)
                # Block language lessons from slots 1-2
                for gi, lg in enumerate(data.language_groups):
                    if cls_id in set(st.class_id for st in lg.students):
                        model.add(lang_lesson[gi, d, s] == 0)

    # CP-SAT only enforces hard constraints (feasibility).
    # Soft optimization is handled by evaluate_schedule() from constraints.py,
    # which is the single source of truth used by both GA and CP-SAT scoring.

    # --- Solve ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # --- Extract solution ---
    result = {}
    for idx, (cls_id, subj, teacher, hours) in enumerate(assignments):
        for d in days:
            for s in all_slots:
                if solver.value(lesson[cls_id, d, s, idx]):
                    result[cls_id, d, s] = (subj, teacher)

    # Add epoch "l. glowna" slots (fixed, not solved)
    for cls_id in data.rules.epoch_classes:
        for d in days:
            for s in (1, 2):
                result[cls_id, d, s] = ("l_glowna", "-")

    # Extract language group lessons
    lang_result = {}
    for gi, lg in enumerate(data.language_groups):
        for d in days:
            for s in all_slots:
                if solver.value(lang_lesson[gi, d, s]):
                    lang_result.setdefault(gi, []).append((d, s))
                    # Also mark in result for each class in this group
                    for cls_id in sorted(set(st.class_id for st in lg.students)):
                        result[cls_id, d, s] = (lg.language, lg.teacher)

    return {
        "schedule": result,
        "language_slots": lang_result,
        "assignments": assignments,
        "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        "objective": 0,  # No internal objective; use evaluate_schedule() for scoring
    }


    # _add_optimization removed: soft constraints are now handled exclusively
    # by constraints.py evaluate_schedule(), the single source of truth for
    # both GA and CP-SAT scoring.
