"""
Agent 6 — Citizen Guidance Agent.

Generates travel instructions in English, Kannada, and Hindi
for citizens exiting the venue.

Task type: multilingual_translation (gemini/flash primary — best multilingual)

ONLY runs after human officer approves the action plan.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.llm_gateway.client import LLMGatewayError
from app.seed.constants import AGENT_PROMPT_TEMPLATES, CHINNASWAMY_GATES


# Static fallback messages — always available without LLM
_FALLBACK_MESSAGES = {
    "gate_A_english": (
        "Exit via North Gate (Gate A). Walk to MG Road Metro Station (12 min). "
        "Alternatively, take BMTC buses at KG Road Junction (5 min walk)."
    ),
    "gate_B_english": (
        "Exit via South Gate (Gate B). Auto-rickshaw pickup zone is available outside. "
        "Walk to KG Road Junction for BMTC buses (5 min)."
    ),
    "gate_C_english": (
        "Exit via East Gate (Gate C). Walk toward Cubbon Park Metro (16 min) "
        "or MG Road Metro via Kasturba Road (12 min)."
    ),
    "gate_D_english": (
        "Exit via West Gate (Gate D). Walk to MG Road Metro via Kasturba Road (12 min). "
        "BMTC buses are available at KG Road Junction."
    ),
    "gate_E_english": (
        "Exit via VIP Gate (Gate E). Dedicated pickup zone available. "
        "Metro and cab pickup at MG Road Metro Station."
    ),
    "metro_english": (
        "MG Road Metro (Purple Line) — 12 min walk north. "
        "Cubbon Park Metro (Green Line) — 16 min walk west. "
        "Surge services active: trains every 10 minutes."
    ),
    "general_kannada": (
        "ಪ್ರಯಾಣಿಕರಿಗೆ ಸೂಚನೆ: ದಯವಿಟ್ಟು ಶಾಂತವಾಗಿ ನಡೆಯಿರಿ. "
        "ಮೆಟ್ರೋ ನಿಲ್ದಾಣ: ಎಂಜಿ ರೋಡ್ (12 ನಿಮಿಷ ನಡಿಗೆ). "
        "ಬಿಎಂಟಿಸಿ ಬಸ್: ಕೆಜಿ ರೋಡ್ (5 ನಿಮಿಷ ನಡಿಗೆ)."
    ),
    "general_hindi": (
        "यात्री सूचना: कृपया शांतिपूर्वक चलें। "
        "मेट्रो स्टेशन: एमजी रोड (12 मिनट पैदल)। "
        "बीएमटीसी बस: केजी रोड (5 मिनट पैदल)।"
    ),
}


class CitizenGuidanceAgent(BaseAgent):
    agent_id = "citizen_guidance"
    task_type = "multilingual_translation"

    async def run(
        self,
        input_data: dict[str, Any],
        db: AsyncSession,
        *,
        exec_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """
        Generate gate-specific and general travel guidance in 3 languages.

        Input keys (from planner output after approval):
            planner: {gate_release_sequence, metro_actions, bmtc_actions},
            supply: {priority_mode},
            event_intelligence: {event_name}

        Output keys:
            guidance_by_gate, general_guidance, metro_instructions,
            languages, llm_fallback, data_source
        """
        planner = input_data.get("planner", {})
        supply = input_data.get("supply", {})
        event_name = input_data.get("event_intelligence", {}).get("event_name", "IPL Match")

        gate_sequence = planner.get("gate_release_sequence", [
            {"gate_id": g["gate_id"], "delay_minutes": i * 5}
            for i, g in enumerate(CHINNASWAMY_GATES)
        ])
        metro_actions = planner.get("metro_actions", ["Metro surge active"])
        bmtc_actions = planner.get("bmtc_actions", ["BMTC buses at KG Road"])
        priority_mode = supply.get("priority_mode", "METRO")

        gate_assignments = "\n".join(
            f"Gate {g['gate_id']}: opens at T+{g['delay_minutes']}min"
            for g in gate_sequence
        )
        transport_options = (
            f"Priority mode: {priority_mode}. "
            f"Metro: {'; '.join(metro_actions[:2])}. "
            f"BMTC: {'; '.join(bmtc_actions[:2])}."
        )

        prompt = AGENT_PROMPT_TEMPLATES["citizen_guidance"].format(
            gate_assignments=gate_assignments,
            transport_options=transport_options,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a multilingual citizen information system for a large public event. "
                    "Generate travel instructions in English, Kannada (ಕನ್ನಡ), and Hindi (हिंदी). "
                    "Keep instructions clear, short, and actionable. "
                    "Respond with a single JSON object only — no markdown. "
                    "Keys:\n"
                    "  by_gate: object keyed by gate_id (A/B/C/D/E), each with {english, kannada, hindi}\n"
                    "  general: {english, kannada, hindi}\n"
                    "  metro: {english, kannada, hindi}\n"
                    "  safety_message: {english, kannada, hindi}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    f"Event: {event_name}\n"
                    f"Gate schedule:\n{gate_assignments}\n"
                    f"Transport options: {transport_options}\n\n"
                    "Generate citizen guidance in all three languages."
                ),
            },
        ]

        llm_fallback = False
        guidance: dict = {}

        try:
            content = await self._call_llm(
                messages, db, agent_exec_id=exec_id, event_id=event_id, max_tokens=2500
            )
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            guidance = json.loads(content)
        except (LLMGatewayError, json.JSONDecodeError, Exception):
            llm_fallback = True
            guidance = self._default_guidance(gate_sequence)

        return {
            "agent_id": self.agent_id,
            "event_id": event_id,
            "event_name": event_name,
            "guidance_by_gate": guidance.get("by_gate", {}),
            "general_guidance": guidance.get("general", {
                "english": _FALLBACK_MESSAGES["gate_A_english"],
                "kannada": _FALLBACK_MESSAGES["general_kannada"],
                "hindi": _FALLBACK_MESSAGES["general_hindi"],
            }),
            "metro_instructions": guidance.get("metro", {
                "english": _FALLBACK_MESSAGES["metro_english"],
                "kannada": _FALLBACK_MESSAGES["general_kannada"],
                "hindi": _FALLBACK_MESSAGES["general_hindi"],
            }),
            "safety_message": guidance.get("safety_message", {}),
            "gate_sequence": gate_sequence,
            "priority_mode": priority_mode,
            "languages": ["english", "kannada", "hindi"],
            "llm_fallback": llm_fallback,
            "data_source": "SIMULATED",
        }

    def _default_guidance(self, gate_sequence: list[dict]) -> dict:
        """Deterministic guidance when LLM is unavailable."""
        gate_map = {g["gate_id"]: g for g in gate_sequence}
        by_gate = {}
        for gate_id in ["A", "B", "C", "D", "E"]:
            delay = gate_map.get(gate_id, {}).get("delay_minutes", 0)
            by_gate[gate_id] = {
                "english": (
                    f"Gate {gate_id} opens at T+{delay}min. "
                    f"{_FALLBACK_MESSAGES.get(f'gate_{gate_id}_english', 'Follow signage to nearest transport.')}"
                ),
                "kannada": _FALLBACK_MESSAGES["general_kannada"],
                "hindi": _FALLBACK_MESSAGES["general_hindi"],
            }

        return {
            "by_gate": by_gate,
            "general": {
                "english": "Walk calmly to your designated exit gate. Follow staff instructions.",
                "kannada": _FALLBACK_MESSAGES["general_kannada"],
                "hindi": _FALLBACK_MESSAGES["general_hindi"],
            },
            "metro": {
                "english": _FALLBACK_MESSAGES["metro_english"],
                "kannada": "ಮೆಟ್ರೋ: ಎಂಜಿ ರೋಡ್ ನಿಲ್ದಾಣ 12 ನಿಮಿಷ ನಡಿಗೆ.",
                "hindi": "मेट्रो: एमजी रोड स्टेशन 12 मिनट पैदल।",
            },
            "safety_message": {
                "english": "Do not rush. Keep moving. Assist those who need help.",
                "kannada": "ಆತುರ ಪಡಬೇಡಿ. ಮುಂದೆ ನಡೆಯಿರಿ.",
                "hindi": "जल्दी मत करें। आगे बढ़ते रहें।",
            },
        }

    def _fallback_output(self, input_data: dict, reason: str = "llm_unavailable") -> dict:
        base = super()._fallback_output(input_data, reason)
        base.update({
            "event_id": input_data.get("event_id", ""),
            "event_name": input_data.get("event_intelligence", {}).get("event_name", "IPL Match"),
            "guidance_by_gate": {},
            "general_guidance": {
                "english": "Please follow gate staff instructions.",
                "kannada": _FALLBACK_MESSAGES["general_kannada"],
                "hindi": _FALLBACK_MESSAGES["general_hindi"],
            },
            "metro_instructions": {
                "english": _FALLBACK_MESSAGES["metro_english"],
                "kannada": "",
                "hindi": "",
            },
            "safety_message": {},
            "gate_sequence": [],
            "priority_mode": "METRO",
            "languages": ["english", "kannada", "hindi"],
        })
        return base
