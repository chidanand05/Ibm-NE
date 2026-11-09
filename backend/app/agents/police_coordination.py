"""
Agent 4 — Police Coordination Agent.

Runs traffic congestion simulation, maps hotspots to H3 cells,
and recommends traffic management deployment actions.

Task type: structured_extraction (watsonx/granite primary)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.seed.constants import AGENT_PROMPT_TEMPLATES
from app.simulator.traffic import simulate_congestion


class PoliceCoordinationAgent(BaseAgent):
    agent_id = "police_coordination"
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
        Assess traffic congestion and recommend police deployments.

        Input keys:
            event_id, attendance (from EventIntelligence)

        Output keys:
            congestion_points, critical_roads, hotspot_h3_cells,
            police_deployments, diversion_routes,
            llm_recommendations, llm_fallback, data_source
        """
        # ── Run traffic simulation ────────────────────────────────────────
        traffic = simulate_congestion(event_id=event_id, horizon_minutes=60)

        critical_roads = traffic.critical_roads
        congestion_summary = (
            f"Critical roads: {', '.join(critical_roads) or 'None'}. "
            f"Total congestion points: {len(traffic.congestion_points)}. "
            "All data SIMULATED."
        )

        # Detailed per-road info for the LLM
        road_details = "\n".join(
            f"  - {p.name}: {p.congestion_level} (peak at T+{p.peak_minute}min, "
            f"diversion: {p.recommended_diversion})"
            for p in traffic.congestion_points
        )

        prompt = AGENT_PROMPT_TEMPLATES["police_coordination"].format(
            congestion_summary=congestion_summary,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a traffic management expert. Respond with a single JSON object only. "
                    "Keys: deployment_zones (list of {location, personnel_count, role}), "
                    "diversion_routes (list of strings), "
                    "gate_sequence (list of gate IDs in release order), "
                    "estimated_clearance_minutes (integer), "
                    "summary (string)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\nRoad conditions:\n{road_details}\n\n"
                    f"Critical roads requiring police presence:\n"
                    + "\n".join(f"  - {r}" for r in critical_roads)
                    + "\n\nProduce police deployment JSON."
                ),
            },
        ]

        llm_fallback = False
        llm_recommendations: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            llm_recommendations = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            llm_recommendations = self._default_deployments(critical_roads)

        hotspot_h3_cells = [
            p.h3_id for p in traffic.congestion_points
            if p.congestion_level in ("HIGH", "CRITICAL")
        ]

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "congestion_points": [p.model_dump() for p in traffic.congestion_points],
            "critical_roads": critical_roads,
            "hotspot_h3_cells": hotspot_h3_cells,
            "deployment_zones": llm_recommendations.get("deployment_zones", []),
            "diversion_routes": llm_recommendations.get("diversion_routes", []),
            "gate_sequence": llm_recommendations.get("gate_sequence", ["A", "B", "C", "D", "E"]),
            "estimated_clearance_minutes": llm_recommendations.get("estimated_clearance_minutes", 45),
            "police_deployments": llm_recommendations.get("deployment_zones", []),
            "llm_recommendations": llm_recommendations,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_deployments(self, critical_roads: list[str]) -> dict:
        return {
            "deployment_zones": [
                {
                    "location": "MG Road / Kasturba Road Junction",
                    "personnel_count": 6,
                    "role": "Traffic signal override + diversion",
                },
                {
                    "location": "North Gate exit — Cubbon Road",
                    "personnel_count": 4,
                    "role": "Pedestrian flow management",
                },
                {
                    "location": "South Gate — KG Road BMTC stop",
                    "personnel_count": 4,
                    "role": "Bus boarding queue control",
                },
                {
                    "location": "MG Road Metro Station entrance",
                    "personnel_count": 3,
                    "role": "Platform crowd control",
                },
            ],
            "diversion_routes": [
                "Redirect MG Road traffic via Residency Road (southbound)",
                "Close inbound Kasturba Road from T+10 to T+35",
                "Open Raj Bhavan Road as alternate egress corridor",
            ],
            "gate_sequence": ["A", "B", "C", "D", "E"],
            "estimated_clearance_minutes": 45,
            "summary": (
                "Deterministic fallback: deploy 17 personnel across 4 zones. "
                f"Critical roads: {', '.join(critical_roads) or 'none'}."
            ),
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "congestion_points": [],
            "critical_roads": ["MG Road", "Kasturba Road"],
            "hotspot_h3_cells": [],
            "deployment_zones": [],
            "diversion_routes": [],
            "gate_sequence": ["A", "B", "C", "D", "E"],
            "estimated_clearance_minutes": 45,
            "police_deployments": [],
            "llm_recommendations": {},
        })
        return base
