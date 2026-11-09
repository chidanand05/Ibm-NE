"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { GlassCard } from "@/components/shared/GlassCard";
import { DemandLegend } from "@/components/map/DemandLegend";
import type { H3FeatureCollection } from "@/components/map/H3Layer";
import { apiClient } from "@/lib/api";
import { RCB_DEMO_EVENT_ID } from "@/lib/constants";
import { AlertCircle, RefreshCw } from "lucide-react";
import type { Map as MapLibreMap } from "maplibre-gl";

// Dynamic imports — MapLibre and H3Layer cannot run in SSR
const BaseMap = dynamic(
  () => import("@/components/map/BaseMap").then((m) => m.BaseMap),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center bg-bg-surface rounded-md">
        <p className="text-text-muted text-sm animate-pulse">Loading map…</p>
      </div>
    ),
  }
);

const H3Layer = dynamic(
  () => import("@/components/map/H3Layer").then((m) => m.H3Layer),
  { ssr: false }
);

type Horizon = 20 | 40;

export default function MapPage() {
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [horizon, setHorizon] = useState<Horizon>(20);
  const [geojson, setGeojson] = useState<H3FeatureCollection | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulatedAt] = useState<string | undefined>(undefined);

  const onMapReady = useCallback((map: MapLibreMap) => {
    setMapInstance(map);
  }, []);

  const loadH3Data = useCallback(
    async (h: Horizon) => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient.getH3GeoJSON(RCB_DEMO_EVENT_ID, h);
        setGeojson(data as H3FeatureCollection);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        // 404 means simulation hasn't been run yet — not a hard error
        if (msg.includes("404") || msg.includes("No forecast found")) {
          setError(
            `No simulation data for T+${h} min. ` +
              "Run the simulation from the Dashboard first."
          );
        } else {
          setError(`Failed to load H3 data: ${msg}`);
        }
        setGeojson(null);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Load H3 data when map is ready or horizon changes
  useEffect(() => {
    if (mapInstance) {
      void loadH3Data(horizon);
    }
  }, [mapInstance, horizon, loadH3Data]);

  const totalDemand = geojson?.metadata?.total_demand;
  const cellCount = geojson?.metadata?.feature_count;

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      <SimulatedDataBanner />

      {/* Controls row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-text-muted text-sm">Forecast horizon:</span>
        {([20, 40] as Horizon[]).map((h) => (
          <button
            key={h}
            onClick={() => setHorizon(h)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              horizon === h
                ? "bg-primary-500 text-white"
                : "bg-bg-surface text-text-muted border border-white/[0.08] hover:border-primary-500/50"
            }`}
          >
            T+{h} min
          </button>
        ))}

        <button
          onClick={() => void loadH3Data(horizon)}
          disabled={loading}
          className="ml-auto flex items-center gap-1.5 px-3 py-1 rounded text-xs text-text-muted border border-white/[0.08] hover:border-primary-500/50 disabled:opacity-50 transition-colors"
          aria-label="Refresh H3 demand data"
        >
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Map container fills remaining height */}
      <div className="flex-1 relative rounded-md overflow-hidden border border-white/[0.06]">
        <BaseMap className="w-full h-full" onMapReady={onMapReady} />

        {/* H3 layer — renders inside MapLibre, no DOM */}
        <H3Layer map={mapInstance} geojson={geojson} />

        {/* Error overlay */}
        {error && (
          <div className="absolute top-4 left-4 z-10 w-80">
            <GlassCard padding="compact">
              <div className="flex items-start gap-2">
                <AlertCircle size={14} className="text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-amber-400 text-xs font-semibold">No Simulation Data</p>
                  <p className="text-text-muted text-xs mt-1 leading-relaxed">{error}</p>
                </div>
              </div>
            </GlassCard>
          </div>
        )}

        {/* Legend — bottom right */}
        {!error && (
          <div className="absolute bottom-4 right-4 z-10">
            <DemandLegend
              horizon={horizon}
              totalDemand={totalDemand}
              cellCount={cellCount}
              simulatedAt={simulatedAt}
            />
          </div>
        )}
      </div>
    </div>
  );
}
