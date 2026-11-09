"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, User, Wifi, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export function TopBar() {
  const wsStatus = useAppStore((s) => s.wsStatus);

  const { data: health, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.getHealth(),
    refetchInterval: 30_000,
    retry: 1,
  });

  const systemStatus = isError
    ? "error"
    : health?.status === "ok"
    ? "ok"
    : "degraded";

  return (
    <header className="h-16 flex items-center justify-between px-4 bg-bg-surface border-b border-white/[0.06] shrink-0 z-30">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-primary-500/20 border border-primary-500/40 flex items-center justify-center">
          <span className="text-primary-400 font-bold text-sm font-mono">NX</span>
        </div>
        <div className="hidden sm:block">
          <p className="text-text-primary font-semibold text-sm leading-none">Namma Exodus</p>
          <p className="text-text-muted text-xs mt-0.5">Crowd Exit Command Centre</p>
        </div>
      </div>

      {/* Center: Active event (populated in Milestone 2) */}
      <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06]">
        <Activity size={14} className="text-text-muted" />
        <span className="text-text-muted text-xs font-mono">No active event</span>
      </div>

      {/* Right: Status indicators */}
      <div className="flex items-center gap-3">
        {/* WebSocket status */}
        <div
          className="flex items-center gap-1.5"
          title={`WebSocket: ${wsStatus}`}
        >
          {wsStatus === "connected" ? (
            <Wifi size={14} className="text-severity-low" />
          ) : (
            <WifiOff size={14} className="text-text-muted" />
          )}
          <span className="hidden sm:block text-xs text-text-muted capitalize">{wsStatus}</span>
        </div>

        {/* Backend health */}
        <div
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded-full text-xs",
            systemStatus === "ok"     && "text-severity-low",
            systemStatus === "degraded" && "text-severity-medium",
            systemStatus === "error"  && "text-severity-critical"
          )}
          title={`Backend: ${systemStatus}`}
        >
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              systemStatus === "ok"      && "bg-severity-low",
              systemStatus === "degraded" && "bg-severity-medium",
              systemStatus === "error"   && "bg-severity-critical"
            )}
          />
          <span className="hidden sm:block font-mono uppercase tracking-wide">
            {systemStatus === "ok" ? "API OK" : systemStatus}
          </span>
        </div>

        {/* User avatar placeholder */}
        <div className="w-8 h-8 rounded-full bg-bg-elevated border border-white/[0.08] flex items-center justify-center">
          <User size={14} className="text-text-muted" />
        </div>
      </div>
    </header>
  );
}
