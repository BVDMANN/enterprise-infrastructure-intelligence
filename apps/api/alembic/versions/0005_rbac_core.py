"""Organization-scoped roles and permissions (P1-A3).

Backfills each existing membership from its checked role name to a role_id
owned by the same organization. Downgrade refuses to discard custom roles or
permission assignments.
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_rbac_core"
down_revision = "0004_user_password_hash"
branch_labels = None
depends_on = None

PERMISSION_DESCRIPTIONS = {
    "organization.read": "Read the current organization's profile.",
    "organization.manage": "Change organization-level settings.",
    "members.read": "Read organization members and memberships.",
    "members.manage": "Invite, add, deactivate, or remove organization members.",
    "roles.read": "Read organization roles and permission assignments.",
    "roles.manage": "Create and change organization-scoped roles.",
    "infrastructure.read": "Read infrastructure inventory and status.",
    "infrastructure.manage": "Manage infrastructure connectors and inventory.",
    "audit.read": "Read the organization's audit events.",
}

ROLE_PERMISSIONS = {
    "owner": frozenset(PERMISSION_DESCRIPTIONS),
    "admin": frozenset(
        {
            "organization.read",
            "members.read",
            "members.manage",
            "roles.read",
            "roles.manage",
            "infrastructure.read",
            "infrastructure.manage",
            "audit.read",
        }
    ),
    "member": frozenset(
        {"organization.read", "members.read", "infrastructure.read"}
    ),
    "viewer": frozenset(
        {"organization.read", "infrastructure.read", "audit.read"}
    ),
}


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
        sa.UniqueConstraint("organization_id", "id", name="uq_roles_organization_id_id"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_roles_name_nonempty"),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])

    op.create_table(
        "permissions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_permissions_name"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    permissions_table = sa.table(
        "permissions",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String(length=100)),
        sa.column("description", sa.String(length=255)),
    )
    permission_ids = {name: uuid4() for name in PERMISSION_DESCRIPTIONS}
    op.bulk_insert(
        permissions_table,
        [
            {"id": permission_ids[name], "name": name, "description": description}
            for name, description in PERMISSION_DESCRIPTIONS.items()
        ],
    )

    op.add_column("memberships", sa.Column("role_id", UUID(as_uuid=True), nullable=True))

    roles_table = sa.table(
        "roles",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("organization_id", UUID(as_uuid=True)),
        sa.column("name", sa.String(length=64)),
        sa.column("description", sa.String(length=255)),
        sa.column("is_system", sa.Boolean()),
    )
    role_ids: dict[tuple[str, str], object] = {}
    role_rows = []
    bind = op.get_bind()
    organizations = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for organization_row in organizations:
        organization_id = organization_row[0]
        for role_name in ROLE_PERMISSIONS:
            role_id = uuid4()
            role_ids[(str(organization_id), role_name)] = role_id
            role_rows.append(
                {
                    "id": role_id,
                    "organization_id": organization_id,
                    "name": role_name,
                    "description": f"Built-in {role_name} role",
                    "is_system": True,
                }
            )
    if role_rows:
        op.bulk_insert(roles_table, role_rows)

    memberships = bind.execute(
        sa.text("SELECT id, organization_id, role FROM memberships")
    ).fetchall()
    for membership in memberships:
        role_id = role_ids.get((str(membership[1]), membership[2]))
        if role_id is None:
            raise RuntimeError(
                f"Cannot migrate membership {membership[0]}: unknown role "
                f"{membership[2]!r} for organization {membership[1]}"
            )
        bind.execute(
            sa.text("UPDATE memberships SET role_id = :role_id WHERE id = :id"),
            {"role_id": role_id, "id": membership[0]},
        )

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", UUID(as_uuid=True)),
        sa.column("permission_id", UUID(as_uuid=True)),
    )
    links = []
    for (_, role_name), role_id in role_ids.items():
        for permission_name in ROLE_PERMISSIONS[role_name]:
            links.append(
                {
                    "role_id": role_id,
                    "permission_id": permission_ids[permission_name],
                }
            )
    if links:
        op.bulk_insert(role_permissions_table, links)

    op.alter_column(
        "memberships",
        "role_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_constraint("ck_memberships_role", "memberships", type_="check")
    op.drop_column("memberships", "role")
    op.create_foreign_key(
        "fk_memberships_organization_role",
        "memberships",
        "roles",
        ["organization_id", "role_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_memberships_role_id", "memberships", ["role_id"])


def downgrade() -> None:
    bind = op.get_bind()
    roles = bind.execute(
        sa.text("SELECT id, name, is_system FROM roles")
    ).fetchall()
    if any(name not in ROLE_PERMISSIONS or not is_system for _, name, is_system in roles):
        raise RuntimeError("Refusing to discard custom roles during RBAC downgrade.")

    permission_names = {
        row[0] for row in bind.execute(sa.text("SELECT name FROM permissions")).fetchall()
    }
    if permission_names != set(PERMISSION_DESCRIPTIONS):
        raise RuntimeError(
            "Refusing to discard a customized permission catalog during RBAC downgrade."
        )

    actual_links: dict[object, set[str]] = {}
    link_rows = bind.execute(
        sa.text(
            "SELECT rp.role_id, p.name FROM role_permissions rp "
            "JOIN permissions p ON p.id = rp.permission_id"
        )
    ).fetchall()
    for role_id, permission_name in link_rows:
        actual_links.setdefault(role_id, set()).add(permission_name)
    for role_id, role_name, is_system in bind.execute(
        sa.text("SELECT id, name, is_system FROM roles")
    ).fetchall():
        if not is_system or actual_links.get(role_id, set()) != set(ROLE_PERMISSIONS[role_name]):
            raise RuntimeError(
                f"Refusing to discard customized permissions for role {role_name!r}."
            )

    op.add_column(
        "memberships",
        sa.Column("role", sa.String(length=32), nullable=True),
    )
    bind.execute(
        sa.text(
            "UPDATE memberships SET role = roles.name FROM roles "
            "WHERE memberships.role_id = roles.id "
            "AND memberships.organization_id = roles.organization_id"
        )
    )
    missing_roles = bind.execute(
        sa.text("SELECT count(*) FROM memberships WHERE role IS NULL")
    ).scalar_one()
    if missing_roles:
        raise RuntimeError("Cannot downgrade RBAC: one or more memberships have no role.")

    op.alter_column(
        "memberships",
        "role",
        existing_type=sa.String(length=32),
        nullable=False,
        server_default="member",
    )
    op.drop_constraint(
        "fk_memberships_organization_role", "memberships", type_="foreignkey"
    )
    op.drop_index("ix_memberships_role_id", table_name="memberships")
    op.drop_column("memberships", "role_id")
    op.create_check_constraint(
        "ck_memberships_role",
        "memberships",
        "role IN ('owner', 'admin', 'member', 'viewer')",
    )

    op.drop_table("role_permissions")
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_table("permissions")
    op.drop_table("roles")
