"""
BaseAgent — shared base class for all Namma Exodus agents.

Each agent inherits from BaseAgent and implements `run()`.

Pattern
-------
1. Save AgentExecution row with status=RUNNING.
2. Call LLMClient.complete() with task_type routing.
3. On LLMGatewayError or any exception → return deterministic fallback.
4. Save output_data + status=COMPLETED/FAILED.
5. Return typed output dict with `llm_fallback` flag.

All outputs carry `data_source` fields set by the simulator; agents never
invent transport numbers — they interpret simulator output.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_gateway.client import LLMClient, LLMGatewayError, get_llm_client
from app.models.db.agent_execution import AgentExecution

log = structlog.get_logger(__name__)


class BaseAgent:
    """
    Abstract base for all seven Namma Exodus agents.

    Subclasses must implement `run()` and set:
      - `agent_id`  : stable string key e.g. "event_intelligence"
      - `task_type` : LLM router task type e.g. "structured_extraction"
    """

    agent_id: str = "base"
    task_type: str = "structured_extraction"
    agent_version: str = "1.0"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or get_llm_client()

    # ── LLM helper ────────────────────────────────────────────────────────────

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        db: AsyncSession,
        *,
        agent_exec_id: str | None = None,
        event_id: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """
        Call the LLM gateway. Returns content string.
        Raises LLMGatewayError if all providers fail.
        """
        result = await self._llm.complete(
            task_type=self.task_type,
            messages=messages,
            db=db,
            agent_exec_id=agent_exec_id,
            event_id=event_id,
            max_tokens=max_tokens,
        )
        return result.content

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _create_execution(
        self,
        db: AsyncSession,
        event_id: str,
        session_id: str,
        input_data: dict,
    ) -> AgentExecution:
        """Insert an AgentExecution row with status=RUNNING."""
        exec_id = str(uuid.uuid4())
        row = AgentExecution(
            id=exec_id,
            event_id=event_id,
            session_id=session_id,
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            status="RUNNING",
            started_at=datetime.now(tz=timezone.utc),
            input_data=input_data,
        )
        db.add(row)
        await db.flush()
        return row

    async def _finish_execution(
        self,
        db: AsyncSession,
        row: AgentExecution,
        output_data: dict,
        started_ms: float,
        model_used: str | None = None,
        total_tokens: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update the AgentExecution row to COMPLETED or FAILED."""
        row.status = "FAILED" if error_message else "COMPLETED"
        row.completed_at = datetime.now(tz=timezone.utc)
        row.duration_ms = int((time.monotonic() - started_ms) * 1000)
        row.output_data = output_data
        row.model_used = model_used
        row.total_tokens = total_tokens
        row.error_message = error_message
        await db.flush()

    # ── Public interface ──────────────────────────────────────────────────────

    async def execute(
        self,
        input_data: dict[str, Any],
        db: AsyncSession,
        session_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Main entry point called by the orchestrator.

        Creates the DB execution record, calls run(), persists the result.
        Always returns a dict — never raises to the orchestrator.
        """
        t0 = time.monotonic()
        row = await self._create_execution(db, event_id, session_id, input_data)
        log.info("agent.started", agent=self.agent_id, exec_id=row.id, event_id=event_id)

        try:
            output = await self.run(input_data, db, exec_id=row.id, event_id=event_id)
            await self._finish_execution(db, row, output, t0)
            log.info("agent.completed", agent=self.agent_id, exec_id=row.id,
                     llm_fallback=output.get("llm_fallback", False))
            output["exec_id"] = row.id
            return output

        except Exception as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            log.error("agent.failed", agent=self.agent_id, exec_id=row.id, error=err_msg)
            fallback = self._fallback_output(input_data, reason=err_msg)
            fallback["exec_id"] = row.id
            await self._finish_execution(db, row, fallback, t0, error_message=err_msg)
            return fallback

    async def run(
        self,
        input_data: dict[str, Any],
        db: AsyncSession,
        *,
        exec_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """Override in subclass. Must return a dict."""
        raise NotImplementedError

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        """
        Deterministic fallback when LLM is unavailable.
        Subclasses should override to return typed defaults.
        """
        return {
            "llm_fallback": True,
            "fallback_reason": reason,
            "agent_id": self.agent_id,
            "data_source": "SIMULATED",
        }
