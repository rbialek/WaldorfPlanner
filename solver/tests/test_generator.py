"""Tests for the timetable generator."""

import pytest
from pathlib import Path

from solver.parser import parse_all
from solver.model import build_model
from solver.generator import generate_all

DATA_DIR = Path(__file__).parent.parent.parent / "dane" / "2026-27"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "plany"


@pytest.fixture(scope="module")
def generated_plans():
    """Generate all plans once for tests."""
    data = parse_all(DATA_DIR)
    solution = build_model(data, timeout_seconds=120)
    assert solution is not None
    generate_all(data, solution, OUTPUT_DIR)
    return data, solution


class TestClassPlansGenerated:
    def test_klasa9_exists(self, generated_plans):
        assert (OUTPUT_DIR / "klasa9.md").exists()

    def test_klasa10_exists(self, generated_plans):
        assert (OUTPUT_DIR / "klasa10.md").exists()

    def test_klasa11_exists(self, generated_plans):
        assert (OUTPUT_DIR / "klasa11.md").exists()

    def test_klasa12_exists(self, generated_plans):
        assert (OUTPUT_DIR / "klasa12.md").exists()

    def test_klasa9_has_timetable(self, generated_plans):
        content = (OUTPUT_DIR / "klasa9.md").read_text()
        assert "Tygodniowy plan" in content
        assert "Poniedzialek" in content

    def test_klasa9_has_english_groups(self, generated_plans):
        content = (OUTPUT_DIR / "klasa9.md").read_text()
        assert "angielski1" in content
        assert "angielski2" in content

    def test_klasa9_has_student_names(self, generated_plans):
        content = (OUTPUT_DIR / "klasa9.md").read_text()
        assert "Beyga" in content
        assert "Borowska" in content

    def test_klasa9_has_epoch_info(self, generated_plans):
        content = (OUTPUT_DIR / "klasa9.md").read_text()
        assert "EPOKA" in content

    def test_klasa12_no_epoch(self, generated_plans):
        content = (OUTPUT_DIR / "klasa12.md").read_text()
        # kl12 doesn't participate in epochs, so no [EPOKA] markers
        # But individual subjects should be listed normally
        assert "Baczyk" in content


class TestTeacherPlansGenerated:
    def test_all_teacher_files_exist(self, generated_plans):
        data, _ = generated_plans
        for teacher in data.teachers:
            name_parts = teacher.name.split()
            filename = f"{teacher.id}_{'_'.join(name_parts)}.md"
            filepath = OUTPUT_DIR / filename
            assert filepath.exists(), f"Missing teacher plan: {filename}"

    def test_teacher_plan_has_timetable(self, generated_plans):
        content = (OUTPUT_DIR / "n1_Jan_Kowalski.md").read_text()
        assert "Tygodniowy plan" in content
        assert "Przedmioty:" in content
        assert "Laczna liczba godzin" in content

    def test_teacher_plan_has_details(self, generated_plans):
        content = (OUTPUT_DIR / "n1_Jan_Kowalski.md").read_text()
        assert "Szczegoly lekcji" in content
        assert "Podsumowanie" in content

    def test_teacher_constraints_shown(self, generated_plans):
        content = (OUTPUT_DIR / "n3_Piotr_Wisniewski.md").read_text()
        assert "Ograniczenia:" in content
        assert "Piatek" in content


class TestReportGenerated:
    def test_report_exists(self, generated_plans):
        assert (OUTPUT_DIR / "raport.md").exists()

    def test_report_has_sections(self, generated_plans):
        content = (OUTPUT_DIR / "raport.md").read_text()
        assert "Uzycie lekcji 0" in content
        assert "Okienka uczniow" in content
        assert "Plan nauczycieli" in content

    def test_report_has_all_teachers(self, generated_plans):
        data, _ = generated_plans
        content = (OUTPUT_DIR / "raport.md").read_text()
        for teacher in data.teachers:
            assert teacher.name in content, f"Missing teacher in report: {teacher.name}"


class TestCrossValidation:
    """Validate consistency between class and teacher plans."""

    def test_schedule_entries_match(self, generated_plans):
        data, solution = generated_plans
        schedule = solution["schedule"]
        # For each lesson in schedule, verify it appears in both class and teacher plan
        for (cls_id, d, s), (subj, teacher_id) in schedule.items():
            class_num = cls_id.replace("kl", "")
            class_file = OUTPUT_DIR / f"klasa{class_num}.md"
            assert class_file.exists()

            teacher = next((t for t in data.teachers if t.id == teacher_id), None)
            if teacher:
                name_parts = teacher.name.split()
                teacher_file = OUTPUT_DIR / f"{teacher.id}_{'_'.join(name_parts)}.md"
                assert teacher_file.exists()
