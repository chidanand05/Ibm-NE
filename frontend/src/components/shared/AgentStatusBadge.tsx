/** AgentStatusBadge — pill showing agent execution state. */

import { cn } from "@/lib/utils";
import type { AgentStatus } from "@/types";

interface AgentStatusBadgeProps {
  status: AgentStatus;
  className?: string;
}

const CONFIG: Record<AgentStatus, { label: string; dot: string; bg: string; text: string }> = {
  PENDING:   { label: "Pending",   dot: "bg-status-pending",   bg: "bg-status-pending/10",   text: "text-status-pending" },
  RUNNING:   { label: "Running",   dot: "bg-status-running",   bg: "bg-status-running/10",   text: "text-status-running" },
  COMPLETED: { label: "Completed", dot: "bg-status-completed", bg: "bg-status-completed/10", text: "text-status-completed" },
  FAILED:    { label: "Failed",    dot: "bg-status-failed",    bg: "bg-status-failed/10",    text: "text-status-failed" },
  TIMEOUT:   { label: "Timeout",   dot: "bg-status-timeout",   bg: "bg-status-timeout/10",   text: "text-status-timeout" },
};

export function AgentStatusBadge({ status, className }: AgentStatusBadgeProps) {
  const { label, dot, bg, text } = CONFIG[status] ?? CONFIG.PENDING;
  return (
    <span className={cn("status-badge", bg, text, className)}>
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full shrink-0",
          dot,
          status === "RUNNING" && "animate-pulse-slow"
        )}
      />
      {label}
    </span>
  );
}
