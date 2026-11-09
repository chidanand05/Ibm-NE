"""Initial schema — all 15 tables.

Revision ID: 001_initial_schema
Revises: —
Create Date: 2026-11-07 00:00:00.000000 UTC
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── PostGIS extension (must exist before GEOGRAPHY columns) ───────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_role", "users", ["role"])

    # ── venues ────────────────────────────────────────────────────────────────
    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False, server_default="Bengaluru"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("total_capacity", sa.Integer(), nullable=False),
        sa.Column("gates", postgresql.JSONB(), nullable=True),
        sa.Column("metro_stations", postgresql.JSONB(), nullable=True),
        sa.Column("bus_stops", postgresql.JSONB(), nullable=True),
        sa.Column("h3_center_res7", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_venues_location", "venues", ["location"], postgresql_using="gist")

    # ── events ────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("venue_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("venues.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_attendance", sa.Integer(), nullable=True),
        sa.Column("actual_attendance", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="SCHEDULED"),
        sa.Column("data_source", sa.String(), nullable=False, server_default="SIMULATED"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_events_venue", "events", ["venue_id"])
    op.create_index("idx_events_status", "events", ["status"])
    op.create_index("idx_events_scheduled_end", "events", ["scheduled_end"])

    # ── orchestrator_sessions ─────────────────────────────────────────────────
    op.create_table(
        "orchestrator_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="RUNNING"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("trigger_type", sa.String(), nullable=False, server_default="MANUAL"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_phase", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(), nullable=True),
    )
    op.create_index("idx_sessions_event", "orchestrator_sessions", ["event_id"])
    op.create_index("idx_sessions_status", "orchestrator_sessions", ["status"])
    op.create_index("idx_sessions_started", "orchestrator_sessions", ["started_at"])

    # ── agent_executions ──────────────────────────────────────────────────────
    op.create_table(
        "agent_executions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("orchestrator_sessions.id"), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("agent_version", sa.String(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_data", postgresql.JSONB(), nullable=True),
        sa.Column("output_data", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_used", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_exec_event", "agent_executions", ["event_id"])
    op.create_index("idx_exec_session", "agent_executions", ["session_id"])
    op.create_index("idx_exec_agent", "agent_executions", ["agent_id"])
    op.create_index("idx_exec_status", "agent_executions", ["status"])

    # ── crowd_forecasts ───────────────────────────────────────────────────────
    op.create_table(
        "crowd_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("agent_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("forecast_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("total_demand", sa.Integer(), nullable=False),
        sa.Column("peak_zone_h3", sa.String(), nullable=True),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("data_source", sa.String(), nullable=False, server_default="SIMULATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_forecasts_event", "crowd_forecasts", ["event_id"])
    op.create_index("idx_forecasts_horizon", "crowd_forecasts", ["event_id", "horizon_minutes"])

    # ── h3_demand_cells ───────────────────────────────────────────────────────
    op.create_table(
        "h3_demand_cells",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("forecast_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("crowd_forecasts.id"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("h3_id", sa.String(), nullable=False),
        sa.Column("resolution", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("center_lat", sa.Numeric(9, 6), nullable=True),
        sa.Column("center_lon", sa.Numeric(9, 6), nullable=True),
        sa.Column("demand_persons", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("demand_category", sa.String(), nullable=True),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("data_source", sa.String(), nullable=False, server_default="SIMULATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_h3_cells_forecast", "h3_demand_cells", ["forecast_id"])
    op.create_index("idx_h3_cells_event_horizon", "h3_demand_cells", ["event_id", "horizon_minutes"])
    op.create_index("idx_h3_cells_h3id", "h3_demand_cells", ["h3_id"])

    # ── transport_supply_snapshots ────────────────────────────────────────────
    op.create_table(
        "transport_supply_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("agent_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_horizon", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("h3_id", sa.String(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("vehicles", sa.Integer(), nullable=True),
        sa.Column("frequency_mins", sa.Integer(), nullable=True),
        sa.Column("operational", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("gap_persons", sa.Integer(), nullable=True),
        sa.Column("data_source", sa.String(), nullable=False, server_default="SIMULATED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_supply_event", "transport_supply_snapshots", ["event_id"])
    op.create_index("idx_supply_mode", "transport_supply_snapshots", ["event_id", "mode"])

    # ── agent_messages ────────────────────────────────────────────────────────
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("from_agent", sa.String(), nullable=False),
        sa.Column("to_agent", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_messages_session", "agent_messages", ["session_id", "sequence"])

    # ── action_plans ──────────────────────────────────────────────────────────
    op.create_table(
        "action_plans",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("orchestrator_sessions.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_plan_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("action_plans.id"), nullable=True),
        sa.Column("event_intel_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("forecast_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("supply_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("police_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("planner_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("guidance_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strategies_considered", postgresql.JSONB(), nullable=True),
        sa.Column("recommended_strategy", postgresql.JSONB(), nullable=True),
        sa.Column("metro_actions", postgresql.JSONB(), nullable=True),
        sa.Column("bmtc_actions", postgresql.JSONB(), nullable=True),
        sa.Column("auto_actions", postgresql.JSONB(), nullable=True),
        sa.Column("police_actions", postgresql.JSONB(), nullable=True),
        sa.Column("citizen_guidance", postgresql.JSONB(), nullable=True),
        sa.Column("risk_assessment", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("data_source_summary", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_plans_event", "action_plans", ["event_id"])
    op.create_index("idx_plans_status", "action_plans", ["status"])
    op.create_index("idx_plans_session", "action_plans", ["session_id"])

    # ── action_plan_approvals ─────────────────────────────────────────────────
    op.create_table(
        "action_plan_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("action_plans.id"), nullable=False),
        sa.Column("officer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("edits_made", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_approvals_plan", "action_plan_approvals", ["plan_id"])
    op.create_index("idx_approvals_officer", "action_plan_approvals", ["officer_id"])

    # ── historical_outcomes ───────────────────────────────────────────────────
    op.create_table(
        "historical_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("action_plans.id"), nullable=True),
        sa.Column("recorded_by", sa.String(), nullable=False, server_default="learning_agent"),
        sa.Column("actual_attendance", sa.Integer(), nullable=True),
        sa.Column("actual_exit_duration_mins", sa.Integer(), nullable=True),
        sa.Column("actual_peak_zone_h3", sa.String(), nullable=True),
        sa.Column("forecast_mae", sa.Numeric(8, 2), nullable=True),
        sa.Column("forecast_error_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("transport_adequacy", sa.String(), nullable=True),
        sa.Column("plan_effectiveness", sa.String(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        sa.Column("chroma_doc_id", sa.String(), nullable=True),
        sa.Column("data_source", sa.String(), nullable=False, server_default="SIMULATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_outcomes_event", "historical_outcomes", ["event_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("actor_type", sa.String(), nullable=False, server_default="user"),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_actor", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_action", "audit_logs", ["action"])
    op.create_index("idx_audit_resource", "audit_logs", ["resource", "resource_id"])
    op.create_index("idx_audit_created", "audit_logs", ["created_at"])

    # ── llm_usage ─────────────────────────────────────────────────────────────
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("agent_exec_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("agent_executions.id"), nullable=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("events.id"), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="SUCCESS"),
        sa.Column("fallback_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_llm_usage_agent", "llm_usage", ["agent_exec_id"])
    op.create_index("idx_llm_usage_model", "llm_usage", ["model"])
    op.create_index("idx_llm_usage_provider", "llm_usage", ["provider"])
    op.create_index("idx_llm_usage_event", "llm_usage", ["event_id"])
    op.create_index("idx_llm_usage_date", "llm_usage", ["created_at"])

    # ── model_configs ─────────────────────────────────────────────────────────
    op.create_table(
        "model_configs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False, server_default="0.1"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_model_configs_agent", "model_configs", ["agent_id", "is_active"])
    op.create_index(
        "idx_model_configs_version",
        "model_configs",
        ["agent_id", "task_type", "prompt_version"],
        unique=True,
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("model_configs")
    op.drop_table("llm_usage")
    op.drop_table("audit_logs")
    op.drop_table("historical_outcomes")
    op.drop_table("action_plan_approvals")
    op.drop_table("action_plans")
    op.drop_table("agent_messages")
    op.drop_table("transport_supply_snapshots")
    op.drop_table("h3_demand_cells")
    op.drop_table("crowd_forecasts")
    op.drop_table("agent_executions")
    op.drop_table("orchestrator_sessions")
    op.drop_table("events")
    op.drop_table("venues")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS postgis;")
