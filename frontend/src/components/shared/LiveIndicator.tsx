/** LiveIndicator — animated dot for WebSocket-connected real-time data. */

import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";

export function LiveIndicator({ className }: { className?: string }) {
  const wsStatus = useAppStore((s) => s.wsStatus);
  const isLive = wsStatus === "connected";

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <span
        className={cn(
          "w-2 h-2 rounded-full",
          isLive ? "bg-primary-500 live-dot" : "bg-text-muted"
        )}
      />
      <span className={cn("text-xs font-mono uppercase tracking-widest", isLive ? "text-primary-400" : "text-text-muted")}>
        {isLive ? "LIVE" : wsStatus === "reconnecting" ? "RECONNECTING" : "OFFLINE"}
      </span>
    </div>
  );
}
