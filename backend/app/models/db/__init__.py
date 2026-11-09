"""Import all ORM models so SQLAlchemy metadata is fully populated.

Alembic's env.py imports this module to discover all tables.
Order matters for circular-reference avoidance: define parent tables first.
"""

from app.models.db.base import Base  # noqa: F401
from app.models.db.user import User  # noqa: F401
from app.models.db.venue import Venue  # noqa: F401
from app.models.db.event import Event  # noqa: F401
from app.models.db.orchestrator_session import OrchestratorSession  # noqa: F401
from app.models.db.agent_execution import AgentExecution  # noqa: F401
from app.models.db.crowd_forecast import CrowdForecast  # noqa: F401
from app.models.db.h3_demand_cell import H3DemandCell  # noqa: F401
from app.models.db.transport_supply_snapshot import TransportSupplySnapshot  # noqa: F401
from app.models.db.agent_message import AgentMessage  # noqa: F401
from app.models.db.action_plan import ActionPlan  # noqa: F401
from app.models.db.action_plan_approval import ActionPlanApproval  # noqa: F401
from app.models.db.historical_outcome import HistoricalOutcome  # noqa: F401
from app.models.db.audit_log import AuditLog  # noqa: F401
from app.models.db.llm_usage import LLMUsage  # noqa: F401
from app.models.db.model_config import ModelConfig  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Venue",
    "Event",
    "OrchestratorSession",
    "AgentExecution",
    "CrowdForecast",
    "H3DemandCell",
    "TransportSupplySnapshot",
    "AgentMessage",
    "ActionPlan",
    "ActionPlanApproval",
    "HistoricalOutcome",
    "AuditLog",
    "LLMUsage",
    "ModelConfig",
]
