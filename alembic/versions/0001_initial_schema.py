"""Create the initial StudentTrack schema."""

import sqlalchemy as sa
from alembic import op


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("local_slot", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("local_slot = 1", name="ck_students_local_slot"),
        sa.PrimaryKeyConstraint("id", name="pk_students"),
        sa.UniqueConstraint("local_slot", name="uq_students_local_slot"),
    )
    op.create_table(
        "semesters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("grading_scale", sa.SmallInteger(), nullable=False),
        sa.Column("averaging_mode", sa.String(16), server_default="subject_means", nullable=False),
        sa.CheckConstraint("grading_scale IN (5, 12, 100)", name="ck_semesters_grading_scale"),
        sa.CheckConstraint(
            "averaging_mode IN ('subject_means', 'all_grades')", name="ck_semesters_averaging_mode"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name="fk_semesters_student", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_semesters"),
        sa.UniqueConstraint("id", "grading_scale", name="uq_semesters_id_grading_scale"),
    )
    op.create_index("ix_semesters_student_id", "semesters", ["student_id"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.ForeignKeyConstraint(
            ["semester_id"], ["semesters.id"], name="fk_subjects_semester", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_subjects"),
        sa.UniqueConstraint("id", "semester_id", name="uq_subjects_id_semester_id"),
    )
    op.create_index("ix_subjects_semester_id", "subjects", ["semester_id"])

    op.create_table(
        "grades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("semester_id", sa.Integer(), nullable=False),
        sa.Column("grading_scale", sa.SmallInteger(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "value >= CASE WHEN grading_scale = 100 THEN 0 ELSE 1 END AND value <= grading_scale",
            name="ck_grades_value_range",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "semester_id"],
            ["subjects.id", "subjects.semester_id"],
            name="fk_grades_subject_semester",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["semester_id", "grading_scale"],
            ["semesters.id", "semesters.grading_scale"],
            name="fk_grades_semester_scale",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_grades"),
    )
    op.create_index("ix_grades_subject_id_semester_id", "grades", ["subject_id", "semester_id"])
    op.create_index("ix_grades_semester_id_grading_scale", "grades", ["semester_id", "grading_scale"])

    op.create_table(
        "scholarship_settings",
        sa.Column("semester_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("grading_scale", sa.SmallInteger(), nullable=False),
        sa.Column("target_average", sa.Numeric(5, 2), nullable=False),
        sa.CheckConstraint(
            "target_average > 0 AND target_average <= grading_scale "
            "AND (grading_scale = 100 OR target_average >= 1)",
            name="ck_scholarship_settings_target_range",
        ),
        sa.ForeignKeyConstraint(
            ["semester_id", "grading_scale"],
            ["semesters.id", "semesters.grading_scale"],
            name="fk_scholarship_settings_semester_scale",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("semester_id", name="pk_scholarship_settings"),
    )


def downgrade() -> None:
    op.drop_table("scholarship_settings")
    op.drop_table("grades")
    op.drop_table("subjects")
    op.drop_table("semesters")
    op.drop_table("students")
