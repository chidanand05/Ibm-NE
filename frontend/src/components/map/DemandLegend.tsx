"use client";

/**
 * DemandLegend — map overlay legend for H3 demand categories.
 *
 * Shows LOW/MEDIUM/HIGH/CRITICAL color coding.
 * Never dismissible — always visible when map is showing crowd data.
 * Always carries the SIMULATED data notice.
 */

interface LegendEntry {
  category: string;
  color: string;
  description: string;
}

const LEGEND: LegendEntry[] = [
  { category: "CRITICAL", color: "#ef4444", description: "3,000+ persons" },
  { category: "HIGH",     color: "#f97316", description: "1,500–2,999 persons" },
  { category: "MEDIUM",   color: "#eab308", description: "500–1,499 persons" },
  { category: "LOW",      color: "#22c55e", description: "< 500 persons" },
];

interface DemandLegendProps {
  horizon: 20 | 40;
  totalDemand?: number;
  cellCount?: number;
  /** ISO timestamp of when simulation was last run */
  simulatedAt?: string;
}

export function DemandLegend({
  horizon,
  totalDemand,
  cellCount,
  simulatedAt,
}: DemandLegendProps) {
  return (
    <div className="bg-bg-surface/90 backdrop-blur-sm border border-white/[0.08] rounded-md p-3 w-52">
      {/* Header */}
      <div className="mb-2">
        <p className="text-text-primary text-xs font-semibold">
          Crowd Demand — T+{horizon} min
        </p>
        {totalDemand !== undefined && (
          <p className="text-text-muted text-xs mt-0.5">
            {totalDemand.toLocaleString()} persons outside venue
          </p>
        )}
      </div>

      {/* Color scale */}
      <div className="space-y-1.5">
        {LEGEND.map((entry) => (
          <div key={entry.category} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-sm shrink-0"
              style={{ backgroundColor: entry.color, opacity: 0.85 }}
            />
            <div>
              <span className="text-text-primary text-xs font-medium">
                {entry.category}
              </span>
              <span className="text-text-muted text-xs ml-1.5">
                {entry.description}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Cell count */}
      {cellCount !== undefined && (
        <p className="text-text-muted text-xs mt-2 pt-2 border-t border-white/[0.06]">
          {cellCount} H3 cells (resolution 7)
        </p>
      )}

      {/* Simulated data notice — NEVER removable */}
      <div className="mt-2 pt-2 border-t border-white/[0.06]">
        <p className="text-amber-400 text-xs font-medium">⚠ SIMULATED DATA</p>
        <p className="text-text-muted text-xs mt-0.5 leading-tight">
          Not real-time. For demonstration only.
        </p>
        {simulatedAt && (
          <p className="text-text-muted text-xs mt-0.5">
            Run: {new Date(simulatedAt).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}
