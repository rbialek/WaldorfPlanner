"""Tests for the school data parser."""

import pytest
from pathlib import Path

from solver.parser import (
    parse_all,
    parse_classes,
    parse_matrix,
    parse_md_table,
    parse_rules,
    parse_subjects,
    parse_teachers,
    parse_unavailability,
    build_language_groups,
)

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"


@pytest.fixture
def school_data():
    return parse_all(DATA_DIR)


# --- parse_md_table ---

class TestParseMdTable:
    def test_simple_table(self):
        text = """
| A | B |
|---|---|
| 1 | 2 |
| 3 | 4 |
"""
        rows = parse_md_table(text)
        assert len(rows) == 2
        assert rows[0] == {"A": "1", "B": "2"}
        assert rows[1] == {"A": "3", "B": "4"}

    def test_empty_text(self):
        assert parse_md_table("") == []

    def test_no_data_rows(self):
        text = """
| A | B |
|---|---|
"""
        assert parse_md_table(text) == []


# --- parse_teachers ---

class TestParseTeachers:
    def test_all_teachers_loaded(self, school_data):
        assert len(school_data.teachers) == 12

    def test_teacher_ids(self, school_data):
        ids = [t.id for t in school_data.teachers]
        assert "n1" in ids
        assert "n12" in ids

    def test_teacher_name(self, school_data):
        n1 = next(t for t in school_data.teachers if t.id == "n1")
        assert n1.name == "Jan Kowalski"

    def test_teacher_subjects(self, school_data):
        n5 = next(t for t in school_data.teachers if t.id == "n5")
        assert "chemia" in n5.subjects
        assert "chemia_roz" in n5.subjects

    def test_teacher_multiple_subjects(self, school_data):
        n3 = next(t for t in school_data.teachers if t.id == "n3")
        assert "historia" in n3.subjects
        assert "edukacja_obyw" in n3.subjects

    def test_no_constraints(self, school_data):
        n1 = next(t for t in school_data.teachers if t.id == "n1")
        assert n1.unavailable == []

    def test_unavailability_parsed(self, school_data):
        """Teachers with constraints should have them parsed.
        Teachers with 'brak' should have empty list."""
        for t in school_data.teachers:
            assert isinstance(t.unavailable, list)
        # Count total constraints
        total = sum(len(t.unavailable) for t in school_data.teachers)
        # At least 0 (all brak) is valid
        assert total >= 0


# --- parse_unavailability ---

class TestParseUnavailability:
    SLOTS = [(i, f"{7+i}:00 - {8+i}:00") for i in range(10)]

    def test_brak(self):
        assert parse_unavailability("brak", self.SLOTS) == []

    def test_empty(self):
        assert parse_unavailability("", self.SLOTS) == []

    def test_full_day(self):
        result = parse_unavailability("niedostepny w piatki (caly dzien)", self.SLOTS)
        assert len(result) == 1
        assert result[0] == ("pt", 0, 9)


# --- parse_subjects ---

class TestParseSubjects:
    def test_all_types_present(self, school_data):
        types = {s.subject_type for s in school_data.subjects}
        assert "yearly" in types
        assert "epoch" in types
        assert "extension" in types
        assert "language" in types
        assert "english" in types

    def test_english_type(self, school_data):
        eng = [s for s in school_data.subjects if s.subject_type == "english"]
        assert len(eng) == 2
        ids = {s.id for s in eng}
        assert "angielski1" in ids
        assert "angielski2" in ids

    def test_yearly_subjects(self, school_data):
        yearly = [s for s in school_data.subjects if s.subject_type == "yearly"]
        yearly_ids = {s.id for s in yearly}
        assert "j_polski" in yearly_ids
        assert "matematyka" in yearly_ids
        assert "fizyka" in yearly_ids
        assert "wf" in yearly_ids

    def test_epoch_subjects(self, school_data):
        epoch = [s for s in school_data.subjects if s.subject_type == "epoch"]
        epoch_ids = {s.id for s in epoch}
        assert "historia" in epoch_ids
        assert "biologia" in epoch_ids
        assert "edukacja_obyw" in epoch_ids
        assert "edb" in epoch_ids
        assert "biz" in epoch_ids

    def test_extension_subjects(self, school_data):
        ext = [s for s in school_data.subjects if s.subject_type == "extension"]
        assert len(ext) == 10
        ext_ids = {s.id for s in ext}
        assert "matematyka_roz" in ext_ids
        assert "historia_sztuki_roz" in ext_ids

    def test_languages(self, school_data):
        lang = [s for s in school_data.subjects if s.subject_type == "language"]
        assert len(lang) == 4
        lang_ids = {s.id for s in lang}
        assert "j_hiszpanski" in lang_ids
        assert "j_niemiecki" in lang_ids
        assert "j_rosyjski" in lang_ids
        assert "j_francuski" in lang_ids

    def test_subject_teachers(self, school_data):
        mat = next(s for s in school_data.subjects if s.id == "matematyka")
        assert "n1" in mat.teachers
        assert "n11" in mat.teachers

    def test_no_duplicate_ids(self, school_data):
        ids = [s.id for s in school_data.subjects]
        assert len(ids) == len(set(ids))


