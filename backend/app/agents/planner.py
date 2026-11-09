"""
Agent 5 — Planner Agent (central reasoning).

Integrates outputs from all parallel agents, compares strategy options,
and produces a single coordinated action plan for human approval.

Task type: strategic_planning (watsonx/granite primary — highest reasoning quality)

IMPORTANT: This plan is NOT executed until a human officer approves it.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.seed.constants import AGENT_PROMPT_TEMPLATES


class PlannerAgent(BaseAgent):
    agent_id = "planner"
    task_type = "strategic_planning"

    async def run(
        self,
        input_data: dict[str, Any],
        db: AsyncSession,
        *,
        exec_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Produce integrated action plan from all parallel agent outputs.

        Input keys (aggregated from EventIntelligence + EgressForecast + Supply + Police):
            event_intelligence, egress_forecast, supply, police_coordination,
            historical_context

        Output keys:
            strategies_considered, recommended_strategy, metro_actions,
            bmtc_actions, auto_actions, police_actions, risk_assessment,
            confidence_score, summary, llm_fallback, data_source
        """
        ei = input_data.get("event_intelligence", {})
        ef = input_data.get("egress_forecast", {})
        sup = input_data.get("supply", {})
        pol = input_data.get("police_coordination", {})
        historical_context = ei.get("historical_context", "No historical data.")

        # Build condensed assessment for LLM
        assessment_summary = (
            f"EVENT: {ei.get('event_name', 'IPL Match')}, "
            f"attendance={ei.get('attendance', 30000):,}, "
            f"risk={ei.get('risk_level', 'HIGH')}.\n"
            f"FORECAST: T+20 demand={ef.get('total_demand_20', 0):,}, "
            f"T+40 demand={ef.get('total_demand_40', 0):,}, "
            f"severity={ef.get('severity', 'HIGH')}.\n"
            f"SUPPLY: adequacy={sup.get('adequacy_rating', 'STRAINED')}, "
            f"gap_20={sup.get('overall_gap_20', 0):,}, "
            f"priority_mode={sup.get('priority_mode', 'METRO')}.\n"
            f"TRAFFIC: critical_roads={pol.get('critical_roads', [])}, "
            f"clearance={pol.get('estimated_clearance_minutes', 45)}min.\n"
            f"SUPPLY ACTIONS: {sup.get('deployment_actions', [])}\n"
            f"POLICE DEPLOYMENTS: {pol.get('deployment_zones', [])}"
        )

        prompt = AGENT_PROMPT_TEMPLATES["planner"].format(
            assessment_summary=assessment_summary,
            historical_context=historical_context,
        )

        strategies = [
            "Strategy A: Metro-first — maximize Metro surge first, BMTC as secondary",
            "Strategy B: Balanced — equal Metro + BMTC deployment, staggered gate releases",
            "Strategy C: Gate-stagger — focus on gate sequencing to reduce peak density",
        ]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are the senior planning agent for a city-scale event management system. "
                    "Produce a comprehensive action plan. Respond with a single JSON object only — no markdown. "
                    "Keys:\n"
                    "  strategies_considered: list of {strategy_id, name, pros, cons}\n"
                    "  recommended_strategy: {strategy_id, name, rationale}\n"
                    "  metro_actions: list of strings\n"
                    "  bmtc_actions: list of strings\n"
                    "  auto_actions: list of strings\n"
                    "  police_actions: list of strings\n"
                    "  gate_release_sequence: list of {gate_id, delay_minutes}\n"
                    "  risk_assessment: {overall_risk, top_risks: list, mitigations: list}\n"
                    "  confidence_score: float 0-1\n"
                    "  summary: string\n"
                    "IMPORTANT: This plan will be reviewed by a human officer before execution."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    f"Strategies to consider:\n" + "\n".join(strategies) + "\n\n"
                    f"Historical context:\n{historical_context}\n\n"
                    "Produce the integrated action plan JSON."
                ),
            },
        ]

        llm_fallback = False
        plan: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id, max_tokens=3000
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            plan = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            plan = self._default_plan(ei, ef, sup, pol)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "strategies_considered": plan.get("strategies_considered", []),
            "recommended_strategy": plan.get("recommended_strategy", {}),
            "metro_actions": plan.get("metro_actions", sup.get("metro_actions", [])),
            "bmtc_actions": plan.get("bmtc_actions", sup.get("bmtc_actions", [])),
            "auto_actions": plan.get("auto_actions", sup.get("auto_actions", [])),
            "police_actions": plan.get("police_actions", pol.get("deployment_zones", [])),
            "gate_release_sequence": plan.get("gate_release_sequence", [
                {"gate_id": "A", "delay_minutes": 0},
                {"gate_id": "B", "delay_minutes": 0},
                {"gate_id": "C", "delay_minutes": 5},
                {"gate_id": "D", "delay_minutes": 5},
                {"gate_id": "E", "delay_minutes": 10},
            ]),
            "risk_assessment": plan.get("risk_assessment", {}),
            "confidence_score": float(plan.get("confidence_score", 0.78)),
            "summary": plan.get("summary", ""),
            "requires_human_approval": True,
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_plan(
        self, ei: dict, ef: dict, sup: dict, pol: dict
    ) -> dict:
        attendance = ei.get("attendance", 30000)
        gap = sup.get("overall_gap_20", 0)

        return {
            "strategies_considered": [
                {
                    "strategy_id": "A",
                    "name": "Metro-first",
                    "pros": ["Highest capacity per vehicle", "Reduced road congestion"],
                    "cons": ["Platform crowding risk", "Limited last-mile connectivity"],
                },
                {
                    "strategy_id": "B",
                    "name": "Balanced multi-modal",
                    "pros": ["Distributes crowd across modes", "Reduces single-point pressure"],
                    "cons": ["More complex coordination"],
                },
            ],
            "recommended_strategy": {
                "strategy_id": "B",
                "name": "Balanced multi-modal with staggered gate release",
                "rationale": (
                    "Given simultaneous demand at T+20, balancing Metro + BMTC "
                    "with staggered gate releases reduces peak density by ~40%."
                ),
            },
            "metro_actions": sup.get("metro_actions", [
                "Activate Purple Line surge: 6 trains/hour",
                "Activate Green Line surge: 4 trains/hour",
            ]),
            "bmtc_actions": sup.get("bmtc_actions", [
                "Deploy 6 surge buses at KG Road",
                "Deploy 4 surge buses at MG Road Junction",
            ]),
            "auto_actions": sup.get("auto_actions", [
                "Direct autos to South Gate pickup zone",
            ]),
            "police_actions": [
                "Deploy 6 personnel at MG Road / Kasturba Junction",
                "Deploy 4 personnel at North Gate — Cubbon Road",
                "Close inbound Kasturba Road from T+10 to T+35",
            ],
            "gate_release_sequence": [
                {"gate_id": "A", "delay_minutes": 0},
                {"gate_id": "B", "delay_minutes": 0},
                {"gate_id": "C", "delay_minutes": 5},
                {"gate_id": "D", "delay_minutes": 5},
                {"gate_id": "E", "delay_minutes": 10},
            ],
            "risk_assessment": {
                "overall_risk": ei.get("risk_level", "HIGH"),
                "top_risks": [
                    "MG Road HIGH congestion during T+10 to T+30",
                    f"Transport gap of {gap:,} persons at T+20",
                    "Metro platform crowding if surge not activated in time",
                ],
                "mitigations": [
                    "Pre-activate Metro surge 30 minutes before event end",
                    "Position BMTC buses 20 minutes before event end",
                    "Police deployment at MG Road from T-5",
                ],
            },
            "confidence_score": 0.78,
            "summary": (
                f"Balanced multi-modal plan for {attendance:,} attendance. "
                f"Estimated clearance: {pol.get('estimated_clearance_minutes', 45)} minutes. "
                "Requires human officer approval before execution."
            ),
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "strategies_considered": [],
            "recommended_strategy": {
                "strategy_id": "B",
                "name": "Balanced multi-modal (fallback)",
                "rationale": "Default plan — LLM unavailable.",
            },
            "metro_actions": ["Activate surge services"],
            "bmtc_actions": ["Pre-position buses at KG Road"],
            "auto_actions": ["Direct autos to South Gate"],
            "police_actions": ["Standard deployment protocol"],
            "gate_release_sequence": [],
            "risk_assessment": {},
            "confidence_score": 0.60,
            "summary": f"Fallback plan: {reason}",
            "requires_human_approval": True,
        })
        return base
