/**
 * AgentTimeline — visualizes agent execution pipeline progress.
 *
 * Shows all 7 agents in pipeline order with status indicators,
 * duration, and LLM fallback flags.
 *
 * Usage:
 *   <AgentTimeline sessionId="..." executions={[...]} currentPhase="planner" />
 */

import { AgentStatusBadge } from "@/components/shared/AgentStatusBadge";
import { agentDisplayName, agentHexColor } from "@/lib/utils";
import { CheckCircle, Clock, Loader2, AlertTriangle } from "lucide-react";

interface AgentTimelineEntry {
  agent_id: string;
  status: string;
  duration_ms: number | null;
  llm_fallback: boolean | null;
}

interface AgentTimelineProps {
  executions: AgentTimelineEntry[];
  currentPhase?: string | null;
  sessionId?: string;
  className?: string;
}

const PIPELINE_ORDER = [
  "event_intelligence",
  "egress_forecast",
  "supply",
  "police_coordination",
  "planner",
  "citizen_guidance",
  "learning",
] as const;

const PARALLEL_AGENTS = new Set(["egress_forecast", "supply", "police_coordination"]);

export function AgentTimeline({
  executions,
  currentPhase,
  sessionId,
  className = "",
}: AgentTimelineProps) {
  const execMap: Record<string, AgentTimelineEntry> = {};
  for (const exec of executions) {
    execMap[exec.agent_id] = exec;
  }

  return (
    <div className={`space-y-1 ${className}`}>
      {sessionId && (
        <p className="text-text-muted text-xs mb-2">Session: {sessionId.slice(0, 16)}…</p>
      )}

      {PIPELINE_ORDER.map((agentId, i) => {
        const exec = execMap[agentId];
        const status = exec?.status ?? "PENDING";
        const isParallel = PARALLEL_AGENTS.has(agentId);
        const isFirst = i === 0;
        const isLast = i === PIPELINE_ORDER.length - 1;

        return (
          <div key={agentId} className="relative flex gap-3 items-start">
            {/* Connector line */}
            <div className="flex flex-col items-center">
              {/* Status icon */}
              <div className={`w-6 h-6 rounded-full border flex items-center justify-center shrink-0 ${
                status === "COMPLETED"
                  ? "bg-green-500/20 border-green-500/40"
                  : status === "RUNNING"
                  ? "bg-primary-500/20 border-primary-500/40"
                  : status === "FAILED"
                  ? "bg-red-500/20 border-red-500/40"
                  : "bg-bg-surface border-white/[0.08]"
              }`}>
                {status === "COMPLETED"
                  ? <CheckCircle size={12} className="text-green-400" />
                  : status === "RUNNING"
                  ? <Loader2 size={12} className="text-primary-400 animate-spin" />
                  : status === "FAILED"
                  ? <AlertTriangle size={12} className="text-red-400" />
                  : <Clock size={12} className="text-text-muted" />
                }
              </div>

              {/* Connector line down */}
              {!isLast && (
                <div className={`w-px flex-1 mt-1 mb-0 min-h-[20px] ${
                  status === "COMPLETED" ? "bg-green-500/30" : "bg-white/[0.06]"
                }`} />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs font-semibold"
                    style={{ color: agentHexColor(agentId) }}
                  >
                    {agentDisplayName(agentId)}
                  </span>
                  {isParallel && (
                    <span className="text-text-muted text-xs opacity-60">(parallel)</span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {exec?.llm_fallback && (
                    <span className="text-simulated text-xs">fallback</span>
                  )}
                  {exec?.duration_ms != null && (
                    <span className="text-text-muted text-xs">{exec.duration_ms}ms</span>
                  )}
                  <AgentStatusBadge
                    status={status as "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"}
                  />
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
