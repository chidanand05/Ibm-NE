"""
Agent 2 — Egress Forecast Agent.

Runs the crowd simulation engine, interprets results with LLM,
and produces a structured egress forecast with confidence intervals.

Task type: structured_extraction (watsonx/granite primary)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.seed.constants import AGENT_PROMPT_TEMPLATES
from app.simulator.crowd import simulate_crowd_exit


class EgressForecastAgent(BaseAgent):
    agent_id = "egress_forecast"
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
        Run crowd simulation and produce egress forecast.

        Input keys (from EventIntelligence output):
            event_id, attendance, venue_lat, venue_lon, gates

        Output keys:
            sim_20min, sim_40min, peak_zone_h3, total_demand_20,
            total_demand_40, gate_flows, h3_cells_20, h3_cells_40,
            exit_wave, llm_interpretation, llm_fallback, data_source
        """
        attendance = int(input_data.get("attendance", 30000))
        venue_lat = float(input_data.get("venue_lat", 12.9789))
        venue_lon = float(input_data.get("venue_lon", 77.5996))
        gates = input_data.get("gates", [])
        event_name = input_data.get("event_name", "IPL Match")

        # ── Run crowd simulation (no LLM — pure physics) ──────────────────
        sim_20 = simulate_crowd_exit(
            event_id=event_id,
            t_plus_minutes=20,
            attendance=attendance,
            venue_lat=venue_lat,
            venue_lon=venue_lon,
            gates=gates,
        )
        sim_40 = simulate_crowd_exit(
            event_id=event_id,
            t_plus_minutes=40,
            attendance=attendance,
            venue_lat=venue_lat,
            venue_lon=venue_lon,
            gates=gates,
        )

        # Serialize for LLM context
        forecast_summary = (
            f"T+20min: {sim_20.total_demand:,} people outside venue, "
            f"{sim_20.remaining_in_venue:,} still inside. "
            f"Peak H3 zone: {sim_20.peak_zone_h3}. "
            f"T+40min: {sim_40.total_demand:,} people outside, "
            f"{sim_40.remaining_in_venue:,} still inside. "
            f"Confidence: {sim_20.confidence:.0%}. Data: SIMULATED."
        )

        # ── LLM interpretation ────────────────────────────────────────────
        prompt = AGENT_PROMPT_TEMPLATES["egress_forecast"].format(
            event_name=event_name,
            attendance=attendance,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a crowd-flow analyst. Interpret simulation data and respond "
                    "with a single JSON object only — no markdown. "
                    "Keys: severity (LOW/MEDIUM/HIGH/CRITICAL), "
                    "peak_period (string describing peak exit window), "
                    "bottlenecks (list of strings), "
                    "stagger_recommendation (string), "
                    "summary (string)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\nSimulation results:\n{forecast_summary}\n\n"
                    f"Gate breakdown at T+20:\n"
                    + "\n".join(
                        f"  - {g.gate_name}: {g.cumulative_exited_20min:,} exited, "
                        f"peak {g.persons_per_minute_peak}/min"
                        for g in sim_20.gate_flows
                    )
                    + "\n\nProduce structured interpretation JSON."
                ),
            },
        ]

        llm_fallback = False
        llm_interpretation: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            llm_interpretation = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            llm_interpretation = self._default_interpretation(sim_20, sim_40)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "attendance": attendance,
            "sim_20min": sim_20.model_dump(),
            "sim_40min": sim_40.model_dump(),
            "peak_zone_h3": sim_20.peak_zone_h3,
            "total_demand_20": sim_20.total_demand,
            "total_demand_40": sim_40.total_demand,
            "gate_flows": [g.model_dump() for g in sim_20.gate_flows],
            "h3_cells_20": [c.model_dump() for c in sim_20.h3_cells],
            "h3_cells_40": [c.model_dump() for c in sim_40.h3_cells],
            "exit_wave": [p.model_dump() for p in sim_20.exit_wave],
            "confidence": sim_20.confidence,
            "severity": llm_interpretation.get("severity", "HIGH"),
            "peak_period": llm_interpretation.get("peak_period", "T+10 to T+25"),
            "bottlenecks": llm_interpretation.get("bottlenecks", []),
            "stagger_recommendation": llm_interpretation.get("stagger_recommendation", ""),
            "llm_interpretation": llm_interpretation,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_interpretation(self, sim_20: Any, sim_40: Any) -> dict:
        demand_20 = sim_20.total_demand
        if demand_20 > 20000:
            severity = "CRITICAL"
        elif demand_20 > 12000:
            severity = "HIGH"
        elif demand_20 > 6000:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return {
            "severity": severity,
            "peak_period": "T+10 to T+25 minutes after event end",
            "bottlenecks": [
                "MG Road junction — predicted HIGH congestion at T+15",
                "Kasturba Road toward Metro — MEDIUM congestion",
                "North Gate pressure — highest single-gate volume",
            ],
            "stagger_recommendation": (
                "Release gates A and B first at T+0, then C and D at T+5, "
                "then VIP Gate E at T+10 to prevent simultaneous surge."
            ),
            "summary": (
                f"Deterministic fallback: {demand_20:,} people need transport at T+20. "
                f"Severity: {severity}."
            ),
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "attendance": int(input_data.get("attendance", 30000)),
            "peak_zone_h3": "",
            "total_demand_20": 18000,
            "total_demand_40": 27000,
            "gate_flows": [],
            "h3_cells_20": [],
            "h3_cells_40": [],
            "exit_wave": [],
            "confidence": 0.82,
            "severity": "HIGH",
            "sim_20min": {},
            "sim_40min": {},
            "llm_interpretation": {},
        })
        return base
