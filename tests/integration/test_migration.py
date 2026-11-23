from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLES = {"students", "semesters", "subjects", "grades", "scholarship_settings"}


def test_initial_migration_matches_models_and_can_be_reversed(isolated_engine):
    with isolated_engine.begin() as connection:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["connection"] = connection

        command.upgrade(config, "head")
        assert TABLES <= set(inspect(connection).get_table_names())
        command.check(config)

        command.downgrade(config, "base")
        assert TABLES.isdisjoint(inspect(connection).get_table_names())

        command.upgrade(config, "head")
        assert TABLES <= set(inspect(connection).get_table_names())


def test_models_can_load_all_student_relationships(migrated_engine):
    from app.models import Grade, ScholarshipSettings, Semester, Student, Subject

    with Session(migrated_engine) as session:
        student = Student(display_name="Jamie")
        semester = Semester(name="Spring", grading_scale=5, student=student)
        subject = Subject(name="Chemistry", semester=semester)
        Grade(subject=subject, grading_scale=5, value=4)
        ScholarshipSettings(semester=semester, grading_scale=5, target_average="4.50")
        session.add(student)
        session.flush()
        student_id = student.id
        session.expire_all()

        saved_semester = session.get(Student, student_id).semesters[0]
        assert saved_semester.averaging_mode == "subject_means"
        assert saved_semester.subjects[0].grades[0].value == 4
        assert str(saved_semester.scholarship_settings.target_average) == "4.50"


def test_session_dependency_leaves_transaction_handling_to_the_caller(migrated_engine, monkeypatch):
    from app import db

    monkeypatch.setattr(db, "get_engine", lambda: migrated_engine)
    dependency = db.get_session()
    session = next(dependency)
    try:
        session.execute(text("INSERT INTO students (display_name) VALUES ('Jamie')"))
    finally:
        dependency.close()

    with migrated_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM students")).scalar_one() == 0


def insert_semester(connection, student_id, scale):
    return connection.execute(
        text(
            "INSERT INTO semesters (student_id, name, grading_scale) "
            "VALUES (:student_id, 'Spring', :scale) RETURNING id"
        ),
        {"student_id": student_id, "scale": scale},
    ).scalar_one()


def insert_subject(connection, scale):
    student_id = connection.execute(
        text("INSERT INTO students (display_name) VALUES ('Jamie') RETURNING id")
    ).scalar_one()
    semester_id = insert_semester(connection, student_id, scale)
    subject_id = connection.execute(
        text("INSERT INTO subjects (semester_id, name) VALUES (:semester_id, 'Chemistry') RETURNING id"),
        {"semester_id": semester_id},
    ).scalar_one()
    return student_id, semester_id, subject_id


def insert_grade(connection, subject_id, semester_id, scale, value):
    connection.execute(
        text(
            "INSERT INTO grades (subject_id, semester_id, grading_scale, value) "
            "VALUES (:subject_id, :semester_id, :scale, :value)"
        ),
        {"subject_id": subject_id, "semester_id": semester_id, "scale": scale, "value": value},
    )


def insert_target(connection, semester_id, scale, target):
    connection.execute(
        text(
            "INSERT INTO scholarship_settings (semester_id, grading_scale, target_average) "
            "VALUES (:semester_id, :scale, :target)"
        ),
        {"semester_id": semester_id, "scale": scale, "target": target},
    )


@pytest.mark.parametrize(("scale", "minimum"), [(5, 1), (12, 1), (100, 0)])
def test_grade_range_is_enforced_by_postgres(migrated_engine, scale, minimum):
    with migrated_engine.begin() as connection:
        _, semester_id, subject_id = insert_subject(connection, scale)
        insert_grade(connection, subject_id, semester_id, scale, minimum)
        insert_grade(connection, subject_id, semester_id, scale, scale)

        for invalid_grade in (minimum - 1, scale + 1):
            with pytest.raises(IntegrityError) as error, connection.begin_nested():
                insert_grade(connection, subject_id, semester_id, scale, invalid_grade)
            assert error.value.orig.diag.constraint_name == "ck_grades_value_range"


def test_grade_cannot_use_a_different_semester_or_scale(migrated_engine):
    with migrated_engine.begin() as connection:
        student_id, semester_id, subject_id = insert_subject(connection, 5)
        other_semester_id = insert_semester(connection, student_id, 5)

        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            insert_grade(connection, subject_id, other_semester_id, 5, 4)
        assert error.value.orig.diag.constraint_name == "fk_grades_subject_semester"

        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            insert_grade(connection, subject_id, semester_id, 12, 4)
        assert error.value.orig.diag.constraint_name == "fk_grades_semester_scale"

        insert_grade(connection, subject_id, semester_id, 5, 4)
        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            connection.execute(
                text("UPDATE semesters SET grading_scale = 12 WHERE id = :id"), {"id": semester_id}
            )
        assert error.value.orig.diag.constraint_name == "fk_grades_semester_scale"


@pytest.mark.parametrize(("scale", "invalid_targets"), [(5, (0.99, 5.01)), (12, (0.99, 12.01)), (100, (0, 100.01))])
def test_target_range_and_semester_scale_are_enforced(migrated_engine, scale, invalid_targets):
    with migrated_engine.begin() as connection:
        _, semester_id, _ = insert_subject(connection, scale)
        other_scale = 12 if scale == 5 else 5

        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            insert_target(connection, semester_id, other_scale, 4)
        assert error.value.orig.diag.constraint_name == "fk_scholarship_settings_semester_scale"

        for invalid_target in invalid_targets:
            with pytest.raises(IntegrityError) as error, connection.begin_nested():
                insert_target(connection, semester_id, scale, invalid_target)
            assert error.value.orig.diag.constraint_name == "ck_scholarship_settings_target_range"

        insert_target(connection, semester_id, scale, scale)
        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            connection.execute(
                text("UPDATE semesters SET grading_scale = :scale WHERE id = :id"),
                {"scale": other_scale, "id": semester_id},
            )
        assert error.value.orig.diag.constraint_name == "fk_scholarship_settings_semester_scale"


def test_postgres_cascades_deletions_and_enforces_the_single_profile(migrated_engine):
    with migrated_engine.begin() as connection:
        student_id, semester_id, subject_id = insert_subject(connection, 5)
        insert_grade(connection, subject_id, semester_id, 5, 4)
        insert_target(connection, semester_id, 5, 5)

        with pytest.raises(IntegrityError) as error, connection.begin_nested():
            connection.execute(text("INSERT INTO students (display_name) VALUES ('Morgan')"))
        assert error.value.orig.diag.constraint_name == "uq_students_local_slot"

        connection.execute(text("DELETE FROM subjects WHERE id = :id"), {"id": subject_id})
        assert connection.execute(text("SELECT count(*) FROM grades")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM semesters")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM scholarship_settings")).scalar_one() == 1

        subject_id = connection.execute(
            text("INSERT INTO subjects (semester_id, name) VALUES (:semester_id, 'Biology') RETURNING id"),
            {"semester_id": semester_id},
        ).scalar_one()
        insert_grade(connection, subject_id, semester_id, 5, 5)
        connection.execute(text("DELETE FROM students WHERE id = :id"), {"id": student_id})

        for table in TABLES:
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
