/**
 * SimulatedDataBanner — mandatory on every card/page showing synthetic data.
 * NEVER dismissible. This is a governance requirement.
 */

import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SimulatedDataBannerProps {
  /** "strip" = full-width banner above content; "badge" = corner tag on a card */
  variant?: "strip" | "badge";
  className?: string;
}

export function SimulatedDataBanner({
  variant = "strip",
  className,
}: SimulatedDataBannerProps) {
  if (variant === "badge") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold",
          "bg-simulated/10 border border-simulated/30 text-simulated",
          className
        )}
      >
        <AlertTriangle size={10} />
        SIMULATED
      </span>
    );
  }

  return (
    <div
      className={cn(
        "w-full flex items-center gap-2 px-4 py-2.5",
        "bg-simulated/[0.08] border border-simulated/25 rounded-md",
        className
      )}
      role="alert"
      aria-label="Simulated data warning"
    >
      <AlertTriangle size={14} className="text-simulated shrink-0" />
      <p className="text-simulated text-xs font-semibold tracking-wide">
        ⚠ SIMULATED DATA — This information is synthetically generated for demonstration purposes.
        Do not use for real operational decisions.
      </p>
    </div>
  );
}
