"""Real PostgreSQL proof for agent-authenticated metric writes."""

from __future__ import annotations

import os
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db.tenant_context import set_current_organization
from app.models.identity import Membership, Organization, User
from app.models.infrastructure import InfrastructureAsset
from app.models.infrastructure_metrics import InfrastructureMetric
from app.services.agents import authenticate_agent_credential, create_agent_credential
from app.services.infrastructure_metrics import create_infrastructure_metric
from app.services.rbac import create_default_roles_for_organization

pytestmark = pytest.mark.skipif(
    os.getenv("EII_POSTGRES_RLS_APPLICATION") != "1",
    reason="Requires the least-privilege application PostgreSQL integration job.",
)


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def test_authenticated_agent_can_write_only_its_bound_tenant_metrics() -> None:
    """The token establishes one tenant; a forged organization is rejected by RLS."""
    runtime_url = os.environ.get("DATABASE_URL")
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    assert runtime_url, "DATABASE_URL must use the non-superuser runtime role."
    assert migration_url, "MIGRATION_DATABASE_URL must use the migrator role."

    runtime_engine = create_engine(
        runtime_url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    migrator_engine = create_engine(migration_url, pool_pre_ping=True)

    suffix = uuid4().hex
    try:
        with Session(migrator_engine) as db:
            organization_a = Organization(
                name=f"Agent ingestion A {suffix}",
                slug=f"agent-ingestion-a-{suffix}",
            )
            organization_b = Organization(
                name=f"Agent ingestion B {suffix}",
                slug=f"agent-ingestion-b-{suffix}",
            )
            user_a = User(
                email=f"agent-ingestion-a-{suffix}@example.test",
                display_name="Agent ingestion A",
            )
            user_b = User(
                email=f"agent-ingestion-b-{suffix}@example.test",
                display_name="Agent ingestion B",
            )
            db.add_all([organization_a, organization_b, user_a, user_b])
            db.flush()

            roles_a = create_default_roles_for_organization(db, organization_a.id)
            roles_b = create_default_roles_for_organization(db, organization_b.id)
            owner_a = next(role for role in roles_a if role.name == "owner")
            owner_b = next(role for role in roles_b if role.name == "owner")
            db.add_all(
                [
                    Membership(
                        organization_id=organization_a.id,
                        user_id=user_a.id,
                        role_id=owner_a.id,
                    ),
                    Membership(
                        organization_id=organization_b.id,
                        user_id=user_b.id,
                        role_id=owner_b.id,
                    ),
                ]
            )
            db.flush()

            set_current_organization(db, organization_a.id, user_a.id)
            asset_a = InfrastructureAsset(
                organization_id=organization_a.id,
                name=f"Agent A {suffix}",
                asset_type="server",
            )
            db.add(asset_a)
            db.flush()
            credential = create_agent_credential(
                db,
                organization_id=organization_a.id,
                asset_id=asset_a.id,
                created_by_user_id=user_a.id,
                name="postgres-agent-a",
            )

            set_current_organization(db, organization_b.id, user_b.id)
            asset_b = InfrastructureAsset(
                organization_id=organization_b.id,
                name=f"Agent B {suffix}",
                asset_type="server",
            )
            db.add(asset_b)
            db.commit()

            organization_a_id = organization_a.id
            organization_b_id = organization_b.id
            asset_a_id = asset_a.id
            asset_b_id = asset_b.id
            token = credential.token
            user_a_id = user_a.id

        with Session(runtime_engine) as db:
            assert db.scalar(text("SELECT current_user")) == "eii_runtime"
            credential = authenticate_agent_credential(db, token)
            assert credential is not None
            assert credential.organization_id == organization_a_id
            assert credential.asset_id == asset_a_id
            create_infrastructure_metric(
                db,
                organization_a_id,
                asset_a_id,
                {
                    "metric_name": "cpu.utilization",
                    "metric_value": Decimal("10.25"),
                    "unit": "%",
                    "ingestion_source": "agent_api",
                },
            )
            db.commit()

        with Session(runtime_engine) as db:
            credential = authenticate_agent_credential(db, token)
            assert credential is not None
            with pytest.raises(DBAPIError) as denied:
                with db.begin_nested():
                    create_infrastructure_metric(
                        db,
                        organization_b_id,
                        asset_b_id,
                        {
                            "metric_name": "cpu.utilization",
                            "metric_value": Decimal("99.0"),
                            "unit": "%",
                            "ingestion_source": "agent_api",
                        },
                    )
            assert _sqlstate(denied.value) == "42501"

            own_rows = list(
                db.scalars(
                    select(InfrastructureMetric).where(
                        InfrastructureMetric.organization_id == organization_a_id
                    )
                ).all()
            )
            foreign_rows = list(
                db.scalars(
                    select(InfrastructureMetric).where(
                        InfrastructureMetric.organization_id == organization_b_id
                    )
                ).all()
            )
            assert len(own_rows) == 1
            assert own_rows[0].ingestion_source == "agent_api"
            assert foreign_rows == []
            assert own_rows[0].asset_id == asset_a_id
            assert own_rows[0].organization_id == organization_a_id
            assert credential.created_by_user_id == user_a_id
    finally:
        runtime_engine.dispose()
        migrator_engine.dispose()
