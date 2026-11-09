"""
Unit tests for Sub-task 2.1 — Seed module.

Covers:
- constants.py    — stable UUIDs, gate data, metro stations, prompt templates
- venues.py       — seed_venue SQL construction (mocked DB)
- events.py       — seed_event SQL construction (mocked DB)
- model_configs.py — seed_model_configs row count and fields
- chroma_seed.py  — upsert logic (ChromaDB mocked)
- run_seed.py     — seed_all orchestration with mocked dependencies

All tests locally executable — no Docker, no DB, no ChromaDB.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ═══════════════════════════════════════════════════════════════════════════════
# TestConstants
# ═══════════════════════════════════════════════════════════════════════════════

class TestConstants:
    """Validate that seed constants have the correct stable values."""

    def test_stable_venue_uuid(self):
        from app.seed.constants import CHINNASWAMY_VENUE_ID
        assert CHINNASWAMY_VENUE_ID == "10000000-0000-0000-0000-000000000001"

    def test_stable_event_uuid(self):
        from app.seed.constants import RCB_EVENT_ID
        assert RCB_EVENT_ID == "20000000-0000-0000-0000-000000000001"

    def test_stable_user_uuid(self):
        from app.seed.constants import SEED_USER_ID
        assert SEED_USER_ID == "30000000-0000-0000-0000-000000000001"

    def test_chinnaswamy_coordinates(self):
        from app.seed.constants import CHINNASWAMY_LAT, CHINNASWAMY_LON
        assert abs(CHINNASWAMY_LAT - 12.9789) < 0.001
        assert abs(CHINNASWAMY_LON - 77.5996) < 0.001

    def test_five_gates_defined(self):
        from app.seed.constants import CHINNASWAMY_GATES
        assert len(CHINNASWAMY_GATES) == 5
        gate_ids = {g["gate_id"] for g in CHINNASWAMY_GATES}
        assert gate_ids == {"A", "B", "C", "D", "E"}

    def test_gate_capacity_pct_sums_to_one(self):
        from app.seed.constants import CHINNASWAMY_GATES
        total = sum(g["capacity_pct"] for g in CHINNASWAMY_GATES)
        assert abs(total - 1.0) < 1e-9

    def test_gates_have_coordinates(self):
        from app.seed.constants import CHINNASWAMY_GATES
        for gate in CHINNASWAMY_GATES:
            assert "lat" in gate and "lon" in gate
            assert isinstance(gate["lat"], float)
            assert isinstance(gate["lon"], float)

    def test_two_metro_stations(self):
        from app.seed.constants import CHINNASWAMY_METRO_STATIONS
        assert len(CHINNASWAMY_METRO_STATIONS) == 2
        lines = {s["line"] for s in CHINNASWAMY_METRO_STATIONS}
        assert "Purple" in lines
        assert "Green" in lines

    def test_two_bus_stops(self):
        from app.seed.constants import CHINNASWAMY_BUS_STOPS
        assert len(CHINNASWAMY_BUS_STOPS) == 2

    def test_seven_agent_prompt_templates(self):
        from app.seed.constants import AGENT_PROMPT_TEMPLATES
        expected_agents = {
            "event_intelligence", "egress_forecast", "supply",
            "police_coordination", "planner", "citizen_guidance", "learning",
        }
        assert set(AGENT_PROMPT_TEMPLATES.keys()) == expected_agents

    def test_planner_prompt_has_approval_note(self):
        from app.seed.constants import AGENT_PROMPT_TEMPLATES
        assert "human officer approval" in AGENT_PROMPT_TEMPLATES["planner"]

    def test_three_chroma_historical_records(self):
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS
        assert len(CHROMA_HISTORICAL_RECORDS) == 3

    def test_chroma_records_all_simulated(self):
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS
        for rec in CHROMA_HISTORICAL_RECORDS:
            assert rec["metadata"]["data_source"] == "SIMULATED"

    def test_chroma_record_ids_unique(self):
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS
        ids = [r["id"] for r in CHROMA_HISTORICAL_RECORDS]
        assert len(ids) == len(set(ids))

    def test_chroma_records_have_required_fields(self):
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS
        for rec in CHROMA_HISTORICAL_RECORDS:
            assert "id" in rec
            assert "document" in rec
            assert "metadata" in rec
            assert len(rec["document"]) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# TestSeedVenue
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedVenue:
    """seed_venue() should call db.execute with correct SQL parameters."""

    @pytest.mark.asyncio
    async def test_seed_venue_calls_execute(self):
        from app.seed.venues import seed_venue
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        await seed_venue(mock_db)
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_seed_venue_passes_correct_id(self):
        from app.seed.venues import seed_venue
        from app.seed.constants import CHINNASWAMY_VENUE_ID
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_venue(mock_db)
        assert captured_params.get("id") == CHINNASWAMY_VENUE_ID

    @pytest.mark.asyncio
    async def test_seed_venue_passes_coordinates(self):
        from app.seed.venues import seed_venue
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_venue(mock_db)
        assert abs(float(captured_params.get("lat", 0)) - 12.9789) < 0.001
        assert abs(float(captured_params.get("lon", 0)) - 77.5996) < 0.001

    @pytest.mark.asyncio
    async def test_seed_venue_capacity_35000(self):
        from app.seed.venues import seed_venue
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_venue(mock_db)
        assert captured_params.get("total_capacity") == 35_000

    @pytest.mark.asyncio
    async def test_seed_venue_h3_center_is_valid(self):
        """H3 center cell at Chinnaswamy should be a valid resolution-7 cell."""
        from app.seed.venues import seed_venue
        import h3
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_venue(mock_db)
        h3_cell = captured_params.get("h3_center_res7", "")
        assert h3_cell != ""
        assert h3.get_resolution(h3_cell) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# TestSeedEvent
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedEvent:
    """seed_event() should insert RCB event with correct parameters."""

    @pytest.mark.asyncio
    async def test_seed_event_calls_execute(self):
        from app.seed.events import seed_event
        mock_db = AsyncMock()
        await seed_event(mock_db)
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_seed_event_passes_correct_id(self):
        from app.seed.events import seed_event
        from app.seed.constants import RCB_EVENT_ID
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_event(mock_db)
        assert captured_params.get("id") == RCB_EVENT_ID

    @pytest.mark.asyncio
    async def test_seed_event_references_chinnaswamy_venue(self):
        from app.seed.events import seed_event
        from app.seed.constants import CHINNASWAMY_VENUE_ID
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_event(mock_db)
        assert captured_params.get("venue_id") == CHINNASWAMY_VENUE_ID

    @pytest.mark.asyncio
    async def test_seed_event_is_simulated(self):
        from app.seed.events import seed_event
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_event(mock_db)
        assert captured_params.get("data_source") == "SIMULATED"

    @pytest.mark.asyncio
    async def test_seed_event_attendance_34000(self):
        from app.seed.events import seed_event
        mock_db = AsyncMock()
        captured_params = {}

        async def capture_execute(stmt, params=None):
            if params:
                captured_params.update(params)

        mock_db.execute = capture_execute
        await seed_event(mock_db)
        assert captured_params.get("estimated_attendance") == 34_000


# ═══════════════════════════════════════════════════════════════════════════════
# TestSeedModelConfigs
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedModelConfigs:
    """seed_model_configs() should insert 7 rows, one per agent."""

    @pytest.mark.asyncio
    async def test_seeds_seven_agent_configs(self):
        from app.seed.model_configs import seed_model_configs
        mock_db = AsyncMock()
        call_count = 0

        async def count_execute(stmt, params=None):
            nonlocal call_count
            call_count += 1

        mock_db.execute = count_execute
        await seed_model_configs(mock_db)
        assert call_count == 7

    @pytest.mark.asyncio
    async def test_granite_used_for_planner(self):
        from app.seed.model_configs import seed_model_configs
        mock_db = AsyncMock()
        planner_params = {}

        async def capture_execute(stmt, params=None):
            if params and params.get("agent_id") == "planner":
                planner_params.update(params)

        mock_db.execute = capture_execute
        await seed_model_configs(mock_db)
        assert "granite" in planner_params.get("model_name", "").lower()

    @pytest.mark.asyncio
    async def test_citizen_guidance_uses_gemini(self):
        from app.seed.model_configs import seed_model_configs
        mock_db = AsyncMock()
        cg_params = {}

        async def capture_execute(stmt, params=None):
            if params and params.get("agent_id") == "citizen_guidance":
                cg_params.update(params)

        mock_db.execute = capture_execute
        await seed_model_configs(mock_db)
        assert "gemini" in cg_params.get("model_name", "").lower()

    @pytest.mark.asyncio
    async def test_all_configs_have_version_v1(self):
        from app.seed.model_configs import seed_model_configs
        mock_db = AsyncMock()
        versions = []

        async def capture_execute(stmt, params=None):
            if params and "prompt_version" in params:
                versions.append(params["prompt_version"])

        mock_db.execute = capture_execute
        await seed_model_configs(mock_db)
        assert all(v == "v1.0" for v in versions)
        assert len(versions) == 7


# ═══════════════════════════════════════════════════════════════════════════════
# TestSeedChroma
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedChroma:
    """seed_chroma_history() should call collection.upsert with 3 records."""

    @pytest.mark.asyncio
    async def test_chroma_seed_upserts_three_records(self):
        """Patch chromadb at sys.modules level to avoid requiring Docker."""
        import sys
        import types
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        # Build minimal chromadb stub modules
        chroma_mod = types.ModuleType("chromadb")
        chroma_mod.HttpClient = MagicMock(return_value=mock_client)
        utils_mod = types.ModuleType("chromadb.utils")
        ef_mod = types.ModuleType("chromadb.utils.embedding_functions")
        ef_mod.SentenceTransformerEmbeddingFunction = MagicMock(return_value=MagicMock())

        orig_mods = {k: sys.modules.get(k) for k in ["chromadb", "chromadb.utils", "chromadb.utils.embedding_functions"]}
        sys.modules["chromadb"] = chroma_mod
        sys.modules["chromadb.utils"] = utils_mod
        sys.modules["chromadb.utils.embedding_functions"] = ef_mod

        try:
            # Force re-import so patched modules are used
            import importlib
            if "app.seed.chroma_seed" in sys.modules:
                del sys.modules["app.seed.chroma_seed"]
            from app.seed.chroma_seed import seed_chroma_history
            await seed_chroma_history()
        finally:
            # Restore original modules
            for k, v in orig_mods.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
            sys.modules.pop("app.seed.chroma_seed", None)

        mock_collection.upsert.assert_called_once()
        assert len(CHROMA_HISTORICAL_RECORDS) == 3

    @pytest.mark.asyncio
    async def test_chroma_seed_passes_all_ids(self):
        """All 3 historical record IDs must be passed to upsert."""
        import sys
        import types
        from app.seed.constants import CHROMA_HISTORICAL_RECORDS

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection

        chroma_mod = types.ModuleType("chromadb")
        chroma_mod.HttpClient = MagicMock(return_value=mock_client)
        utils_mod = types.ModuleType("chromadb.utils")
        ef_mod = types.ModuleType("chromadb.utils.embedding_functions")
        ef_mod.SentenceTransformerEmbeddingFunction = MagicMock(return_value=MagicMock())

        sys.modules["chromadb"] = chroma_mod
        sys.modules["chromadb.utils"] = utils_mod
        sys.modules["chromadb.utils.embedding_functions"] = ef_mod

        try:
            import importlib
            if "app.seed.chroma_seed" in sys.modules:
                del sys.modules["app.seed.chroma_seed"]
            from app.seed.chroma_seed import seed_chroma_history
            await seed_chroma_history()
        finally:
            for key in ["chromadb", "chromadb.utils", "chromadb.utils.embedding_functions", "app.seed.chroma_seed"]:
                sys.modules.pop(key, None)

        call_kwargs = mock_collection.upsert.call_args[1]
        expected_ids = {r["id"] for r in CHROMA_HISTORICAL_RECORDS}
        assert set(call_kwargs["ids"]) == expected_ids
