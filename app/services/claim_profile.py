"""Assign credentials to an old local profile; run only as a DB administrator."""
import argparse
from getpass import getpass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import Student
from app.schemas.auth import RegisterRequest
from app.services.security import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id", type=int)
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass("New password: ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords differ")
    with Session(get_engine()) as session:
        student = session.scalar(select(Student).where(Student.id == args.student_id).with_for_update())
        if student is None or student.username is not None:
            raise SystemExit("No unclaimed profile with this ID")
        data = RegisterRequest(display_name=student.display_name, username=args.username, password=password)
        student.username = data.username
        student.password_hash = hash_password(data.password)
        session.commit()
    print("Profile claimed")


if __name__ == "__main__":
    main()
