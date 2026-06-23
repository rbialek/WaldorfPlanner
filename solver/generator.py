"""Generate timetable .md files from solver solution."""

from pathlib import Path
from collections import defaultdict

from .data_model import SchoolData


DAY_NAMES = {
    "pn": "Poniedzialek",
    "wt": "Wtorek",
    "sr": "Sroda",
    "cz": "Czwartek",
    "pt": "Piatek",
}


def generate_all(data: SchoolData, solution: dict, output_dir: str | Path):
    """Generate all plan files from the solution."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    schedule = solution["schedule"]
    teacher_map = {t.id: t for t in data.teachers}
    subject_map = {s.id: s for s in data.subjects}
    slot_times = {nr: time for nr, time in data.rules.slots}

    # Identify epoch subjects
    epoch_subjects = set()
    for epoch in data.rules.epochs:
        for cls_id, subj in epoch.assignments.items():
            epoch_subjects.add(subj)

    # Student lookup by class
    class_students = {c.id: c.students for c in data.classes}

    # Generate class plans
    for cls in data.classes:
        _generate_class_plan(
            cls, data, schedule, teacher_map, slot_times,
            epoch_subjects, output_dir,
        )

    # Generate teacher plans
    for teacher in data.teachers:
        _generate_teacher_plan(
            teacher, data, schedule, class_students, slot_times,
            epoch_subjects, output_dir,
        )

    # Generate report
    _generate_report(data, solution, schedule, teacher_map, slot_times, output_dir)


def _generate_class_plan(
    cls, data, schedule, teacher_map, slot_times, epoch_subjects, output_dir,
):
    """Generate plany/klasa{N}.md"""
    class_num = cls.id.replace("kl", "")
    lines = [f"# Plan lekcji - Klasa {class_num} - Rok szkolny 2026/27\n"]
    lines.append(f"Liczba uczniow: {len(cls.students)}\n")

    # Weekly timetable
    lines.append("## Tygodniowy plan\n")
    if cls.id in data.rules.epoch_classes:
        lines.append("Uwaga: przedmioty epokowe oznaczone [EPOKA] zmieniaja sie wg planu epok (patrz zasady.md).\n")

    days = data.rules.days
    all_slots = sorted(set(s[0] for s in data.rules.slots))

    # Build header
    header = "|  | " + " | ".join(DAY_NAMES[d] for d in days) + " |"
    separator = "|--|" + "|".join("---" for _ in days) + "|"
    lines.append(header)
    lines.append(separator)

    for s in all_slots:
        time_str = slot_times.get(s, "")
        row = f"| {s} ({time_str}) |"
        for d in days:
            key = (cls.id, d, s)
            if key in schedule:
                subj, teacher = schedule[key]
                t_name = teacher_map.get(teacher)
                t_display = t_name.name.split()[-1] if t_name else teacher
                # Mark epoch subjects
                if subj in epoch_subjects and cls.id in data.rules.epoch_classes:
                    row += f" [EPOKA] ({teacher}) |"
                else:
                    row += f" {subj} ({t_display}) |"
            else:
                row += " - |"
        lines.append(row)

    # Epoch details
    if cls.id in data.rules.epoch_classes:
        lines.append("\n## Plan epok\n")
        lines.append("| Okres | Przedmiot |")
        lines.append("|-------|-----------|")
        for epoch in data.rules.epochs:
            subj = epoch.assignments.get(cls.id, "-")
            lines.append(f"| {epoch.period} | {subj} |")

    # English groups
    lines.append("\n## Grupy angielskiego\n")
    for group_name in ["angielski1", "angielski2"]:
        students = [s for s in cls.students if s.english_group == group_name]
        if students:
            # Find slot
            eng_slots = [
                (d, s) for (k, d, s), (subj, t) in schedule.items()
                if k == cls.id and subj == group_name
            ]
            slot_str = ", ".join(f"{d}/{s}" for d, s in sorted(eng_slots))
            names = ", ".join(s.name for s in students)
            lines.append(f"**{group_name}** ({len(students)} ucz., sloty: {slot_str}):")
            lines.append(f"  {names}\n")

    # Extension groups
    lines.append("## Rozszerzenia uczniow\n")
    ext_groups = defaultdict(list)
    for student in cls.students:
        for ext in student.extensions:
            ext_groups[ext].append(student.name)
    for ext_name in sorted(ext_groups.keys()):
        names = ", ".join(ext_groups[ext_name])
        lines.append(f"- **{ext_name}**: {names}")

    # Language groups
    lines.append("\n## Jezyki obce\n")
    lang_groups = defaultdict(list)
    for student in cls.students:
        if student.language and student.language != "ZW":
            lang_groups[student.language].append(student.name)
    for lang in sorted(lang_groups.keys()):
        names = ", ".join(lang_groups[lang])
        # Find slot for this language
        lang_slots = [
            (d, s) for (k, d, s), (subj, t) in schedule.items()
            if k == cls.id and subj == lang
        ]
        slot_str = ", ".join(f"{d}/{s}" for d, s in sorted(lang_slots))
        lines.append(f"- **{lang}** ({len(lang_groups[lang])} ucz., sloty: {slot_str}): {names}")

    # ZW students
    zw_students = [s for s in cls.students if s.language == "ZW"]
    if zw_students:
        names = ", ".join(s.name for s in zw_students)
        lines.append(f"- **ZW** (zwolnieni): {names}")

    content = "\n".join(lines) + "\n"
    filepath = output_dir / f"klasa{class_num}.md"
    filepath.write_text(content, encoding="utf-8")


def _generate_teacher_plan(
    teacher, data, schedule, class_students, slot_times, epoch_subjects, output_dir,
):
    """Generate plany/nX_Imie_Nazwisko.md"""
    name_parts = teacher.name.split()
    filename = f"{teacher.id}_{'_'.join(name_parts)}.md"

    lines = [f"# Plan lekcji - {teacher.name} ({teacher.id}) - Rok szkolny 2026/27\n"]
    lines.append(f"## Przedmioty: {', '.join(teacher.subjects)}")

    if teacher.unavailable:
        constraints = []
        for day, sf, st in teacher.unavailable:
            if sf == 0 and st == 9:
                constraints.append(f"{DAY_NAMES.get(day, day)} (caly dzien)")
            else:
                constraints.append(f"{DAY_NAMES.get(day, day)} sloty {sf}-{st}")
        lines.append(f"## Ograniczenia: {', '.join(constraints)}")
    else:
        lines.append("## Ograniczenia: brak")

    # Count total hours
    teacher_lessons = [
        (k, d, s, subj) for (k, d, s), (subj, t) in schedule.items()
        if t == teacher.id
    ]
    # Deduplicate cross-class language lessons
    lang_subjects = {lg.language for lg in data.language_groups}
    seen_lang_slots = set()
    unique_count = 0
    for k, d, s, subj in teacher_lessons:
        if subj in lang_subjects:
            slot_key = (subj, d, s)
            if slot_key not in seen_lang_slots:
                seen_lang_slots.add(slot_key)
                unique_count += 1
        else:
            unique_count += 1
    lines.append(f"## Laczna liczba godzin: {unique_count}h/tydzien\n")

    # Weekly timetable
    lines.append("## Tygodniowy plan\n")
    days = data.rules.days
    all_slots = sorted(set(s[0] for s in data.rules.slots))

    header = "|  | " + " | ".join(DAY_NAMES[d] for d in days) + " |"
    separator = "|--|" + "|".join("---" for _ in days) + "|"
    lines.append(header)
    lines.append(separator)

    for s in all_slots:
        time_str = slot_times.get(s, "")
        row = f"| {s} ({time_str}) |"
        for d in days:
            # Find what this teacher does at this slot
            entries = [
                (k, subj) for k, d2, s2, subj in teacher_lessons
                if d2 == d and s2 == s
            ]
            if entries:
                # Group cross-class language lessons
                subjects = set(subj for _, subj in entries)
                if len(subjects) == 1 and subjects.pop() in lang_subjects:
                    subj = entries[0][1]
                    classes = sorted(set(k for k, _ in entries))
                    row += f" {subj} ({'+'.join(classes)}) |"
                elif len(entries) == 1:
                    cls_id, subj = entries[0]
                    if subj in epoch_subjects and cls_id in data.rules.epoch_classes:
                        row += f" [EPOKA] {cls_id} |"
                    else:
                        row += f" {subj} {cls_id} |"
                else:
                    # Shouldn't happen (teacher conflict) - show all
                    parts = [f"{subj} {k}" for k, subj in entries]
                    row += f" {'|'.join(parts)} |"
            else:
                row += " - |"
        lines.append(row)

    # Lesson details
    lines.append("\n## Szczegoly lekcji\n")
    lines.append("| Dzien | Lekcja | Przedmiot | Klasa/Grupa | Uczniowie |")
    lines.append("|-------|--------|-----------|-------------|-----------|")

    seen_lang = set()
    for d in days:
        for s in all_slots:
            entries = [
                (k, subj) for k, d2, s2, subj in teacher_lessons
                if d2 == d and s2 == s
            ]
            for cls_id, subj in sorted(entries):
                # For language groups, show once with all students
                if subj in lang_subjects:
                    lang_key = (subj, d, s)
                    if lang_key in seen_lang:
                        continue
                    seen_lang.add(lang_key)
                    lg = next(
                        (g for g in data.language_groups if g.language == subj),
                        None,
                    )
                    if lg:
                        names = ", ".join(st.name for st in lg.students[:10])
                        if len(lg.students) > 10:
                            names += f" ... (+{len(lg.students)-10})"
                        lines.append(
                            f"| {d} | {s} | {subj} | grupa jezykowa | "
                            f"{names} ({len(lg.students)} ucz.) |"
                        )
                    continue

                # For english groups
                if subj in ("angielski1", "angielski2"):
                    students = [
                        st for st in class_students.get(cls_id, [])
                        if st.english_group == subj
                    ]
                    names = ", ".join(st.name for st in students)
                    lines.append(
                        f"| {d} | {s} | {subj} | {cls_id} | {names} ({len(students)} ucz.) |"
                    )
                    continue

                # Regular class subject
                student_count = len(class_students.get(cls_id, []))
                lines.append(
                    f"| {d} | {s} | {subj} | {cls_id} (cala klasa) | {student_count} ucz. |"
                )

    # Summary
    lines.append("\n## Podsumowanie\n")
    work_days = sorted(set(d for _, d, _, _ in teacher_lessons))
    lines.append(f"- Dni pracy: {', '.join(DAY_NAMES.get(d, d) for d in work_days)}")

    if teacher_lessons:
        slots_used = [s for _, _, s, _ in teacher_lessons]
        min_slot, max_slot = min(slots_used), max(slots_used)
        lines.append(f"- Godziny: lekcje {min_slot}-{max_slot}")

    # Count gaps
    gap_count = 0
    for d in work_days:
        day_slots = sorted(set(s for _, d2, s, _ in teacher_lessons if d2 == d))
        if len(day_slots) >= 2:
            for i in range(len(day_slots) - 1):
                gap = day_slots[i + 1] - day_slots[i] - 1
                gap_count += gap
    lines.append(f"- Okienka: {gap_count}")

    content = "\n".join(lines) + "\n"
    filepath = output_dir / filename
    filepath.write_text(content, encoding="utf-8")


def _generate_report(data, solution, schedule, teacher_map, slot_times, output_dir):
    """Generate plany/raport.md"""
    lines = ["# Raport planu lekcji - Rok szkolny 2026/27\n"]
    lines.append(f"Status solvera: {solution['status']}")
    lines.append(f"Wartosc funkcji celu: {solution.get('objective', 'N/A')}\n")

    # Slot 0 usage
    lines.append("## Uzycie lekcji 0 (7:25)\n")
    slot0_count = sum(1 for (k, d, s) in schedule if s == 0)
    lines.append(f"Laczne uzycie slotu 0: {slot0_count} lekcji\n")
    if slot0_count > 0:
        for (k, d, s), (subj, t) in sorted(schedule.items()):
            if s == 0:
                lines.append(f"- {k} {d}: {subj} ({t})")
    else:
        lines.append("Brak lekcji o 7:25 - optymalne!")

    # Student gaps
    lines.append("\n## Okienka uczniow\n")
    total_student_gaps = 0
    for cls in data.classes:
        for d in data.rules.days:
            cls_slots = sorted(
                s for (k, day, s) in schedule if k == cls.id and day == d
            )
            if len(cls_slots) >= 2:
                gaps = cls_slots[-1] - cls_slots[0] + 1 - len(cls_slots)
                total_student_gaps += gaps
                if gaps > 0:
                    lines.append(f"- {cls.id} {d}: {gaps} okienek (sloty {cls_slots})")
    if total_student_gaps == 0:
        lines.append("Brak okienek uczniow - optymalne!")
    else:
        lines.append(f"\nLaczna liczba okienek uczniow: {total_student_gaps}")

    # Teacher gaps and days
    lines.append("\n## Plan nauczycieli - podsumowanie\n")
    lines.append("| Nauczyciel | Godziny | Dni pracy | Okienka |")
    lines.append("|------------|---------|-----------|---------|")

    lang_subjects = {lg.language for lg in data.language_groups}
    for teacher in data.teachers:
        t_lessons = [
            (d, s) for (k, d, s), (subj, t) in schedule.items()
            if t == teacher.id
        ]
        # Deduplicate language slots
        seen = set()
        unique_lessons = []
        for d, s in t_lessons:
            key_check = None
            for (k, d2, s2), (subj, t) in schedule.items():
                if t == teacher.id and d2 == d and s2 == s:
                    if subj in lang_subjects:
                        key_check = (subj, d, s)
                    break
            if key_check:
                if key_check not in seen:
                    seen.add(key_check)
                    unique_lessons.append((d, s))
            else:
                unique_lessons.append((d, s))

        hours = len(unique_lessons)
        work_days = sorted(set(d for d, s in unique_lessons))
        gaps = 0
        for d in work_days:
            day_slots = sorted(s for d2, s in unique_lessons if d2 == d)
            if len(day_slots) >= 2:
                gaps += day_slots[-1] - day_slots[0] + 1 - len(day_slots)

        days_str = ", ".join(DAY_NAMES.get(d, d) for d in work_days)
        lines.append(f"| {teacher.name} ({teacher.id}) | {hours}h | {days_str} | {gaps} |")

    # Compromises
    lines.append("\n## Kompromisy\n")
    if slot0_count > 0:
        lines.append(f"- Uzyto lekcji 0 w {slot0_count} przypadkach")
    if total_student_gaps > 0:
        lines.append(f"- {total_student_gaps} okienek uczniow")
    if slot0_count == 0 and total_student_gaps == 0:
        lines.append("Brak kompromisow - plan optymalny!")

    content = "\n".join(lines) + "\n"
    filepath = output_dir / "raport.md"
    filepath.write_text(content, encoding="utf-8")
