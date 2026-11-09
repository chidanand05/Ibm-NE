"""
Agent 3 — Supply Agent.

Runs transport supply simulation, computes supply-demand gaps,
and recommends specific vehicle deployment actions.

Task type: structured_extraction (watsonx/granite primary)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.seed.constants import AGENT_PROMPT_TEMPLATES
from app.simulator.transport import get_supply_snapshot


class SupplyAgent(BaseAgent):
    agent_id = "supply"
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
        Assess transport supply against egress demand.

        Input keys (from EgressForecast output):
            event_id, attendance, total_demand_20, total_demand_40,
            venue_lat, venue_lon

        Output keys:
            supply_20, supply_40, overall_gap, gap_by_mode,
            surge_recommended, deployment_actions,
            llm_recommendations, llm_fallback, data_source
        """
        attendance = int(input_data.get("attendance", 30000))
        demand_20 = int(input_data.get("total_demand_20", 18000))
        demand_40 = int(input_data.get("total_demand_40", 27000))
        venue_lat = float(input_data.get("venue_lat", 12.9789))
        venue_lon = float(input_data.get("venue_lon", 77.5996))

        # ── Run supply simulation ─────────────────────────────────────────
        supply_20 = get_supply_snapshot(
            event_id=event_id,
            time_horizon=20,
            total_demand=demand_20,
            venue_lat=venue_lat,
            venue_lon=venue_lon,
            attendance=attendance,
            surge_active=True,
        )
        supply_40 = get_supply_snapshot(
            event_id=event_id,
            time_horizon=40,
            total_demand=demand_40,
            venue_lat=venue_lat,
            venue_lon=venue_lon,
            attendance=attendance,
            surge_active=True,
        )

        gap_20 = supply_20.overall_gap
        gap_40 = supply_40.overall_gap

        forecast_summary = (
            f"T+20min demand={demand_20:,}, supply={supply_20.total_window_capacity:,}, "
            f"gap={gap_20:,}. "
            f"T+40min demand={demand_40:,}, supply={supply_40.total_window_capacity:,}, "
            f"gap={gap_40:,}. "
            f"Modes: Metro={supply_20.modes[0].window_capacity:,}, "
            f"BMTC={supply_20.modes[1].window_capacity:,}, "
            f"Auto={supply_20.modes[2].window_capacity:,}. "
            "All data SIMULATED."
        )

        # ── LLM recommendations ───────────────────────────────────────────
        prompt = AGENT_PROMPT_TEMPLATES["supply"].format(forecast_summary=forecast_summary)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a transport supply analyst. Respond with a single JSON object only. "
                    "Keys: adequacy_rating (ADEQUATE/STRAINED/INADEQUATE/CRITICAL), "
                    "metro_actions (list of strings), bmtc_actions (list of strings), "
                    "auto_actions (list of strings), priority_mode (METRO/BMTC/AUTO), "
                    "additional_vehicles_needed (integer), summary (string)."
                ),
            },
            {
                "role": "user",
                "content": f"{prompt}\n\nProduce supply assessment JSON.",
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
            llm_recommendations = self._default_recommendations(gap_20, supply_20)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "supply_20": supply_20.model_dump(),
            "supply_40": supply_40.model_dump(),
            "overall_gap_20": gap_20,
            "overall_gap_40": gap_40,
            "total_capacity_20": supply_20.total_window_capacity,
            "total_capacity_40": supply_40.total_window_capacity,
            "gap_by_mode": {
                m.mode: m.gap_persons for m in supply_20.modes
            },
            "surge_recommended": attendance >= 25000,
            "adequacy_rating": llm_recommendations.get("adequacy_rating", "STRAINED"),
            "metro_actions": llm_recommendations.get("metro_actions", []),
            "bmtc_actions": llm_recommendations.get("bmtc_actions", []),
            "auto_actions": llm_recommendations.get("auto_actions", []),
            "priority_mode": llm_recommendations.get("priority_mode", "METRO"),
            "additional_vehicles_needed": llm_recommendations.get("additional_vehicles_needed", 0),
            "deployment_actions": (
                llm_recommendations.get("metro_actions", [])
                + llm_recommendations.get("bmtc_actions", [])
                + llm_recommendations.get("auto_actions", [])
            ),
            "llm_recommendations": llm_recommendations,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_recommendations(self, gap: int, supply: Any) -> dict:
        if gap > 10000:
            rating = "CRITICAL"
        elif gap > 5000:
            rating = "INADEQUATE"
        elif gap > 0:
            rating = "STRAINED"
        else:
            rating = "ADEQUATE"

        return {
            "adequacy_rating": rating,
            "metro_actions": [
                "Activate Purple Line surge: 6 trains/hour",
                "Activate Green Line surge: 4 trains/hour",
                "Open all platform gates at MG Road station",
            ],
            "bmtc_actions": [
                "Deploy 6 surge buses at KG Road Junction",
                "Deploy 4 surge buses at MG Road Junction",
                "Activate routes 137, 201, 401, 36 on 10-min frequency",
            ],
            "auto_actions": [
                "Direct auto-rickshaws to designated pickup zones at South Gate",
                "Coordinate with Ola/Uber for surge zone pricing removal",
            ],
            "priority_mode": "METRO",
            "additional_vehicles_needed": max(0, gap // 90),
            "summary": f"Deterministic fallback: {rating} supply. Gap={gap:,}.",
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "supply_20": {},
            "supply_40": {},
            "overall_gap_20": 8000,
            "overall_gap_40": 5000,
            "total_capacity_20": 10000,
            "total_capacity_40": 22000,
            "gap_by_mode": {"METRO": 5000, "BMTC": 2000, "AUTO": 1000},
            "surge_recommended": True,
            "adequacy_rating": "STRAINED",
            "metro_actions": ["Activate surge services"],
            "bmtc_actions": ["Pre-position buses at KG Road"],
            "auto_actions": ["Direct autos to South Gate"],
            "priority_mode": "METRO",
            "additional_vehicles_needed": 10,
            "deployment_actions": [],
            "llm_recommendations": {},
        })
        return base
