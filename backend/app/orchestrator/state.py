"""
ExodusState — LangGraph state TypedDict for the Namma Exodus orchestrator.

All nodes read from and write to this shared state object.
LangGraph merges state between nodes using the Annotated reducer pattern.
"""

from __future__ import annotations

from typing import Annotated, Any

from typing_extensions import TypedDict


def _merge_dict(a: dict | None, b: dict | None) -> dict:
    """Merge two dicts; b overrides a. None-safe."""
    result = dict(a or {})
    result.update(b or {})
    return result


def _last(a: Any, b: Any) -> Any:
    """Last-write-wins reducer — most fields use this."""
    return b if b is not None else a


class ExodusState(TypedDict, total=False):
    """
    Shared state for the Exodus LangGraph pipeline.

    Annotated[T, reducer] fields are merged by LangGraph when multiple nodes
    write to them concurrently (e.g. the parallel agent trio).
    """

    # ── Session context (set by runner before graph start) ────────────────
    session_id: Annotated[str, _last]
    event_id: Annotated[str, _last]
    trigger_type: Annotated[str, _last]           # MANUAL | REPLAY | SCHEDULED

    # ── Event inputs ──────────────────────────────────────────────────────
    event_name: Annotated[str, _last]
    attendance: Annotated[int, _last]
    venue_lat: Annotated[float, _last]
    venue_lon: Annotated[float, _last]
    gates: Annotated[list, _last]

    # ── Agent outputs ─────────────────────────────────────────────────────
    event_intelligence: Annotated[dict, _merge_dict]
    egress_forecast: Annotated[dict, _merge_dict]
    supply: Annotated[dict, _merge_dict]
    police_coordination: Annotated[dict, _merge_dict]
    planner: Annotated[dict, _merge_dict]
    citizen_guidance: Annotated[dict, _merge_dict]
    learning: Annotated[dict, _merge_dict]

    # ── Approval workflow ─────────────────────────────────────────────────
    plan_id: Annotated[str | None, _last]
    approval_status: Annotated[str | None, _last]   # PENDING_APPROVAL | APPROVED | REJECTED
    approval_decision: Annotated[str | None, _last]  # APPROVED | REJECTED
    approval_comments: Annotated[str | None, _last]
    approved_by: Annotated[str | None, _last]

    # ── Pipeline control ──────────────────────────────────────────────────
    current_phase: Annotated[str, _last]            # event_intel | parallel | planner | approval | guidance | learning | done
    error_message: Annotated[str | None, _last]
    completed: Annotated[bool, _last]
    pipeline_version: Annotated[str, _last]

    # ── Decision engine output ────────────────────────────────────────────
    decision_score: Annotated[float | None, _last]
    decision_label: Annotated[str | None, _last]    # GREEN | AMBER | RED | CRITICAL
