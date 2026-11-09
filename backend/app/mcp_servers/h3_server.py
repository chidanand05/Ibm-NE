"""
MCP Server 4 — H3 Geospatial Server (in-process).

Pure functions wrapping the h3 v4 library.  No async, no I/O, no external APIs.
All functions are synchronous and side-effect free.

Promotion path: wrap each function in @mcp.tool() to make this a real
Streamable HTTP MCP server with zero logic changes.
"""

from __future__ import annotations

import math

import h3 as _h3


# ── Public API ────────────────────────────────────────────────────────────────

def latlon_to_h3(lat: float, lon: float, resolution: int = 7) -> str:
    """
    Convert a latitude/longitude to an H3 cell index string.

    Parameters
    ----------
    lat         Latitude (-90 to 90).
    lon         Longitude (-180 to 180).
    resolution  H3 resolution (0–15). Default 7 (~1.2 km edge length).

    Returns
    -------
    H3 cell index string, e.g. "87194ad3fffffff".
    """
    if not (0 <= resolution <= 15):
        raise ValueError(f"resolution must be 0–15, got {resolution}")
    return _h3.latlng_to_cell(lat, lon, resolution)


def get_h3_neighbors(h3_id: str, k: int = 1) -> list[str]:
    """
    Return all H3 cells within grid distance k of h3_id (k-ring).

    The result includes h3_id itself (distance 0).

    Parameters
    ----------
    h3_id  Valid H3 cell index.
    k      Grid distance (0 = center only, 1 = immediate ring, etc.).

    Returns
    -------
    List of H3 cell index strings (unordered).
    """
    if not _h3.is_valid_cell(h3_id):
        raise ValueError(f"Invalid H3 cell ID: {h3_id!r}")
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    return list(_h3.grid_disk(h3_id, k))


def get_cells_in_radius(
    lat: float,
    lon: float,
    radius_km: float,
    resolution: int = 7,
) -> list[str]:
    """
    Return all H3 cells at `resolution` whose center is within `radius_km` of lat/lon.

    Uses a grid_disk approach: computes the k-ring radius that covers radius_km at the
    given resolution, then filters cells whose centers fall within radius_km.

    Parameters
    ----------
    lat, lon    Centre point.
    radius_km   Radius in kilometres.
    resolution  H3 resolution (default 7).

    Returns
    -------
    List of H3 cell index strings.
    """
    if radius_km <= 0:
        raise ValueError(f"radius_km must be > 0, got {radius_km}")

    center = _h3.latlng_to_cell(lat, lon, resolution)

    # Average edge length at each resolution (km) — used to estimate k
    # h3.average_hexagon_edge_length(resolution, unit='km') works in h3 v4
    try:
        edge_km = _h3.average_hexagon_edge_length(resolution, unit="km")
    except Exception:
        edge_km = max(0.001, radius_km / 10)

    # Estimate k: each ring step ≈ 2 × edge_length in km; minimum 1 so we always
    # get at least the immediate ring (7 cells at resolution 7).
    k = max(1, math.ceil(radius_km / (2 * edge_km)))

    candidates = list(_h3.grid_disk(center, k))

    # Filter by actual haversine distance — the center cell always passes
    # (distance from the query point to the center cell's centroid is ≤ half
    # the edge length, which is always ≤ radius_km for any valid radius).
    result = [center]  # center cell always included
    for cell in candidates:
        if cell == center:
            continue
        clat, clon = _h3.cell_to_latlng(cell)
        if _haversine_km(lat, lon, clat, clon) <= radius_km:
            result.append(cell)
    return result


def h3_to_geojson(h3_ids: list[str]) -> dict:
    """
    Convert a list of H3 cell IDs to a GeoJSON FeatureCollection.

    Each feature has:
    - geometry: Polygon (hexagon boundary)
    - properties: {h3_id, resolution}

    Parameters
    ----------
    h3_ids  List of valid H3 cell index strings.

    Returns
    -------
    GeoJSON FeatureCollection dict.
    """
    features = []
    for cell_id in h3_ids:
        if not _h3.is_valid_cell(cell_id):
            raise ValueError(f"Invalid H3 cell ID: {cell_id!r}")

        # cell_to_boundary returns list of (lat, lon) tuples
        boundary = _h3.cell_to_boundary(cell_id)
        # GeoJSON uses [lon, lat] order; close the ring by repeating first vertex
        coords = [[lon, lat] for lat, lon in boundary]
        coords.append(coords[0])  # close polygon

        resolution = _h3.get_resolution(cell_id)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords],
            },
            "properties": {
                "h3_id": cell_id,
                "resolution": resolution,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_cell_center(h3_id: str) -> tuple[float, float]:
    """
    Return the (lat, lon) centre of an H3 cell.

    Parameters
    ----------
    h3_id  Valid H3 cell index string.

    Returns
    -------
    (latitude, longitude) tuple.
    """
    if not _h3.is_valid_cell(h3_id):
        raise ValueError(f"Invalid H3 cell ID: {h3_id!r}")
    return _h3.cell_to_latlng(h3_id)


def h3_distance(h3_a: str, h3_b: str) -> int:
    """
    Return the H3 grid distance between two cells at the same resolution.

    Grid distance is the minimum number of cell steps to move from h3_a to h3_b.

    Parameters
    ----------
    h3_a, h3_b  Valid H3 cell index strings at the same resolution.

    Returns
    -------
    Integer grid distance.

    Raises
    ------
    ValueError  If either cell is invalid or they are at different resolutions.
    """
    if not _h3.is_valid_cell(h3_a):
        raise ValueError(f"Invalid H3 cell ID: {h3_a!r}")
    if not _h3.is_valid_cell(h3_b):
        raise ValueError(f"Invalid H3 cell ID: {h3_b!r}")
    res_a = _h3.get_resolution(h3_a)
    res_b = _h3.get_resolution(h3_b)
    if res_a != res_b:
        raise ValueError(
            f"Cells must be at the same resolution; got {res_a} and {res_b}"
        )
    return _h3.grid_distance(h3_a, h3_b)


# ── Internal ──────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
