"""
Seed data constants for M. Chinnaswamy Stadium and the RCB demo event.

All IDs are stable UUIDs so seed scripts are idempotent.
"""

from __future__ import annotations

# ── Stable UUIDs (never change — referenced across seed modules) ──────────────

CHINNASWAMY_VENUE_ID = "10000000-0000-0000-0000-000000000001"
RCB_EVENT_ID         = "20000000-0000-0000-0000-000000000001"
SEED_USER_ID         = "30000000-0000-0000-0000-000000000001"  # system seed user

# ── Venue ─────────────────────────────────────────────────────────────────────

CHINNASWAMY_LAT = 12.9789
CHINNASWAMY_LON = 77.5996

CHINNASWAMY_GATES = [
    {"gate_id": "A", "name": "North Gate",  "lat": 12.9800, "lon": 77.5990, "capacity_pct": 0.25},
    {"gate_id": "B", "name": "South Gate",  "lat": 12.9778, "lon": 77.5996, "capacity_pct": 0.25},
    {"gate_id": "C", "name": "East Gate",   "lat": 12.9789, "lon": 77.6008, "capacity_pct": 0.20},
    {"gate_id": "D", "name": "West Gate",   "lat": 12.9789, "lon": 77.5984, "capacity_pct": 0.20},
    {"gate_id": "E", "name": "VIP Gate",    "lat": 12.9795, "lon": 77.5992, "capacity_pct": 0.10},
]

CHINNASWAMY_METRO_STATIONS = [
    {
        "name": "MG Road Metro",
        "line": "Purple",
        "walking_minutes": 12,
        "lat": 12.9752,
        "lon": 77.6060,
    },
    {
        "name": "Cubbon Park Metro",
        "line": "Green",
        "walking_minutes": 16,
        "lat": 12.9796,
        "lon": 77.5930,
    },
]

CHINNASWAMY_BUS_STOPS = [
    {
        "name": "KG Road Junction",
        "routes": ["137", "201", "401"],
        "walking_minutes": 5,
        "lat": 12.9756,
        "lon": 77.5936,
    },
    {
        "name": "MG Road Junction",
        "routes": ["36", "201"],
        "walking_minutes": 8,
        "lat": 12.9760,
        "lon": 77.6045,
    },
]

# ── Model config prompt templates (minimal placeholders for M2) ───────────────

AGENT_PROMPT_TEMPLATES = {
    "event_intelligence": (
        "You are the Event Intelligence Agent for Namma Exodus. "
        "Analyze the provided event data and produce structured intelligence. "
        "Event ID: {event_id}. Historical context: {historical_context}."
    ),
    "egress_forecast": (
        "You are the Egress Forecast Agent. "
        "Using the simulation data provided, produce a structured crowd-exit forecast. "
        "Event: {event_name}. Estimated attendance: {attendance}."
    ),
    "supply": (
        "You are the Supply Agent. "
        "Analyze transport availability and identify gaps. "
        "Forecast data: {forecast_summary}."
    ),
    "police_coordination": (
        "You are the Police Coordination Agent. "
        "Identify congestion hotspots and recommend traffic management actions. "
        "Congestion data: {congestion_summary}."
    ),
    "planner": (
        "You are the Planner Agent for Namma Exodus. "
        "Compare strategies and produce one coordinated action plan. "
        "All assessments: {assessment_summary}. "
        "Similar past events: {historical_context}. "
        "IMPORTANT: This plan requires human officer approval before any action."
    ),
    "citizen_guidance": (
        "You are the Citizen Guidance Agent. "
        "Generate travel instructions in English, Kannada, and Hindi. "
        "Gate assignments: {gate_assignments}. Transport options: {transport_options}."
    ),
    "learning": (
        "You are the Learning Agent. "
        "Compare predicted outcomes with actual/simulated results. "
        "Predicted: {predicted}. Actual: {actual}. Compute error and extract lessons."
    ),
}

# ── Historical ChromaDB seed records ─────────────────────────────────────────
# All records are SYNTHETIC — explicitly labeled as such.

CHROMA_HISTORICAL_RECORDS = [
    {
        "id": "hist-rcb-csk-2026",
        "document": (
            "RCB vs CSK IPL 2026 at M. Chinnaswamy Stadium, Bengaluru. "
            "Attendance: 33,000. Exit duration: 45 minutes. "
            "Transport adequacy: INADEQUATE. Metro gap: 8,000 persons at T+20. "
            "Lesson: Metro capacity insufficient; pre-positioned BMTC buses needed."
        ),
        "metadata": {
            "event_name": "RCB vs CSK IPL 2026",
            "venue": "M. Chinnaswamy Stadium",
            "attendance": "33000",
            "exit_duration_mins": "45",
            "transport_adequacy": "INADEQUATE",
            "data_source": "SIMULATED",
            "season": "IPL 2026",
        },
    },
    {
        "id": "hist-diwali-concert-2026",
        "document": (
            "Diwali Concert at M. Chinnaswamy Stadium, Bengaluru, October 2026. "
            "Attendance: 28,000. Exit duration: 38 minutes. "
            "Transport adequacy: ADEQUATE. "
            "Lesson: Pre-positioned BMTC buses at KG Road reduced auto demand by 30%. "
            "Staggered gate release reduced peak crowd density by 40%."
        ),
        "metadata": {
            "event_name": "Diwali Concert 2026",
            "venue": "M. Chinnaswamy Stadium",
            "attendance": "28000",
            "exit_duration_mins": "38",
            "transport_adequacy": "ADEQUATE",
            "data_source": "SIMULATED",
            "season": "2026",
        },
    },
    {
        "id": "hist-ipl-final-2026",
        "document": (
            "IPL Final 2026 at M. Chinnaswamy Stadium, Bengaluru. "
            "Attendance: 35,000. Exit duration: 55 minutes. "
            "Transport adequacy: INADEQUATE. MG Road: HIGH congestion for 40 minutes. "
            "Lesson: Simultaneous release of all gates caused MG Road bottleneck. "
            "Staggered 5-minute gate intervals recommended for future finals."
        ),
        "metadata": {
            "event_name": "IPL Final 2026",
            "venue": "M. Chinnaswamy Stadium",
            "attendance": "35000",
            "exit_duration_mins": "55",
            "transport_adequacy": "INADEQUATE",
            "data_source": "SIMULATED",
            "season": "IPL 2026",
        },
    },
]
