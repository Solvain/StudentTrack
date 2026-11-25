"""Add account credentials without deleting existing academic data."""
import sqlalchemy as sa
from alembic import op

revision = "0002_student_auth"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_students_local_slot", "students", type_="check")
    op.drop_constraint("uq_students_local_slot", "students", type_="unique")
    op.drop_column("students", "local_slot")
    op.add_column("students", sa.Column("username", sa.String(50), nullable=True))
    op.add_column("students", sa.Column("password_hash", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_students_username", "students", ["username"])
    op.create_check_constraint("ck_students_credentials_pair", "students",
                               "(username IS NULL) = (password_hash IS NULL)")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM students")).scalar_one() > 1:
        raise RuntimeError("Cannot downgrade a multi-account database")
    op.drop_constraint("ck_students_credentials_pair", "students", type_="check")
    op.drop_constraint("uq_students_username", "students", type_="unique")
    op.drop_column("students", "password_hash")
    op.drop_column("students", "username")
    op.add_column("students", sa.Column("local_slot", sa.SmallInteger(), server_default=sa.text("1"), nullable=False))
    op.create_check_constraint("ck_students_local_slot", "students", "local_slot = 1")
    op.create_unique_constraint("uq_students_local_slot", "students", ["local_slot"])
