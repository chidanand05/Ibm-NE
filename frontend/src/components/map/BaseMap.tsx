"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";

// Map config from env vars — default to Chinnaswamy Stadium
const CENTER_LNG = parseFloat(process.env.NEXT_PUBLIC_MAP_CENTER_LNG ?? "77.5996");
const CENTER_LAT = parseFloat(process.env.NEXT_PUBLIC_MAP_CENTER_LAT ?? "12.9789");
const ZOOM = parseFloat(process.env.NEXT_PUBLIC_MAP_ZOOM ?? "13");

// Carto Dark Matter — free, no API key required
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

interface BaseMapProps {
  className?: string;
  onMapReady?: (map: MapLibreMap) => void;
}

export function BaseMap({ className = "w-full h-full", onMapReady }: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // Dynamically import maplibre-gl (client-only)
    import("maplibre-gl").then((maplibregl) => {
      if (!containerRef.current) return;

      const map = new maplibregl.Map({
        container: containerRef.current,
        style: MAP_STYLE,
        center: [CENTER_LNG, CENTER_LAT],
        zoom: ZOOM,
        attributionControl: { compact: true },
      });

      // Add navigation controls
      map.addControl(new maplibregl.NavigationControl(), "top-right");

      // Add marker at Chinnaswamy Stadium
      const el = document.createElement("div");
      el.className = "w-4 h-4 rounded-full bg-primary-500 border-2 border-white shadow-lg";

      new maplibregl.Marker({ element: el })
        .setLngLat([CENTER_LNG, CENTER_LAT])
        .setPopup(
          new maplibregl.Popup({ offset: 25 }).setHTML(
            '<div style="color:#050D1A;font-size:12px;font-weight:600">M. Chinnaswamy Stadium</div>'
          )
        )
        .addTo(map);

      mapRef.current = map;
      onMapReady?.(map);
    });

    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [onMapReady]);

  return (
    <div
      ref={containerRef}
      className={className}
      aria-label="Crowd intelligence map centered on Bengaluru"
    />
  );
}
