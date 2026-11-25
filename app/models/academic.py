from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("username", name="uq_students_username"),
        CheckConstraint("(username IS NULL) = (password_hash IS NULL)", name="ck_students_credentials_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str | None] = mapped_column(String(50))
    password_hash: Mapped[str | None] = mapped_column(String(255))

    semesters: Mapped[list[Semester]] = relationship(
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        CheckConstraint("grading_scale IN (5, 12, 100)", name="ck_semesters_grading_scale"),
        CheckConstraint(
            "averaging_mode IN ('subject_means', 'all_grades')", name="ck_semesters_averaging_mode"
        ),
        UniqueConstraint("id", "grading_scale", name="uq_semesters_id_grading_scale"),
        Index("ix_semesters_student_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", name="fk_semesters_student", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))
    grading_scale: Mapped[int] = mapped_column(SmallInteger)
    averaging_mode: Mapped[str] = mapped_column(String(16), server_default="subject_means")

    student: Mapped[Student] = relationship(back_populates="semesters")
    subjects: Mapped[list[Subject]] = relationship(
        back_populates="semester", cascade="all, delete-orphan", passive_deletes=True
    )
    scholarship_settings: Mapped[ScholarshipSettings | None] = relationship(
        back_populates="semester", cascade="all, delete-orphan", passive_deletes=True
    )


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("id", "semester_id", name="uq_subjects_id_semester_id"),
        Index("ix_subjects_semester_id", "semester_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", name="fk_subjects_semester", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))

    semester: Mapped[Semester] = relationship(back_populates="subjects")
    grades: Mapped[list[Grade]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", passive_deletes=True
    )


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subject_id", "semester_id"],
            ["subjects.id", "subjects.semester_id"],
            name="fk_grades_subject_semester",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["semester_id", "grading_scale"],
            ["semesters.id", "semesters.grading_scale"],
            name="fk_grades_semester_scale",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "value >= CASE WHEN grading_scale = 100 THEN 0 ELSE 1 END AND value <= grading_scale",
            name="ck_grades_value_range",
        ),
        Index("ix_grades_subject_id_semester_id", "subject_id", "semester_id"),
        Index("ix_grades_semester_id_grading_scale", "semester_id", "grading_scale"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column()
    semester_id: Mapped[int] = mapped_column()
    grading_scale: Mapped[int] = mapped_column(SmallInteger)
    value: Mapped[int] = mapped_column(SmallInteger)

    subject: Mapped[Subject] = relationship(back_populates="grades")


class ScholarshipSettings(Base):
    __tablename__ = "scholarship_settings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["semester_id", "grading_scale"],
            ["semesters.id", "semesters.grading_scale"],
            name="fk_scholarship_settings_semester_scale",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "target_average > 0 AND target_average <= grading_scale "
            "AND (grading_scale = 100 OR target_average >= 1)",
            name="ck_scholarship_settings_target_range",
        ),
    )

    semester_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    grading_scale: Mapped[int] = mapped_column(SmallInteger)
    target_average: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    semester: Mapped[Semester] = relationship(back_populates="scholarship_settings")
