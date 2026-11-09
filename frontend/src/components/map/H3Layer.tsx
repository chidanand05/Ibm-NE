"use client";

/**
 * H3Layer — renders H3 demand hexagons on the MapLibre map.
 *
 * Takes GeoJSON FeatureCollection from the backend /api/v1/map/h3/{eventId}/geojson
 * and adds it as a fill + outline layer on top of the base map.
 *
 * Architecture:
 * - Uses MapLibre GL source/layer API (not deck.gl — keeps dependency simple).
 * - Layer is added after map `load` event via the `onMapReady` callback.
 * - Re-renders when `geojson` prop changes (old source is removed and replaced).
 * - All data carries data_source="SIMULATED" — never represents real crowd data.
 */

import { useEffect, useRef } from "react";
import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";

const H3_SOURCE_ID = "h3-demand-source";
const H3_FILL_LAYER_ID = "h3-demand-fill";
const H3_OUTLINE_LAYER_ID = "h3-demand-outline";

export interface H3GeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  properties: {
    h3_id: string;
    demand_persons: number;
    demand_category: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
    color: string;
    opacity: number;
    horizon_minutes: number;
    data_source: "SIMULATED";
  };
}

export interface H3FeatureCollection {
  type: "FeatureCollection";
  features: H3GeoJSONFeature[];
  metadata?: {
    event_id: string;
    forecast_id: string;
    horizon_minutes: number;
    total_demand: number;
    peak_zone_h3: string;
    feature_count: number;
    data_source: "SIMULATED";
    note: string;
  };
}

interface H3LayerProps {
  map: MapLibreMap | null;
  geojson: H3FeatureCollection | null;
}

export function H3Layer({ map, geojson }: H3LayerProps) {
  const prevGeojsonRef = useRef<H3FeatureCollection | null>(null);

  useEffect(() => {
    if (!map || !geojson) return;

    const addOrUpdateLayer = () => {
      // Remove existing source/layers if present
      if (map.getLayer(H3_OUTLINE_LAYER_ID)) map.removeLayer(H3_OUTLINE_LAYER_ID);
      if (map.getLayer(H3_FILL_LAYER_ID)) map.removeLayer(H3_FILL_LAYER_ID);
      if (map.getSource(H3_SOURCE_ID)) map.removeSource(H3_SOURCE_ID);

      // Add H3 demand source
      map.addSource(H3_SOURCE_ID, {
        type: "geojson",
        data: geojson as GeoJSON.GeoJSON,
      });

      // Fill layer — color from demand category
      map.addLayer({
        id: H3_FILL_LAYER_ID,
        type: "fill",
        source: H3_SOURCE_ID,
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": ["get", "opacity"],
        },
      });

      // Outline layer — subtle white border
      map.addLayer({
        id: H3_OUTLINE_LAYER_ID,
        type: "line",
        source: H3_SOURCE_ID,
        paint: {
          "line-color": "rgba(255,255,255,0.3)",
          "line-width": 0.5,
        },
      });
    };

    // If map is already loaded, add immediately; otherwise wait for load
    if (map.isStyleLoaded()) {
      addOrUpdateLayer();
    } else {
      map.once("load", addOrUpdateLayer);
    }

    prevGeojsonRef.current = geojson;

    // Cleanup on unmount
    return () => {
      if (map && !map._removed) {
        if (map.getLayer(H3_OUTLINE_LAYER_ID)) map.removeLayer(H3_OUTLINE_LAYER_ID);
        if (map.getLayer(H3_FILL_LAYER_ID)) map.removeLayer(H3_FILL_LAYER_ID);
        if (map.getSource(H3_SOURCE_ID)) map.removeSource(H3_SOURCE_ID);
      }
    };
  }, [map, geojson]);

  // This component renders no DOM — it operates purely via MapLibre API
  return null;
}
