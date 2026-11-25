"""One-time interactive bootstrap for the first EII administrator.

Run after applying Alembic migrations:
    cd apps/api && python -m scripts.bootstrap_admin

No default credentials or password command-line arguments are accepted.
The PostgreSQL table lock makes the empty-database check safe against
concurrent bootstrap attempts.
"""

from __future__ import annotations

import getpass
import re

from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.models.identity import Membership, Organization, User
from app.services.passwords import hash_password


def main() -> None:
    """Create the first user and their initial organization owner membership."""
    email = input("Administrator email: ").strip().lower()
    display_name = input("Administrator display name: ").strip()
    organization_name = input("Initial organization name: ").strip()
    slug = input("Organization slug (lowercase, hyphen-separated): ").strip().lower()

    if "@" not in email or len(email) > 320:
        raise SystemExit("Invalid email address.")
    if not display_name or len(display_name) > 255:
        raise SystemExit("Display name is required (max 255 characters).")
    if not organization_name or len(organization_name) > 255:
        raise SystemExit("Organization name is required (max 255 characters).")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SystemExit("Invalid organization slug.")

    password = getpass.getpass("Administrator password (12–128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    password_hash = hash_password(password)

    db = SessionLocal()
    try:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            raise SystemExit("Bootstrap is supported only against PostgreSQL.")
        db.execute(text("LOCK TABLE users IN EXCLUSIVE MODE"))
        existing_users = db.scalar(select(func.count()).select_from(User))
        if existing_users:
            raise SystemExit(
                "Bootstrap refused: users already exist. Use the normal account provisioning flow."
            )

        user = User(
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            is_active=True,
        )
        organization = Organization(name=organization_name, slug=slug)
        db.add_all([user, organization])
        db.flush()
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=user.id,
                role="owner",
            )
        )
        db.commit()
        print(f"Initial administrator created: {user.email}")
        print(f"Organization created: {organization.slug}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
