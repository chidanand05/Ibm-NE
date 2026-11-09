"""
Unit tests for Sub-task 2.1b — REST API endpoints for forecasts, transport, and map data.

All DB calls are mocked — no Docker, no PostgreSQL required.
Tests validate correct query construction, response structure, helper functions,
and error handling (404, filter params).
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


# ── Shared Factories ──────────────────────────────────────────────────────────

def _make_forecast(
    id: str = "fc-1",
    event_id: str = "ev-1",
    horizon: int = 20,
    total_demand: int = 22000,
    peak_zone: str = "87194ad3fffffff",
    confidence: float | None = 0.82,
    data_source: str = "SIMULATED",
):
    m = MagicMock()
    m.id = id
    m.event_id = event_id
    m.horizon_minutes = horizon
    m.total_demand = total_demand
    m.peak_zone_h3 = peak_zone
    m.confidence = Decimal(str(confidence)) if confidence is not None else None
    m.data_source = data_source
    m.forecast_time = datetime(2027, 4, 15, 9, 0, tzinfo=timezone.utc)
    m.created_at = datetime(2027, 4, 15, 9, 0, tzinfo=timezone.utc)
    return m


def _make_h3_cell(
    id: int = 1,
    forecast_id: str = "fc-1",
    event_id: str = "ev-1",
    h3_id: str = "87194ad3fffffff",
    demand_persons: int = 5000,
    demand_category: str = "HIGH",
    horizon: int = 20,
):
    m = MagicMock()
    m.id = id
    m.forecast_id = forecast_id
    m.event_id = event_id
    m.h3_id = h3_id
    m.resolution = 7
    m.center_lat = Decimal("12.978900")
    m.center_lon = Decimal("77.599600")
    m.demand_persons = demand_persons
    m.demand_category = demand_category
    m.horizon_minutes = horizon
    m.data_source = "SIMULATED"
    m.created_at = datetime(2027, 4, 15, 9, 0, tzinfo=timezone.utc)
    return m


def _make_snapshot(
    id: str = "snap-1",
    event_id: str = "ev-1",
    horizon: int = 20,
    mode: str = "METRO",
    capacity: int = 9600,
    vehicles: int = 12,
    gap_persons: int = 5000,
):
    m = MagicMock()
    m.id = id
    m.event_id = event_id
    m.time_horizon = horizon
    m.mode = mode
    m.capacity = capacity
    m.vehicles = vehicles
    m.frequency_mins = 5
    m.operational = True
    m.gap_persons = gap_persons
    m.data_source = "SIMULATED"
    m.notes = f"SIMULATED {mode} snapshot"
    m.snapshot_time = datetime(2027, 4, 15, 9, 0, tzinfo=timezone.utc)
    m.created_at = datetime(2027, 4, 15, 9, 0, tzinfo=timezone.utc)
    return m


def _async_db_returning(rows: list):
    """Build an AsyncMock DB session that returns `rows` from scalars().all()
    and from scalar_one_or_none() (sync call on result object)."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    # scalar_one_or_none is a SYNC method on the SQLAlchemy result object
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


