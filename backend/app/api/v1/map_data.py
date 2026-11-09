"""H3 map data endpoints — Sub-task 2.1b."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.dependencies import DBSession
from app.models.db.h3_demand_cell import H3DemandCell
from app.models.db.crowd_forecast import CrowdForecast

from sqlalchemy import select

import h3 as _h3

router = APIRouter()

# Demand category → hex color for GeoJSON styling (WCAG-compliant, dark-map friendly)
_CATEGORY_COLOR = {
    "CRITICAL": "#ef4444",   # red-500
    "HIGH":     "#f97316",   # orange-500
    "MEDIUM":   "#eab308",   # yellow-500
    "LOW":      "#22c55e",   # green-500
}

_CATEGORY_OPACITY = {
    "CRITICAL": 0.85,
    "HIGH":     0.70,
    "MEDIUM":   0.55,
    "LOW":      0.35,
}


@router.get("/h3/{event_id}")
async def get_h3_demand_cells(
    event_id: str,
    db: DBSession,
    horizon: int = Query(20, description="Horizon in minutes: 20 or 40"),
) -> dict:
    """
    Return H3 demand cells for an event at a given horizon.

    Returns the latest forecast's cells. Results include demand_persons,
    demand_category, and center coordinates for map rendering.

    data_source is always SIMULATED — labeled in every cell.
    """
    # Find the latest forecast for this event + horizon
    forecast_stmt = (
        select(CrowdForecast)
        .where(CrowdForecast.event_id == event_id)
        .where(CrowdForecast.horizon_minutes == horizon)
        .order_by(CrowdForecast.created_at.desc())
        .limit(1)
    )
    forecast_result = await db.execute(forecast_stmt)
    forecast = forecast_result.scalar_one_or_none()
    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No forecast found for event {event_id} at T+{horizon}. "
                "Run POST /api/v1/events/{event_id}/simulate first."
            ),
        )

    # Load cells for this forecast
    cell_stmt = (
        select(H3DemandCell)
        .where(H3DemandCell.forecast_id == forecast.id)
        .order_by(H3DemandCell.demand_persons.desc())
    )
    cell_result = await db.execute(cell_stmt)
    cells = cell_result.scalars().all()

    return {
        "event_id":        event_id,
        "forecast_id":     forecast.id,
        "horizon_minutes": horizon,
        "total_demand":    forecast.total_demand,
        "peak_zone_h3":    forecast.peak_zone_h3,
        "cell_count":      len(cells),
        "data_source":     "SIMULATED",
        "cells": [
            {
                "h3_id":           c.h3_id,
                "center_lat":      float(c.center_lat) if c.center_lat is not None else None,
                "center_lon":      float(c.center_lon) if c.center_lon is not None else None,
                "demand_persons":  c.demand_persons,
                "demand_category": c.demand_category or "LOW",
                "color":           _CATEGORY_COLOR.get(c.demand_category or "LOW", "#22c55e"),
                "opacity":         _CATEGORY_OPACITY.get(c.demand_category or "LOW", 0.35),
                "data_source":     "SIMULATED",
            }
            for c in cells
        ],
    }


@router.get("/h3/{event_id}/geojson")
async def get_h3_geojson(
    event_id: str,
    db: DBSession,
    horizon: int = Query(20, description="Horizon in minutes: 20 or 40"),
) -> dict:
    """
    Return H3 demand cells as a GeoJSON FeatureCollection for MapLibre rendering.

    Each feature is an H3 hexagon polygon with demand properties.
    data_source is always SIMULATED — labeled in every feature.
    """
    # Reuse the cell-loading logic from get_h3_demand_cells
    forecast_stmt = (
        select(CrowdForecast)
        .where(CrowdForecast.event_id == event_id)
        .where(CrowdForecast.horizon_minutes == horizon)
        .order_by(CrowdForecast.created_at.desc())
        .limit(1)
    )
    forecast_result = await db.execute(forecast_stmt)
    forecast = forecast_result.scalar_one_or_none()
    if forecast is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No forecast found for event {event_id} at T+{horizon}. "
                "Run POST /api/v1/events/{event_id}/simulate first."
            ),
        )

    cell_stmt = (
        select(H3DemandCell)
        .where(H3DemandCell.forecast_id == forecast.id)
        .where(H3DemandCell.demand_persons > 0)   # skip zero-demand cells
        .order_by(H3DemandCell.demand_persons.desc())
    )
    cell_result = await db.execute(cell_stmt)
    cells = cell_result.scalars().all()

    features = []
    for cell in cells:
        try:
            # h3.cell_to_boundary returns list of (lat, lon) tuples
            boundary = _h3.cell_to_boundary(cell.h3_id)
            # GeoJSON uses [lon, lat] — swap from H3's (lat, lon)
            coordinates = [[lon, lat] for lat, lon in boundary]
            # Close the ring
            coordinates.append(coordinates[0])
        except Exception:
            continue  # skip cells with invalid H3 IDs

        category = cell.demand_category or "LOW"
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
            "properties": {
                "h3_id":           cell.h3_id,
                "demand_persons":  cell.demand_persons,
                "demand_category": category,
                "color":           _CATEGORY_COLOR.get(category, "#22c55e"),
                "opacity":         _CATEGORY_OPACITY.get(category, 0.35),
                "horizon_minutes": horizon,
                "data_source":     "SIMULATED",
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "event_id":        event_id,
            "forecast_id":     forecast.id,
            "horizon_minutes": horizon,
            "total_demand":    forecast.total_demand,
            "peak_zone_h3":    forecast.peak_zone_h3,
            "feature_count":   len(features),
            "data_source":     "SIMULATED",
            "note":            "All crowd data is SIMULATED. Not real-time or authoritative.",
        },
    }
