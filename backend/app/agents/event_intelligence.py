"""
Agent 1 — Event Intelligence Agent.

Retrieves event metadata, queries ChromaDB for similar past events,
and produces a structured event assessment.

Task type: structured_extraction (watsonx/granite primary)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.mcp_servers import history_server
from app.seed.constants import (
    AGENT_PROMPT_TEMPLATES,
    CHINNASWAMY_GATES,
    CHINNASWAMY_LAT,
    CHINNASWAMY_LON,
    CHINNASWAMY_VENUE_ID,
)


class EventIntelligenceAgent(BaseAgent):
    agent_id = "event_intelligence"
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
        Analyze event context and retrieve similar historical events.

        Input keys:
            event_id, event_name, attendance, venue_name (optional)

        Output keys:
            risk_level, crowd_category, similar_events, historical_context,
            venue_context, llm_analysis, llm_fallback, data_source
        """
        attendance = int(input_data.get("attendance", 30000))
        event_name = input_data.get("event_name", "IPL Match")

        # ── ChromaDB RAG retrieval ─────────────────────────────────────────
        query = f"{event_name} attendance {attendance} M. Chinnaswamy Stadium Bengaluru"
        similar_events = history_server.retrieve_similar_events(query, top_k=3)
        historical_context = "\n".join(
            f"- {e['document']}" for e in similar_events
        ) or "No historical records available."

        # ── LLM analysis ─────────────────────────────────────────────────
        prompt = AGENT_PROMPT_TEMPLATES["event_intelligence"].format(
            event_id=event_id,
            historical_context=historical_context,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert event intelligence analyst. "
                    "Respond with a single JSON object only — no markdown, no explanation. "
                    "Keys: risk_level (LOW/MEDIUM/HIGH/CRITICAL), crowd_category (NORMAL/LARGE/MEGA), "
                    "key_risks (list of strings), recommendations (list of strings), summary (string)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\nEvent details:\n"
                    f"- Name: {event_name}\n"
                    f"- Attendance: {attendance:,}\n"
                    f"- Venue: M. Chinnaswamy Stadium, Bengaluru\n"
                    f"- Gates: {len(CHINNASWAMY_GATES)}\n\n"
                    f"Historical context:\n{historical_context}\n\n"
                    "Produce structured JSON assessment."
                ),
            },
        ]

        llm_fallback = False
        llm_analysis: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id
            )
            # Parse JSON — strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            llm_analysis = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            llm_analysis = self._default_analysis(attendance)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "event_name": event_name,
            "attendance": attendance,
            "venue_id": CHINNASWAMY_VENUE_ID,
            "venue_lat": CHINNASWAMY_LAT,
            "venue_lon": CHINNASWAMY_LON,
            "gates": CHINNASWAMY_GATES,
            "risk_level": llm_analysis.get("risk_level", "HIGH"),
            "crowd_category": llm_analysis.get("crowd_category", "LARGE"),
            "key_risks": llm_analysis.get("key_risks", []),
            "recommendations": llm_analysis.get("recommendations", []),
            "summary": llm_analysis.get("summary", ""),
            "similar_events": similar_events,
            "historical_context": historical_context,
            "llm_analysis": llm_analysis,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_analysis(self, attendance: int) -> dict:
        if attendance >= 35000:
            risk_level = "CRITICAL"
            crowd_category = "MEGA"
        elif attendance >= 25000:
            risk_level = "HIGH"
            crowd_category = "LARGE"
        else:
            risk_level = "MEDIUM"
            crowd_category = "NORMAL"

        return {
            "risk_level": risk_level,
            "crowd_category": crowd_category,
            "key_risks": [
                "MG Road congestion expected at T+15",
                "Metro platform crowding near capacity",
                "Auto supply insufficient for demand spike",
            ],
            "recommendations": [
                "Activate surge metro services",
                "Pre-position BMTC buses at KG Road",
                "Stagger gate releases by 5-minute intervals",
            ],
            "summary": (
                f"Event with {attendance:,} attendance at M. Chinnaswamy Stadium. "
                f"Risk level: {risk_level}. Deterministic fallback assessment."
            ),
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        attendance = int(input_data.get("attendance", 30000))
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "event_name": input_data.get("event_name", "IPL Match"),
            "attendance": attendance,
            "venue_id": CHINNASWAMY_VENUE_ID,
            "venue_lat": CHINNASWAMY_LAT,
            "venue_lon": CHINNASWAMY_LON,
            "gates": CHINNASWAMY_GATES,
            "risk_level": "HIGH",
            "crowd_category": "LARGE",
            "key_risks": ["Agent execution error — using fallback assessment"],
            "recommendations": ["Activate all standard surge protocols"],
            "summary": f"Fallback assessment: {reason}",
            "similar_events": [],
            "historical_context": "",
            "llm_analysis": {},
        })
        return base
