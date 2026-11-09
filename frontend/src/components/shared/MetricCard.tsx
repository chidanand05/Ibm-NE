/** MetricCard — large numerical display with label and optional trend. */

import { cn, formatNumber } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { GlassCard } from "./GlassCard";

interface MetricCardProps {
  label: string;
  value: number | string;
  unit?: string;
  trend?: "up" | "down" | "flat";
  trendValue?: string;
  icon?: React.ReactNode;
  accentColor?: string; // Tailwind text color class
  isSimulated?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  unit,
  trend,
  trendValue,
  icon,
  accentColor = "text-primary-400",
  isSimulated = false,
  className,
}: MetricCardProps) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up" ? "text-severity-low" :
    trend === "down" ? "text-severity-critical" :
    "text-text-muted";

  return (
    <GlassCard className={cn("relative overflow-hidden", className)}>
      {/* Simulated badge */}
      {isSimulated && (
        <span className="absolute top-3 right-3 text-[10px] font-semibold text-simulated bg-simulated/10 border border-simulated/25 px-1.5 py-0.5 rounded">
          SIM
        </span>
      )}

      {/* Icon */}
      {icon && (
        <div className={cn("mb-3", accentColor)}>{icon}</div>
      )}

      {/* Value */}
      <div className={cn("text-4xl font-bold font-mono leading-none", accentColor)}>
        {typeof value === "number" ? formatNumber(value) : value}
        {unit && <span className="text-lg text-text-secondary ml-1">{unit}</span>}
      </div>

      {/* Label */}
      <p className="text-text-secondary text-sm mt-2">{label}</p>

      {/* Trend */}
      {trend && (
        <div className={cn("flex items-center gap-1 mt-2 text-xs", trendColor)}>
          <TrendIcon size={12} />
          {trendValue && <span>{trendValue}</span>}
        </div>
      )}
    </GlassCard>
  );
}