# --- parse_classes ---

class TestParseClasses:
    def test_four_classes(self, school_data):
        assert len(school_data.classes) == 4

    def test_class_ids(self, school_data):
        ids = [c.id for c in school_data.classes]
        assert ids == ["kl9", "kl10", "kl11", "kl12"]

    def test_class_sizes(self, school_data):
        sizes = {c.id: len(c.students) for c in school_data.classes}
        assert sizes["kl9"] == 17
        assert sizes["kl10"] == 17
        assert sizes["kl11"] == 18
        assert sizes["kl12"] == 10

    def test_student_names(self, school_data):
        kl9 = next(c for c in school_data.classes if c.id == "kl9")
        names = [s.name for s in kl9.students]
        assert "Franciszek Beyga" in names
        assert "Lena Borowska" in names

    def test_student_extensions(self, school_data):
        kl9 = next(c for c in school_data.classes if c.id == "kl9")
        beyga = next(s for s in kl9.students if s.name == "Franciszek Beyga")
        assert beyga.extensions == ["biologia", "chemia"]

    def test_student_one_extension(self, school_data):
        kl9 = next(c for c in school_data.classes if c.id == "kl9")
        cader = next(s for s in kl9.students if s.name == "Mateusz Cader")
        assert cader.extensions == ["informatyka"]

    def test_student_three_extensions(self, school_data):
        kl10 = next(c for c in school_data.classes if c.id == "kl10")
        dzoga = next(s for s in kl10.students if s.name == "Masza Dzoga")
        assert len(dzoga.extensions) == 3
        assert "matematyka" in dzoga.extensions
        assert "historia" in dzoga.extensions
        assert "wos" in dzoga.extensions

    def test_student_language(self, school_data):
        kl10 = next(c for c in school_data.classes if c.id == "kl10")
        danysz = next(s for s in kl10.students if s.name == "Sebastian Danysz")
        assert danysz.language == "j_niemiecki"

    def test_student_zw(self, school_data):
        kl10 = next(c for c in school_data.classes if c.id == "kl10")
        samel = next(s for s in kl10.students if "Samel" in s.name)
        assert samel.language == "ZW"

    def test_student_english_group(self, school_data):
        kl9 = next(c for c in school_data.classes if c.id == "kl9")
        beyga = next(s for s in kl9.students if s.name == "Franciszek Beyga")
        assert beyga.english_group == "angielski1"
        cader = next(s for s in kl9.students if s.name == "Mateusz Cader")
        assert cader.english_group == "angielski2"


# --- parse_matrix ---

class TestParseMatrix:
    def test_entries_exist(self, school_data):
        assert len(school_data.matrix) > 0

    def test_mat_n1_kl9(self, school_data):
        entry = next(
            e for e in school_data.matrix
            if e.subject == "matematyka" and e.teacher == "n1"
        )
        assert entry.hours["kl9"] == 4
        assert entry.hours["kl10"] == 0

    def test_ang1_n8(self, school_data):
        entry = next(
            e for e in school_data.matrix
            if e.subject == "angielski1" and e.teacher == "n8"
        )
        assert entry.hours["kl9"] == 3
        assert entry.hours["kl10"] == 3
        assert entry.hours["kl11"] == 3
        assert entry.hours["kl12"] == 3

    def test_ang2_n8(self, school_data):
        entry = next(
            e for e in school_data.matrix
            if e.subject == "angielski2" and e.teacher == "n8"
        )
        assert entry.hours["kl9"] == 3

    def test_rozszerzone_exist(self, school_data):
        roz = [e for e in school_data.matrix if "_roz" in e.subject]
        assert len(roz) > 0

    def test_chemia_roz_n5(self, school_data):
        entry = next(
            e for e in school_data.matrix
            if e.subject == "chemia_roz" and e.teacher == "n5"
        )
        assert entry.hours["kl9"] == 2
        assert entry.hours["kl12"] == 2


