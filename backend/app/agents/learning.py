"""
Agent 7 — Learning Agent.

Compares predicted outcomes with actual/simulated post-event data,
computes error metrics, extracts lessons, and stores them in ChromaDB
for future RAG retrieval.

Task type: structured_extraction (watsonx/granite primary)

Write permission to history_server is restricted to this agent only.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.mcp_servers import history_server
from app.seed.constants import AGENT_PROMPT_TEMPLATES


class LearningAgent(BaseAgent):
    agent_id = "learning"
    task_type = "structured_extraction"

    async def run(
        self,
        input_data: dict[str, Any],
        db: AsyncSession,
        *,
        exec_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Evaluate prediction accuracy and store lessons in ChromaDB.

        Input keys:
            planner: {confidence_score, summary},
            egress_forecast: {total_demand_20, total_demand_40, confidence},
            supply: {adequacy_rating, overall_gap_20},
            police_coordination: {estimated_clearance_minutes},
            event_intelligence: {event_name, attendance, risk_level}

        Output keys:
            accuracy_metrics, lessons_learned, model_drift_flags,
            stored_in_chroma, llm_analysis, llm_fallback, data_source
        """
        planner = input_data.get("planner", {})
        ef = input_data.get("egress_forecast", {})
        sup = input_data.get("supply", {})
        pol = input_data.get("police_coordination", {})
        ei = input_data.get("event_intelligence", {})

        event_name = ei.get("event_name", "IPL Match")
        attendance = int(ei.get("attendance", 30000))

        # ── Simulated "actual" outcomes (post-event simulation) ───────────
        # In production these would come from real post-event telemetry.
        # Here we apply a ±10% variation to predicted values to simulate
        # realistic error for the learning pipeline.
        predicted_demand_20 = ef.get("total_demand_20", 18000)
        predicted_clearance = pol.get("estimated_clearance_minutes", 45)
        predicted_confidence = float(planner.get("confidence_score", 0.78))

        actual_demand_20 = int(predicted_demand_20 * 0.92)   # simulated: 8% less than predicted
        actual_clearance = int(predicted_clearance * 1.05)    # simulated: 5% longer

        demand_error_pct = abs(actual_demand_20 - predicted_demand_20) / max(predicted_demand_20, 1) * 100
        clearance_error_pct = abs(actual_clearance - predicted_clearance) / max(predicted_clearance, 1) * 100

        transport_adequacy = "ADEQUATE" if sup.get("overall_gap_20", 0) < 5000 else "INADEQUATE"

        accuracy_metrics = {
            "predicted_demand_20": predicted_demand_20,
            "actual_demand_20": actual_demand_20,
            "demand_error_pct": round(demand_error_pct, 1),
            "predicted_clearance_minutes": predicted_clearance,
            "actual_clearance_minutes": actual_clearance,
            "clearance_error_pct": round(clearance_error_pct, 1),
            "confidence_score": predicted_confidence,
            "transport_adequacy": transport_adequacy,
            "data_source": "SIMULATED",
        }

        predicted_summary = (
            f"Predicted: demand_20={predicted_demand_20:,}, "
            f"clearance={predicted_clearance}min, "
            f"adequacy={sup.get('adequacy_rating', 'STRAINED')}"
        )
        actual_summary = (
            f"Actual: demand_20={actual_demand_20:,}, "
            f"clearance={actual_clearance}min, "
            f"adequacy={transport_adequacy}"
        )

        prompt = AGENT_PROMPT_TEMPLATES["learning"].format(
            predicted=predicted_summary,
            actual=actual_summary,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a post-event learning analyst. Respond with a single JSON object only. "
                    "Keys: lessons_learned (list of strings), "
                    "model_improvements (list of strings), "
                    "accuracy_grade (A/B/C/D), "
                    "drift_detected (boolean), "
                    "summary (string)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    f"Event: {event_name} (attendance={attendance:,})\n"
                    f"{predicted_summary}\n{actual_summary}\n"
                    f"Demand error: {demand_error_pct:.1f}%\n"
                    f"Clearance error: {clearance_error_pct:.1f}%\n\n"
                    "Extract lessons and grade model accuracy."
                ),
            },
        ]

        llm_fallback = False
        llm_analysis: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            llm_analysis = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            llm_analysis = self._default_analysis(demand_error_pct, clearance_error_pct)

        # ── Store in ChromaDB (learning agent has exclusive write access) ─
        outcome = {
            "event_name": event_name,
            "actual_attendance": attendance,
            "actual_exit_duration_mins": actual_clearance,
            "transport_adequacy": transport_adequacy,
            "demand_error_pct": round(demand_error_pct, 1),
            "lessons_learned": "; ".join(llm_analysis.get("lessons_learned", [])),
            "accuracy_grade": llm_analysis.get("accuracy_grade", "B"),
            "data_source": "SIMULATED",
        }

        stored_in_chroma = False
        chroma_error: str | None = None
        try:
            history_server.store_event_outcome(
                event_id=event_id,
                outcome=outcome,
                calling_agent="learning",
            )
            stored_in_chroma = True
        except Exception as exc:
            chroma_error = str(exc)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "accuracy_metrics": accuracy_metrics,
            "lessons_learned": llm_analysis.get("lessons_learned", []),
            "model_improvements": llm_analysis.get("model_improvements", []),
            "accuracy_grade": llm_analysis.get("accuracy_grade", "B"),
            "drift_detected": llm_analysis.get("drift_detected", False),
            "model_drift_flags": ["demand_over_prediction"] if demand_error_pct > 10 else [],
            "stored_in_chroma": stored_in_chroma,
            "chroma_error": chroma_error,
            "llm_analysis": llm_analysis,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_analysis(self, demand_err: float, clearance_err: float) -> dict:
        grade = "A" if demand_err < 5 else "B" if demand_err < 10 else "C" if demand_err < 20 else "D"
        return {
            "lessons_learned": [
                f"Demand prediction error: {demand_err:.1f}% — model slightly over-predicted egress speed.",
                "Metro surge activation proved adequate for first 20 minutes.",
                "Staggered gate release reduced peak density at MG Road junction.",
                "Auto supply depleted faster than predicted — increase base count estimate.",
            ],
            "model_improvements": [
                "Increase patient-fan fraction from 25% to 30% for cricket finals.",
                "Add weather correction factor for hot days (attendance leaving early).",
                "Calibrate auto decay rate using actual GPS data when available.",
            ],
            "accuracy_grade": grade,
            "drift_detected": demand_err > 15,
            "summary": (
                f"Deterministic fallback: demand error={demand_err:.1f}%, "
                f"clearance error={clearance_err:.1f}%. Grade: {grade}."
            ),
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "accuracy_metrics": {},
            "lessons_learned": [],
            "model_improvements": [],
            "accuracy_grade": "B",
            "drift_detected": False,
            "model_drift_flags": [],
            "stored_in_chroma": False,
            "chroma_error": reason,
            "llm_analysis": {},
        })
        return base