# ═══════════════════════════════════════════════════════════════════════════════
# TestForecastHelpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestForecastHelpers:
    """Test _forecast_to_dict and _cell_to_dict helpers directly."""

    def test_forecast_to_dict_required_fields(self):
        from app.api.v1.forecasts import _forecast_to_dict
        f = _make_forecast()
        d = _forecast_to_dict(f)
        assert d["forecast_id"] == "fc-1"
        assert d["event_id"] == "ev-1"
        assert d["horizon_minutes"] == 20
        assert d["total_demand"] == 22000
        assert d["data_source"] == "SIMULATED"

    def test_forecast_to_dict_confidence_is_float(self):
        from app.api.v1.forecasts import _forecast_to_dict
        f = _make_forecast(confidence=0.82)
        d = _forecast_to_dict(f)
        assert isinstance(d["confidence"], float)
        assert abs(d["confidence"] - 0.82) < 0.001

    def test_forecast_to_dict_confidence_none(self):
        from app.api.v1.forecasts import _forecast_to_dict
        f = _make_forecast(confidence=None)
        d = _forecast_to_dict(f)
        assert d["confidence"] is None

    def test_cell_to_dict_required_fields(self):
        from app.api.v1.forecasts import _cell_to_dict
        c = _make_h3_cell()
        d = _cell_to_dict(c)
        assert d["h3_id"] == "87194ad3fffffff"
        assert d["demand_persons"] == 5000
        assert d["demand_category"] == "HIGH"
        assert d["data_source"] == "SIMULATED"

    def test_cell_to_dict_coordinates_are_float(self):
        from app.api.v1.forecasts import _cell_to_dict
        c = _make_h3_cell()
        d = _cell_to_dict(c)
        assert isinstance(d["center_lat"], float)
        assert isinstance(d["center_lon"], float)


