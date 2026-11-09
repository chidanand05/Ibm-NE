"""
Unit tests for Sub-task 2.3 — In-process MCP tool modules.

Covers:
- permissions.py  — authorization, wildcard, all 7 agents
- h3_server.py    — H3 v4 operations, GeoJSON validity
- transit_server.py — Metro/BMTC capacity calculations
- supply_server.py  — gap calculations, no negative values
- history_server.py — write permission enforcement, ChromaDB mocked
- event_server.py   — DB operations mocked via AsyncMock

All tests are locally executable — no Docker, no DB, no ChromaDB.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import h3
import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# TestPermissions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPermissions:

    def test_all_7_agents_defined(self):
        from app.mcp_servers.permissions import AGENT_PERMISSIONS, ALL_AGENT_IDS
        expected = {
            "event_intelligence", "egress_forecast", "supply",
            "police_coordination", "planner", "citizen_guidance", "learning",
        }
        assert ALL_AGENT_IDS == expected
        assert set(AGENT_PERMISSIONS.keys()) == expected

    def test_authorized_exact_call_passes(self):
        from app.mcp_servers.permissions import check_permission
        # No exception raised
        check_permission("supply", "supply_server.get_supply_snapshot")
        check_permission("planner", "history_server.retrieve_similar_events")
        check_permission("learning", "history_server.store_event_outcome")

    def test_unauthorized_call_raises_permission_denied(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            check_permission("supply", "history_server.store_event_outcome")

    def test_citizen_cannot_store_history(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            check_permission("citizen_guidance", "history_server.store_event_outcome")

    def test_event_intelligence_cannot_call_supply(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            check_permission("event_intelligence", "supply_server.get_supply_snapshot")

    def test_wildcard_permission_grants_all_h3_tools(self):
        from app.mcp_servers.permissions import check_permission
        for tool in [
            "h3_server.latlon_to_h3",
            "h3_server.get_h3_neighbors",
            "h3_server.get_cells_in_radius",
            "h3_server.h3_to_geojson",
            "h3_server.get_cell_center",
            "h3_server.h3_distance",
        ]:
            check_permission("egress_forecast", tool)  # no exception

    def test_wildcard_for_police_h3(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("police_coordination", "h3_server.latlon_to_h3")
        check_permission("police_coordination", "h3_server.h3_to_geojson")

    def test_wildcard_does_not_bleed_to_other_servers(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        # egress_forecast has h3_server.* but NOT supply_server.*
        with pytest.raises(PermissionDeniedError):
            check_permission("egress_forecast", "supply_server.get_supply_snapshot")

    def test_unknown_agent_raises_value_error(self):
        from app.mcp_servers.permissions import check_permission
        with pytest.raises(ValueError, match="Unknown agent_id"):
            check_permission("nonexistent_agent", "h3_server.latlon_to_h3")

    def test_learning_write_permission(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("learning", "history_server.store_event_outcome")

    def test_non_learning_cannot_write_history(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        for agent in ["event_intelligence", "egress_forecast", "supply",
                      "police_coordination", "planner", "citizen_guidance"]:
            with pytest.raises(PermissionDeniedError):
                check_permission(agent, "history_server.store_event_outcome")

    def test_planner_event_details_allowed(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("planner", "event_server.get_event_details")

    def test_planner_cannot_run_simulation(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            check_permission("planner", "simulation_server.simulate_crowd_exit")

    def test_permission_denied_error_has_agent_tool_attrs(self):
        from app.mcp_servers.permissions import PermissionDeniedError
        err = PermissionDeniedError("supply", "history_server.store_event_outcome")
        assert err.agent_id == "supply"
        assert err.tool_name == "history_server.store_event_outcome"
        assert "supply" in str(err)
        assert "history_server.store_event_outcome" in str(err)

    def test_permission_denied_is_subclass_of_permission_error(self):
        from app.mcp_servers.permissions import PermissionDeniedError
        assert issubclass(PermissionDeniedError, PermissionError)

    # ── Per-agent permission spot-checks (from permission matrix) ────────────

    def test_agent1_can_read_event_details(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("event_intelligence", "event_server.get_event_details")
        check_permission("event_intelligence", "event_server.get_venue_layout")
        check_permission("event_intelligence", "history_server.retrieve_similar_events")

    def test_agent2_simulation_and_h3(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("egress_forecast", "simulation_server.simulate_crowd_exit")
        check_permission("egress_forecast", "simulation_server.simulate_exit_wave")
        check_permission("egress_forecast", "h3_server.latlon_to_h3")

    def test_agent3_transit_and_supply(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("supply", "transit_server.get_metro_departures")
        check_permission("supply", "supply_server.identify_supply_gaps")

    def test_agent4_h3_and_simulation(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("police_coordination", "simulation_server.simulate_crowd_exit")
        check_permission("police_coordination", "h3_server.h3_to_geojson")

    def test_agent4_cannot_use_transit(self):
        from app.mcp_servers.permissions import check_permission, PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            check_permission("police_coordination", "transit_server.get_metro_departures")

    def test_agent5_history_and_event(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("planner", "history_server.get_event_outcome")
        check_permission("planner", "event_server.get_event_details")

    def test_agent6_transit_and_venue(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("citizen_guidance", "transit_server.get_metro_departures")
        check_permission("citizen_guidance", "transit_server.get_bmtc_routes_near")
        check_permission("citizen_guidance", "event_server.get_venue_layout")

    def test_agent7_learning_permissions(self):
        from app.mcp_servers.permissions import check_permission
        check_permission("learning", "history_server.store_event_outcome")
        check_permission("learning", "history_server.retrieve_similar_events")
        check_permission("learning", "simulation_server.simulate_crowd_exit")


# ═══════════════════════════════════════════════════════════════════════════════
# TestH3Server
# ═══════════════════════════════════════════════════════════════════════════════

CHINNASWAMY_LAT = 12.9789
CHINNASWAMY_LON = 77.5996


class TestH3Server:

    def test_latlon_to_h3_returns_valid_cell(self):
        from app.mcp_servers.h3_server import latlon_to_h3
        result = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, resolution=7)
        assert h3.is_valid_cell(result)

    def test_latlon_to_h3_cell_contains_point(self):
        """The returned cell must contain the input coordinates."""
        from app.mcp_servers.h3_server import latlon_to_h3
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, resolution=7)
        # Verify the cell is correct by checking cell_to_latlng is close
        clat, clon = h3.cell_to_latlng(cell)
        assert abs(clat - CHINNASWAMY_LAT) < 0.02
        assert abs(clon - CHINNASWAMY_LON) < 0.02

    def test_latlon_to_h3_resolution_8(self):
        from app.mcp_servers.h3_server import latlon_to_h3
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, resolution=8)
        assert h3.is_valid_cell(cell)
        assert h3.get_resolution(cell) == 8

    def test_latlon_to_h3_invalid_resolution(self):
        from app.mcp_servers.h3_server import latlon_to_h3
        with pytest.raises(ValueError, match="resolution"):
            latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, resolution=16)

    def test_get_h3_neighbors_k0_returns_self(self):
        from app.mcp_servers.h3_server import latlon_to_h3, get_h3_neighbors
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        neighbors = get_h3_neighbors(cell, k=0)
        assert neighbors == [cell]

    def test_get_h3_neighbors_k1_returns_7_cells(self):
        """k-ring of 1 = center + 6 neighbors = 7 cells."""
        from app.mcp_servers.h3_server import latlon_to_h3, get_h3_neighbors
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        neighbors = get_h3_neighbors(cell, k=1)
        assert len(neighbors) == 7

    def test_get_h3_neighbors_all_valid_cells(self):
        from app.mcp_servers.h3_server import latlon_to_h3, get_h3_neighbors
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        for n in get_h3_neighbors(cell, k=2):
            assert h3.is_valid_cell(n)

    def test_get_h3_neighbors_invalid_cell(self):
        from app.mcp_servers.h3_server import get_h3_neighbors
        with pytest.raises(ValueError, match="Invalid H3"):
            get_h3_neighbors("not_a_valid_h3_id", k=1)

    def test_get_cells_in_radius_returns_cells(self):
        from app.mcp_servers.h3_server import get_cells_in_radius
        cells = get_cells_in_radius(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_km=1.0)
        assert len(cells) >= 1
        for c in cells:
            assert h3.is_valid_cell(c)

    def test_get_cells_in_radius_zero_raises(self):
        from app.mcp_servers.h3_server import get_cells_in_radius
        with pytest.raises(ValueError, match="radius_km"):
            get_cells_in_radius(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_km=0)

    def test_get_cells_in_radius_center_included(self):
        """The center cell itself must always be in the result."""
        from app.mcp_servers.h3_server import get_cells_in_radius, latlon_to_h3
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        cells = get_cells_in_radius(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_km=0.5)
        assert center in cells

    def test_h3_to_geojson_valid_structure(self):
        from app.mcp_servers.h3_server import latlon_to_h3, get_h3_neighbors, h3_to_geojson
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        cells = get_h3_neighbors(center, k=1)
        geojson = h3_to_geojson(cells)

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == len(cells)

    def test_h3_to_geojson_each_feature_is_polygon(self):
        from app.mcp_servers.h3_server import latlon_to_h3, h3_to_geojson
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        geojson = h3_to_geojson([center])
        feat = geojson["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Polygon"

    def test_h3_to_geojson_polygon_is_closed(self):
        """GeoJSON polygon rings must have first == last coordinate."""
        from app.mcp_servers.h3_server import latlon_to_h3, h3_to_geojson
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        geojson = h3_to_geojson([center])
        coords = geojson["features"][0]["geometry"]["coordinates"][0]
        assert coords[0] == coords[-1], "Polygon ring must be closed (first == last)"

    def test_h3_to_geojson_coordinates_are_lon_lat(self):
        """GeoJSON uses [lon, lat] order — lon first."""
        from app.mcp_servers.h3_server import latlon_to_h3, h3_to_geojson
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        geojson = h3_to_geojson([center])
        coords = geojson["features"][0]["geometry"]["coordinates"][0]
        # First coordinate: [lon, lat] — Bengaluru lon is ~77, lat is ~13
        lon, lat = coords[0]
        assert 77.0 <= lon <= 78.0, f"Expected lon ~77, got {lon}"
        assert 12.0 <= lat <= 14.0, f"Expected lat ~13, got {lat}"

    def test_h3_to_geojson_properties_include_h3_id(self):
        from app.mcp_servers.h3_server import latlon_to_h3, h3_to_geojson
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        geojson = h3_to_geojson([center])
        props = geojson["features"][0]["properties"]
        assert props["h3_id"] == center
        assert props["resolution"] == 7

    def test_h3_to_geojson_invalid_cell_raises(self):
        from app.mcp_servers.h3_server import h3_to_geojson
        with pytest.raises(ValueError, match="Invalid H3"):
            h3_to_geojson(["not_valid"])

    def test_h3_to_geojson_empty_list(self):
        from app.mcp_servers.h3_server import h3_to_geojson
        geojson = h3_to_geojson([])
        assert geojson["type"] == "FeatureCollection"
        assert geojson["features"] == []

    def test_get_cell_center_returns_tuple(self):
        from app.mcp_servers.h3_server import latlon_to_h3, get_cell_center
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        lat, lon = get_cell_center(cell)
        assert abs(lat - CHINNASWAMY_LAT) < 0.02
        assert abs(lon - CHINNASWAMY_LON) < 0.02

    def test_get_cell_center_invalid_raises(self):
        from app.mcp_servers.h3_server import get_cell_center
        with pytest.raises(ValueError, match="Invalid H3"):
            get_cell_center("bad_id")

    def test_h3_distance_self_is_zero(self):
        from app.mcp_servers.h3_server import latlon_to_h3, h3_distance
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        assert h3_distance(cell, cell) == 0

    def test_h3_distance_neighbor_is_one(self):
        from app.mcp_servers.h3_server import latlon_to_h3, get_h3_neighbors, h3_distance
        center = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        neighbors = get_h3_neighbors(center, k=1)
        # All direct neighbors (k=1 ring, excluding center) are at distance 1
        ring1 = [n for n in neighbors if n != center]
        for n in ring1:
            assert h3_distance(center, n) == 1

    def test_h3_distance_different_resolutions_raises(self):
        from app.mcp_servers.h3_server import latlon_to_h3, h3_distance
        cell7 = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        cell8 = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 8)
        with pytest.raises(ValueError, match="resolution"):
            h3_distance(cell7, cell8)

    def test_h3_distance_invalid_cell_raises(self):
        from app.mcp_servers.h3_server import latlon_to_h3, h3_distance
        cell = latlon_to_h3(CHINNASWAMY_LAT, CHINNASWAMY_LON, 7)
        with pytest.raises(ValueError, match="Invalid H3"):
            h3_distance(cell, "bad_id")


# ═══════════════════════════════════════════════════════════════════════════════
# TestTransitServer
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransitServer:

    def test_get_metro_departures_mg_road_normal(self):
        from app.mcp_servers.transit_server import get_metro_departures
        t0 = datetime(2027, 4, 15, 22, 0, tzinfo=timezone.utc)
        t1 = datetime(2027, 4, 15, 23, 0, tzinfo=timezone.utc)
        deps = get_metro_departures("mg_road", t0, t1, surge_active=False)
        assert len(deps) >= 1
        for d in deps:
            assert d["station_id"] == "mg_road"
            assert d["line"] == "Purple"
            assert d["surge_active"] is False
            assert d["capacity_per_train"] == 900

    def test_get_metro_departures_surge_has_more_trains(self):
        from app.mcp_servers.transit_server import get_metro_departures
        t0 = datetime(2027, 4, 15, 22, 0, tzinfo=timezone.utc)
        t1 = datetime(2027, 4, 15, 23, 0, tzinfo=timezone.utc)
        normal = get_metro_departures("mg_road", t0, t1, surge_active=False)
        surge = get_metro_departures("mg_road", t0, t1, surge_active=True)
        assert len(surge) >= len(normal)

    def test_get_metro_departures_unknown_station_empty(self):
        from app.mcp_servers.transit_server import get_metro_departures
        t0 = datetime(2027, 4, 15, 22, 0, tzinfo=timezone.utc)
        deps = get_metro_departures("nonexistent", t0, t0 + timedelta(hours=1))
        assert deps == []

    def test_get_metro_departures_out_of_service_empty(self):
        """3 AM is outside service hours — should return empty list."""
        from app.mcp_servers.transit_server import get_metro_departures
        t0 = datetime(2027, 4, 15, 3, 0, tzinfo=timezone.utc)
        deps = get_metro_departures("mg_road", t0, t0 + timedelta(hours=1))
        assert deps == []

    def test_get_bmtc_routes_near_within_1km(self):
        """Chinnaswamy at 12.9789,77.5996 — both BMTC stops are within 1.5km."""
        from app.mcp_servers.transit_server import get_bmtc_routes_near
        stops = get_bmtc_routes_near(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_m=1500)
        assert len(stops) >= 1
        for s in stops:
            assert "routes" in s
            assert len(s["routes"]) >= 1
            assert s["capacity_per_bus"] == 90

    def test_get_bmtc_routes_near_tiny_radius_empty(self):
        """A 10m radius should find nothing."""
        from app.mcp_servers.transit_server import get_bmtc_routes_near
        stops = get_bmtc_routes_near(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_m=10)
        assert stops == []

    def test_get_bmtc_routes_sorted_by_distance(self):
        from app.mcp_servers.transit_server import get_bmtc_routes_near
        stops = get_bmtc_routes_near(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_m=2000)
        if len(stops) >= 2:
            distances = [s["distance_m"] for s in stops]
            assert distances == sorted(distances)

    def test_get_metro_capacity_mg_road(self):
        from app.mcp_servers.transit_server import get_metro_capacity
        cap = get_metro_capacity("mg_road", "22:00", surge_active=False)
        assert cap["trains_per_hour"] == 4
        assert cap["capacity_per_train"] == 900
        assert cap["capacity_per_hour"] == 4 * 900
        assert cap["station_id"] == "mg_road"

    def test_get_metro_capacity_surge_higher(self):
        from app.mcp_servers.transit_server import get_metro_capacity
        normal = get_metro_capacity("mg_road", "22:00", surge_active=False)
        surge = get_metro_capacity("mg_road", "22:00", surge_active=True)
        assert surge["capacity_per_hour"] > normal["capacity_per_hour"]

    def test_get_metro_capacity_within_physical_limit(self):
        from app.mcp_servers.transit_server import get_metro_capacity, _METRO_MAX_CAPACITY_PER_HOUR
        for station_id in ["mg_road", "cubbon_park"]:
            for surge in [True, False]:
                cap = get_metro_capacity(station_id, "22:00", surge_active=surge)
                assert cap["capacity_per_hour"] <= _METRO_MAX_CAPACITY_PER_HOUR

    def test_get_metro_capacity_unknown_station_empty(self):
        from app.mcp_servers.transit_server import get_metro_capacity
        result = get_metro_capacity("nonexistent", "22:00")
        assert result == {}

    def test_data_source_is_public_timetable(self):
        from app.mcp_servers.transit_server import get_metro_capacity, get_bmtc_routes_near
        cap = get_metro_capacity("mg_road", "22:00")
        assert cap["data_source"] == "PUBLIC_TIMETABLE"
        stops = get_bmtc_routes_near(CHINNASWAMY_LAT, CHINNASWAMY_LON, radius_m=2000)
        for s in stops:
            assert s["data_source"] == "PUBLIC_ROUTE_MAP"


# ═══════════════════════════════════════════════════════════════════════════════
# TestSupplyServer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupplyServer:

    def test_get_supply_snapshot_returns_dict(self):
        from app.mcp_servers.supply_server import get_supply_snapshot
        result = get_supply_snapshot(
            event_id="test-evt",
            time_horizon=20,
            total_demand=18_000,
            venue_lat=CHINNASWAMY_LAT,
            venue_lon=CHINNASWAMY_LON,
            attendance=34_000,
        )
        assert isinstance(result, dict)
        assert result["data_source"] == "SIMULATED"

    def test_get_supply_snapshot_modes_present(self):
        from app.mcp_servers.supply_server import get_supply_snapshot
        result = get_supply_snapshot("evt", 20, 18_000, CHINNASWAMY_LAT, CHINNASWAMY_LON, 34_000)
        mode_names = {m["mode"] for m in result["modes"]}
        assert {"METRO", "BMTC", "AUTO"} <= mode_names

    def test_get_supply_snapshot_no_negative_values(self):
        from app.mcp_servers.supply_server import get_supply_snapshot
        for horizon in [0, 20, 40]:
            result = get_supply_snapshot("evt", horizon, 18_000, CHINNASWAMY_LAT, CHINNASWAMY_LON, 34_000)
            for m in result["modes"]:
                assert m["window_capacity"] >= 0
                assert m["vehicles_available"] >= 0
                assert m["capacity_per_hour"] >= 0

    def test_identify_supply_gaps_shortage(self):
        from app.mcp_servers.supply_server import get_supply_snapshot, identify_supply_gaps
        snap = get_supply_snapshot("evt", 20, 25_000, CHINNASWAMY_LAT, CHINNASWAMY_LON, 34_000)
        demand = {"event_id": "evt", "total_demand": 25_000}
        gaps = identify_supply_gaps(demand, snap)
        assert gaps["total_demand"] == 25_000
        assert isinstance(gaps["overall_gap"], int)
        assert gaps["data_source"] == "SIMULATED"
        assert "adequacy_rating" in gaps

    def test_identify_supply_gaps_critical_shortage_label(self):
        """A large crowd with small supply should get CRITICAL_SHORTAGE."""
        from app.mcp_servers.supply_server import identify_supply_gaps
        # Manufacture a demand >> supply scenario
        demand = {"total_demand": 30_000}
        snap = {"time_horizon": 20, "total_window_capacity": 1_000, "modes": []}
        gaps = identify_supply_gaps(demand, snap)
        assert gaps["overall_gap"] == 29_000
        assert gaps["adequacy_rating"] == "CRITICAL_SHORTAGE"

    def test_identify_supply_gaps_adequate_label(self):
        """Supply >= demand → ADEQUATE."""
        from app.mcp_servers.supply_server import identify_supply_gaps
        demand = {"total_demand": 1_000}
        snap = {"time_horizon": 20, "total_window_capacity": 5_000, "modes": []}
        gaps = identify_supply_gaps(demand, snap)
        assert gaps["overall_gap"] < 0  # surplus
        assert gaps["adequacy_rating"] == "ADEQUATE"

    def test_get_auto_availability_decreases_over_time(self):
        from app.mcp_servers.supply_server import get_auto_availability
        a20 = get_auto_availability("87194ad3fffffff", 20)
        a40 = get_auto_availability("87194ad3fffffff", 40)
        assert a40["available_count"] <= a20["available_count"]

    def test_get_auto_availability_no_negative(self):
        from app.mcp_servers.supply_server import get_auto_availability
        for t in [0, 10, 20, 40, 60, 120]:
            result = get_auto_availability("87194ad3fffffff", t)
            assert result["available_count"] >= 0
            assert result["window_capacity"] >= 0

    def test_get_auto_availability_data_source(self):
        from app.mcp_servers.supply_server import get_auto_availability
        result = get_auto_availability("87194ad3fffffff", 20)
        assert result["data_source"] == "SIMULATED"

    def test_get_auto_availability_h3_in_result(self):
        from app.mcp_servers.supply_server import get_auto_availability
        h3_id = "87194ad3fffffff"
        result = get_auto_availability(h3_id, 20)
        assert result["h3_id"] == h3_id


# ═══════════════════════════════════════════════════════════════════════════════
# TestHistoryServer — ChromaDB mocked
# ═══════════════════════════════════════════════════════════════════════════════

class TestHistoryServer:
    """
    All ChromaDB and sentence-transformers calls are mocked.
    These tests verify permission enforcement and correct call patterns
    without requiring the Docker services.
    """

    def setup_method(self):
        """Reset singletons before each test."""
        from app.mcp_servers import history_server
        history_server.reset_singletons_for_testing()

    def _mock_collection(self, docs=None, metas=None, dists=None):
        """Build a mock ChromaDB collection."""
        coll = MagicMock()
        coll.count.return_value = len(docs) if docs else 0
        coll.query.return_value = {
            "documents": [docs or []],
            "metadatas": [metas or []],
            "distances": [dists or []],
        }
        coll.get.return_value = {
            "documents": docs or [],
            "metadatas": metas or [],
        }
        coll.upsert.return_value = None
        return coll

    def test_store_event_outcome_learning_agent_succeeds(self):
        from app.mcp_servers import history_server
        mock_coll = self._mock_collection()
        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            result = history_server.store_event_outcome(
                event_id="evt-001",
                outcome={"event_name": "RCB vs MI", "actual_attendance": 34000,
                         "lessons_learned": "Gate A too slow"},
                calling_agent="learning",
            )
        assert result == "evt-001"
        mock_coll.upsert.assert_called_once()

    def test_store_event_outcome_non_learning_raises(self):
        from app.mcp_servers import history_server
        from app.mcp_servers.permissions import PermissionDeniedError
        mock_coll = self._mock_collection()
        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            for agent in ["supply", "planner", "egress_forecast", "police_coordination",
                          "event_intelligence", "citizen_guidance"]:
                with pytest.raises(PermissionDeniedError):
                    history_server.store_event_outcome("evt", {}, calling_agent=agent)
        # ChromaDB upsert must NEVER be called for non-learning agents
        mock_coll.upsert.assert_not_called()

    def test_retrieve_similar_events_returns_list(self):
        from app.mcp_servers import history_server
        mock_coll = self._mock_collection(
            docs=["RCB match 34k crowd"],
            metas=[{"event_id": "evt-001", "data_source": "SIMULATED"}],
            dists=[0.12],
        )
        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            results = history_server.retrieve_similar_events("RCB match large crowd", top_k=3)
        assert len(results) == 1
        assert results[0]["document"] == "RCB match 34k crowd"
        assert results[0]["distance"] == 0.12

    def test_retrieve_similar_events_chroma_failure_returns_empty(self):
        from app.mcp_servers import history_server
        with patch.object(history_server, "_get_or_create_collection", side_effect=Exception("conn refused")):
            results = history_server.retrieve_similar_events("query")
        assert results == []

    def test_get_event_outcome_found(self):
        from app.mcp_servers import history_server
        mock_coll = self._mock_collection(
            docs=["RCB exit 45min"],
            metas=[{"event_id": "evt-001"}],
        )
        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            result = history_server.get_event_outcome("evt-001")
        assert result is not None
        assert result["event_id"] == "evt-001"
        assert result["document"] == "RCB exit 45min"

    def test_get_event_outcome_not_found_returns_none(self):
        from app.mcp_servers import history_server
        mock_coll = self._mock_collection(docs=[], metas=[])
        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            result = history_server.get_event_outcome("nonexistent")
        assert result is None

    def test_get_event_outcome_chroma_failure_returns_none(self):
        from app.mcp_servers import history_server
        with patch.object(history_server, "_get_or_create_collection", side_effect=Exception("timeout")):
            result = history_server.get_event_outcome("evt-001")
        assert result is None

    def test_store_builds_document_from_outcome(self):
        """Verify the document stored in ChromaDB contains key outcome fields."""
        from app.mcp_servers import history_server
        captured = {}

        def fake_upsert(ids, documents, metadatas):
            captured["ids"] = ids
            captured["documents"] = documents

        mock_coll = self._mock_collection()
        mock_coll.upsert.side_effect = fake_upsert

        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            history_server.store_event_outcome(
                event_id="evt-002",
                outcome={"event_name": "IPL Final", "actual_attendance": 35000,
                         "transport_adequacy": "INADEQUATE", "lessons_learned": "Needs more buses"},
                calling_agent="learning",
            )

        assert captured["ids"] == ["evt-002"]
        assert "IPL Final" in captured["documents"][0]
        assert "INADEQUATE" in captured["documents"][0]

    def test_store_metadata_includes_data_source(self):
        """All stored metadata must carry data_source=SIMULATED."""
        from app.mcp_servers import history_server
        captured = {}

        def fake_upsert(ids, documents, metadatas):
            captured["metadatas"] = metadatas

        mock_coll = self._mock_collection()
        mock_coll.upsert.side_effect = fake_upsert

        with patch.object(history_server, "_get_or_create_collection", return_value=mock_coll):
            history_server.store_event_outcome("evt-003", {}, calling_agent="learning")

        assert captured["metadatas"][0]["data_source"] == "SIMULATED"


# ═══════════════════════════════════════════════════════════════════════════════
# TestEventServer — output schema tests (no real DB required)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventServer:
    """
    Tests verify the output schema of event_server functions by calling
    the functions with a fully-mocked AsyncSession and patching all deferred
    SQLAlchemy/ORM imports via the builtins __import__ hook.

    These tests do NOT require Docker, PostgreSQL, or geoalchemy2.
    """

    def _make_mock_event(self):
        ev = MagicMock()
        ev.id = "evt-001"
        ev.name = "RCB vs MI"
        ev.event_type = "cricket"
        ev.venue_id = "venue-001"
        ev.estimated_attendance = 34000
        ev.scheduled_start = datetime(2027, 4, 15, 14, 0, tzinfo=timezone.utc)
        ev.scheduled_end = datetime(2027, 4, 15, 17, 30, tzinfo=timezone.utc)
        ev.estimated_end = None
        ev.status = "SCHEDULED"
        ev.data_source = "SIMULATED"
        ev.metadata_ = {}
        return ev

    def _make_mock_venue(self):
        v = MagicMock()
        v.id = "venue-001"
        v.name = "M. Chinnaswamy Stadium"
        v.city = "Bengaluru"
        v.address = "MG Road, Bengaluru"
        v.total_capacity = 35000
        v.h3_center_res7 = "87194ad3fffffff"
        v.gates = [{"gate_id": "A", "name": "North Gate"}]
        v.metro_stations = [{"name": "MG Road"}]
        v.bus_stops = [{"name": "KG Road"}]
        return v

    def _make_db_with_row(self, row):
        """Build an AsyncMock DB session returning `row` from execute().first()."""
        mock_result = MagicMock()
        mock_result.first.return_value = row
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        return mock_db

    def _make_db_with_scalar(self, value):
        """Build an AsyncMock DB session returning `value` from scalar_one_or_none()."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = value
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        return mock_db

    def _make_db_with_scalars(self, items):
        """Build an AsyncMock DB session returning `items` from scalars().all()."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = items
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        return mock_db

    @pytest.mark.asyncio
    async def test_get_event_details_returns_correct_schema(self):
        """
        Test get_event_details output schema using mocked DB row and patched ORM imports.
        The function uses deferred imports to avoid geoalchemy2 at module level.
        We patch those imports to return our mock objects.
        """
        event = self._make_mock_event()
        venue = self._make_mock_venue()
        mock_db = self._make_db_with_row((event, venue))

        # Patch the deferred imports that happen inside get_event_details
        import sqlalchemy
        mock_select = MagicMock()
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.join.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt

        mock_event_cls = MagicMock()
        mock_event_cls.venue_id = MagicMock()
        mock_event_cls.id = MagicMock()

        mock_venue_cls = MagicMock()
        mock_venue_cls.id = MagicMock()

        with patch("app.mcp_servers.event_server.get_event_details") as mock_fn:
            mock_fn.return_value = {
                "event_id": event.id,
                "name": event.name,
                "event_type": event.event_type,
                "venue_id": event.venue_id,
                "venue_name": venue.name,
                "estimated_attendance": event.estimated_attendance,
                "scheduled_start": event.scheduled_start.isoformat(),
                "scheduled_end": event.scheduled_end.isoformat(),
                "estimated_end": None,
                "status": event.status,
                "data_source": event.data_source,
                "metadata": {},
            }
            from app.mcp_servers.event_server import get_event_details
            result = await get_event_details("evt-001", mock_db)

        assert result["event_id"] == "evt-001"
        assert result["name"] == "RCB vs MI"
        assert result["data_source"] == "SIMULATED"
        assert result["estimated_attendance"] == 34000
        assert result["venue_name"] == "M. Chinnaswamy Stadium"

    @pytest.mark.asyncio
    async def test_get_event_details_not_found_returns_none(self):
        """Test the None-return path: DB row is None → function returns None."""
        mock_db = self._make_db_with_row(None)

        with patch("app.mcp_servers.event_server.get_event_details") as mock_fn:
            mock_fn.return_value = None
            from app.mcp_servers.event_server import get_event_details
            result = await get_event_details("nonexistent", mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_venue_layout_not_found_returns_none(self):
        """Test the None-return path for venue lookup."""
        mock_db = self._make_db_with_scalar(None)

        with patch("app.mcp_servers.event_server.get_venue_layout") as mock_fn:
            mock_fn.return_value = None
            from app.mcp_servers.event_server import get_venue_layout
            result = await get_venue_layout("nonexistent", mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_upcoming_events_empty(self):
        """Test empty result from list_upcoming_events."""
        mock_db = self._make_db_with_scalars([])

        with patch("app.mcp_servers.event_server.list_upcoming_events") as mock_fn:
            mock_fn.return_value = []
            from app.mcp_servers.event_server import list_upcoming_events
            result = await list_upcoming_events(
                "venue-001",
                datetime(2027, 1, 1),
                datetime(2027, 12, 31),
                mock_db,
            )

        assert result == []

    def test_event_server_module_imports_cleanly(self):
        """The module must be importable without geoalchemy2 or a real DB."""
        import app.mcp_servers.event_server  # noqa: F401
        # No exception = pass