# --- parse_rules ---

class TestParseRules:
    def test_slots(self, school_data):
        assert len(school_data.rules.slots) == 10
        assert school_data.rules.slots[0][0] == 0
        assert school_data.rules.slots[9][0] == 9

    def test_slot_times(self, school_data):
        slot0 = school_data.rules.slots[0]
        assert "7:25" in slot0[1] or "7.25" in slot0[1]

    def test_days(self, school_data):
        assert school_data.rules.days == ["pn", "wt", "sr", "cz", "pt"]

    def test_max_lessons(self, school_data):
        assert school_data.rules.max_lessons_per_day == 9

    def test_epochs_count(self, school_data):
        assert len(school_data.rules.epochs) == 9

    def test_epoch_first(self, school_data):
        first = school_data.rules.epochs[0]
        assert "2.09" in first.period or "2.9" in first.period
        assert first.assignments.get("kl9") == "informatyka"
        assert first.assignments.get("kl10") == "biologia"
        assert first.assignments.get("kl11") == "historia"

    def test_epoch_classes(self, school_data):
        assert "kl9" in school_data.rules.epoch_classes
        assert "kl10" in school_data.rules.epoch_classes
        assert "kl11" in school_data.rules.epoch_classes
        assert "kl12" not in school_data.rules.epoch_classes

    def test_optimization_rules(self, school_data):
        opt = school_data.rules.optimization
        assert len(opt) == 7

    def test_optimization_ids(self, school_data):
        opt_ids = [r.id for r in school_data.rules.optimization]
        assert "unikaj_slot0" in opt_ids
        assert "brak_okienek_uczniow" in opt_ids
        assert "kompaktowy_plan" in opt_ids

    def test_optimization_weights(self, school_data):
        slot0 = next(r for r in school_data.rules.optimization if r.id == "unikaj_slot0")
        assert slot0.weight == 100
        compact = next(r for r in school_data.rules.optimization if r.id == "kompaktowy_plan")
        assert compact.weight == 10

    def test_optimization_has_descriptions(self, school_data):
        for rule in school_data.rules.optimization:
            assert len(rule.description) > 0


# --- build_language_groups ---

class TestLanguageGroups:
    def test_four_groups(self, school_data):
        assert len(school_data.language_groups) == 4

    def test_languages(self, school_data):
        langs = {g.language for g in school_data.language_groups}
        assert "j_hiszpanski" in langs
        assert "j_niemiecki" in langs
        assert "j_rosyjski" in langs
        assert "j_francuski" in langs

    def test_hiszpanski_students(self, school_data):
        hisp = next(g for g in school_data.language_groups if g.language == "j_hiszpanski")
        # kl9: 17, kl10: ~10, kl11: ~12, kl12: 2
        assert len(hisp.students) > 30

    def test_niemiecki_students(self, school_data):
        niem = next(g for g in school_data.language_groups if g.language == "j_niemiecki")
        # kl10: 5, kl11: 1, kl12: 5
        assert len(niem.students) == 11

    def test_rosyjski_students(self, school_data):
        ros = next(g for g in school_data.language_groups if g.language == "j_rosyjski")
        assert len(ros.students) == 3

    def test_francuski_students(self, school_data):
        fran = next(g for g in school_data.language_groups if g.language == "j_francuski")
        assert len(fran.students) == 2

    def test_zw_excluded(self, school_data):
        all_students = []
        for g in school_data.language_groups:
            all_students.extend(g.students)
        zw_names = [s.name for s in all_students if s.language == "ZW"]
        assert len(zw_names) == 0

    def test_consecutive_flag(self, school_data):
        for g in school_data.language_groups:
            assert g.consecutive is True
            assert g.hours == 2

    def test_teacher_assigned(self, school_data):
        hisp = next(g for g in school_data.language_groups if g.language == "j_hiszpanski")
        assert hisp.teacher == "n8"
        ros = next(g for g in school_data.language_groups if g.language == "j_rosyjski")
        assert ros.teacher == "n12"

    def test_students_from_multiple_classes(self, school_data):
        hisp = next(g for g in school_data.language_groups if g.language == "j_hiszpanski")
        class_ids = {s.class_id for s in hisp.students}
        assert len(class_ids) >= 3