# ═══════════════════════════════════════════════════════════════════════════════
# TestForecastEndpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestForecastEndpoints:

    @pytest.mark.asyncio
    async def test_list_forecasts_returns_items(self):
        from app.api.v1.forecasts import list_forecasts
        mock_db = _async_db_returning([_make_forecast()])
        # Pass integer values explicitly — FastAPI Query() objects are not valid outside DI
        result = await list_forecasts(db=mock_db, event_id=None, horizon=None, limit=50, offset=0)
        assert "items" in result
        assert result["total"] == 1
        assert result["items"][0]["forecast_id"] == "fc-1"

    @pytest.mark.asyncio
    async def test_list_forecasts_empty(self):
        from app.api.v1.forecasts import list_forecasts
        mock_db = _async_db_returning([])
        result = await list_forecasts(db=mock_db, event_id=None, horizon=None, limit=50, offset=0)
        assert result["total"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_list_forecasts_pagination_defaults(self):
        from app.api.v1.forecasts import list_forecasts
        mock_db = _async_db_returning([])
        result = await list_forecasts(db=mock_db, event_id=None, horizon=None, limit=10, offset=5)
        assert result["limit"] == 10
        assert result["offset"] == 5

    @pytest.mark.asyncio
    async def test_get_forecast_not_found_raises_404(self):
        from app.api.v1.forecasts import get_forecast
        from fastapi import HTTPException
        mock_db = _async_db_returning([])
        with pytest.raises(HTTPException) as exc:
            await get_forecast(forecast_id="nonexistent", db=mock_db)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_forecast_returns_h3_cells(self):
        from app.api.v1.forecasts import get_forecast

        forecast = _make_forecast()
        cell = _make_h3_cell(forecast_id="fc-1")

        # First execute → forecast; second execute → cells
        calls = [forecast, cell]
        call_index = [0]
        results_sequence = [
            ([forecast], None),   # first query: forecast rows
            ([cell], None),       # second query: cell rows
        ]

        mock_db = AsyncMock()
        result_iter = iter(results_sequence)

        async def side_effect_execute(stmt, *args, **kwargs):
            rows, _ = next(result_iter)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = rows
            mock_res = MagicMock()
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
            return mock_res

        mock_db.execute = side_effect_execute

        result = await get_forecast(forecast_id="fc-1", db=mock_db)
        assert result["forecast_id"] == "fc-1"
        assert "h3_cells" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TestTransportHelpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransportHelpers:

    def test_snapshot_to_dict_required_fields(self):
        from app.api.v1.transport import _snapshot_to_dict
        s = _make_snapshot()
        d = _snapshot_to_dict(s)
        assert d["snapshot_id"] == "snap-1"
        assert d["event_id"] == "ev-1"
        assert d["mode"] == "METRO"
        assert d["capacity"] == 9600
        assert d["data_source"] == "SIMULATED"

    def test_snapshot_to_dict_gap_persons(self):
        from app.api.v1.transport import _snapshot_to_dict
        s = _make_snapshot(gap_persons=5000)
        d = _snapshot_to_dict(s)
        assert d["gap_persons"] == 5000

    def test_snapshot_to_dict_operational_bool(self):
        from app.api.v1.transport import _snapshot_to_dict
        s = _make_snapshot()
        d = _snapshot_to_dict(s)
        assert isinstance(d["operational"], bool)


# ═══════════════════════════════════════════════════════════════════════════════
# TestTransportEndpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransportEndpoints:

    @pytest.mark.asyncio
    async def test_list_snapshots_returns_items(self):
        from app.api.v1.transport import list_transport_snapshots
        mock_db = _async_db_returning([_make_snapshot()])
        result = await list_transport_snapshots(
            db=mock_db, event_id=None, horizon=None, mode=None, limit=50, offset=0
        )
        assert result["total"] == 1
        assert result["items"][0]["mode"] == "METRO"

    @pytest.mark.asyncio
    async def test_list_snapshots_empty(self):
        from app.api.v1.transport import list_transport_snapshots
        mock_db = _async_db_returning([])
        result = await list_transport_snapshots(
            db=mock_db, event_id=None, horizon=None, mode=None, limit=50, offset=0
        )
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_snapshot_not_found_raises_404(self):
        from app.api.v1.transport import get_transport_snapshot
        from fastapi import HTTPException
        mock_db = _async_db_returning([])
        with pytest.raises(HTTPException) as exc:
            await get_transport_snapshot(snapshot_id="nonexistent", db=mock_db)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_snapshot_returns_correct_fields(self):
        from app.api.v1.transport import get_transport_snapshot
        snap = _make_snapshot(id="snap-42", mode="BMTC", capacity=6000)
        mock_db = _async_db_returning([snap])
        result = await get_transport_snapshot(snapshot_id="snap-42", db=mock_db)
        assert result["snapshot_id"] == "snap-42"
        assert result["mode"] == "BMTC"
        assert result["capacity"] == 6000


# ═══════════════════════════════════════════════════════════════════════════════
# TestMapDataHelpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapDataColors:
    """Test color and opacity constants for demand categories."""

    def test_critical_is_red(self):
        from app.api.v1.map_data import _CATEGORY_COLOR
        assert _CATEGORY_COLOR["CRITICAL"] == "#ef4444"

    def test_all_four_categories_have_colors(self):
        from app.api.v1.map_data import _CATEGORY_COLOR, _CATEGORY_OPACITY
        for cat in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            assert cat in _CATEGORY_COLOR
            assert cat in _CATEGORY_OPACITY

    def test_critical_has_highest_opacity(self):
        from app.api.v1.map_data import _CATEGORY_OPACITY
        assert _CATEGORY_OPACITY["CRITICAL"] > _CATEGORY_OPACITY["LOW"]


# ═══════════════════════════════════════════════════════════════════════════════
# TestMapDataEndpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapDataEndpoints:

    @pytest.mark.asyncio
    async def test_get_h3_cells_no_forecast_returns_404(self):
        from app.api.v1.map_data import get_h3_demand_cells
        from fastapi import HTTPException
        mock_db = _async_db_returning([])
        with pytest.raises(HTTPException) as exc:
            await get_h3_demand_cells(event_id="ev-999", db=mock_db, horizon=20)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_h3_cells_returns_cells_array(self):
        from app.api.v1.map_data import get_h3_demand_cells

        forecast = _make_forecast()
        cell = _make_h3_cell(h3_id="87194ad3fffffff", demand_persons=5000, demand_category="HIGH")

        results_sequence = [([forecast], None), ([cell], None)]
        result_iter = iter(results_sequence)

        mock_db = AsyncMock()

        async def side_effect_execute(stmt, *args, **kwargs):
            rows, _ = next(result_iter)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = rows
            mock_res = MagicMock()
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
            return mock_res

        mock_db.execute = side_effect_execute

        result = await get_h3_demand_cells(event_id="ev-1", db=mock_db, horizon=20)
        assert result["data_source"] == "SIMULATED"
        assert result["cell_count"] == 1
        assert result["cells"][0]["demand_category"] == "HIGH"
        assert result["cells"][0]["color"] == "#f97316"   # HIGH → orange

    @pytest.mark.asyncio
    async def test_get_h3_geojson_no_forecast_returns_404(self):
        from app.api.v1.map_data import get_h3_geojson
        from fastapi import HTTPException
        mock_db = _async_db_returning([])
        with pytest.raises(HTTPException) as exc:
            await get_h3_geojson(event_id="ev-999", db=mock_db, horizon=20)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_h3_geojson_returns_feature_collection(self):
        from app.api.v1.map_data import get_h3_geojson
        import h3

        forecast = _make_forecast()
        # Use a valid H3 cell ID
        valid_h3_id = h3.latlng_to_cell(12.9789, 77.5996, 7)
        cell = _make_h3_cell(h3_id=valid_h3_id, demand_persons=3000, demand_category="CRITICAL")

        results_sequence = [([forecast], None), ([cell], None)]
        result_iter = iter(results_sequence)

        mock_db = AsyncMock()

        async def side_effect_execute(stmt, *args, **kwargs):
            rows, _ = next(result_iter)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = rows
            mock_res = MagicMock()
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
            return mock_res

        mock_db.execute = side_effect_execute

        result = await get_h3_geojson(event_id="ev-1", db=mock_db, horizon=20)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 1
        feature = result["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Polygon"
        assert feature["properties"]["data_source"] == "SIMULATED"
        assert feature["properties"]["demand_category"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_geojson_polygon_is_closed(self):
        """GeoJSON polygon coordinates must start and end with the same point."""
        from app.api.v1.map_data import get_h3_geojson
        import h3

        forecast = _make_forecast()
        valid_h3_id = h3.latlng_to_cell(12.9789, 77.5996, 7)
        cell = _make_h3_cell(h3_id=valid_h3_id, demand_persons=1500, demand_category="MEDIUM")

        results_sequence = [([forecast], None), ([cell], None)]
        result_iter = iter(results_sequence)
        mock_db = AsyncMock()

        async def side_effect_execute(stmt, *args, **kwargs):
            rows, _ = next(result_iter)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = rows
            mock_res = MagicMock()
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
            return mock_res

        mock_db.execute = side_effect_execute

        result = await get_h3_geojson(event_id="ev-1", db=mock_db, horizon=20)
        coords = result["features"][0]["geometry"]["coordinates"][0]
        # Polygon ring must close (first == last point)
        assert coords[0] == coords[-1]

    @pytest.mark.asyncio
    async def test_geojson_metadata_has_data_source_simulated(self):
        from app.api.v1.map_data import get_h3_geojson
        import h3

        forecast = _make_forecast()
        valid_h3_id = h3.latlng_to_cell(12.9789, 77.5996, 7)
        cell = _make_h3_cell(h3_id=valid_h3_id, demand_persons=600, demand_category="LOW")

        results_sequence = [([forecast], None), ([cell], None)]
        result_iter = iter(results_sequence)
        mock_db = AsyncMock()

        async def side_effect_execute(stmt, *args, **kwargs):
            rows, _ = next(result_iter)
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = rows
            mock_res = MagicMock()
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none = MagicMock(return_value=rows[0] if rows else None)
            return mock_res

        mock_db.execute = side_effect_execute

        result = await get_h3_geojson(event_id="ev-1", db=mock_db, horizon=20)
        assert result["metadata"]["data_source"] == "SIMULATED"
        assert "SIMULATED" in result["metadata"]["note"]
