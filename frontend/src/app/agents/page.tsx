"use client";

import { useEffect, useState, useCallback } from "react";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { AgentStatusBadge } from "@/components/shared/AgentStatusBadge";
import { agentDisplayName, agentHexColor } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import type { AgentExecutionRecord } from "@/lib/api";
import { RefreshCw, Play, AlertTriangle, CheckCircle } from "lucide-react";

const AGENTS = [
  "event_intelligence", "egress_forecast", "supply",
  "police_coordination", "planner", "citizen_guidance", "learning",
] as const;

const DEMO_EVENT_ID = "20000000-0000-0000-0000-000000000001";

export default function AgentsPage() {
  const [executions, setExecutions] = useState<AgentExecutionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<string | null>(null);

  const loadExecutions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.getAgentExecutions();
      setExecutions(res.executions);
    } catch {
      // API unavailable — show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExecutions();
  }, [loadExecutions]);

  // Poll session status when a run is in progress
  useEffect(() => {
    if (!sessionId || !running) return;
    const interval = setInterval(async () => {
      try {
        const status = await apiClient.getSessionStatus(sessionId);
        if (status.status !== "RUNNING") {
          setRunning(false);
          setRunResult(`Session complete: ${status.status}. Phase: ${status.current_phase ?? "done"}`);
          clearInterval(interval);
          loadExecutions();
        }
      } catch {
        // ignore transient errors
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [sessionId, running, loadExecutions]);

  const triggerRun = async () => {
    setRunning(true);
    setRunError(null);
    setRunResult(null);
    try {
      const res = await apiClient.triggerAgentRun({
        event_id: DEMO_EVENT_ID,
        event_name: "RCB vs CSK IPL 2026",
        attendance: 30000,
        trigger_type: "MANUAL",
      });
      setSessionId(res.session_id);
      setRunResult(`Session ${res.session_id.slice(0, 8)}… — ${res.status}`);
      setTimeout(loadExecutions, 3000);
    } catch (err) {
      setRunning(false);
      setRunError(err instanceof Error ? err.message : "Failed to start session");
    }
  };

  // Group executions by session
  const latestExecByAgent: Record<string, AgentExecutionRecord> = {};
  for (const exec of executions) {
    if (!latestExecByAgent[exec.agent_id]) {
      latestExecByAgent[exec.agent_id] = exec;
    }
  }

  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />
      <PageHeader
        title="Agent Workflow"
        description="Monitor all 7 AI agents in the orchestration pipeline."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={loadExecutions}
              disabled={loading}
              className="p-1.5 rounded text-text-muted hover:text-text-primary transition-colors disabled:opacity-40"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
            <button
              onClick={triggerRun}
              disabled={running}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-primary-500/20 border border-primary-500/40 text-primary-400 text-xs font-semibold hover:bg-primary-500/30 transition-colors disabled:opacity-50"
            >
              <Play size={12} />
              {running ? "Running…" : "Trigger Run"}
            </button>
          </div>
        }
      />

      {runError && (
        <GlassCard variant="warning" className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-simulated shrink-0" />
          <p className="text-simulated text-xs">{runError}</p>
        </GlassCard>
      )}

      {runResult && (
        <GlassCard className="flex items-center gap-2 border-green-500/20">
          <CheckCircle size={14} className="text-green-400 shrink-0" />
          <p className="text-green-300 text-xs">{runResult}</p>
        </GlassCard>
      )}

      {/* Agent cards — show latest execution status */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {AGENTS.map((agentId) => {
          const exec = latestExecByAgent[agentId];
          const status = exec?.status ?? "PENDING";
          return (
            <GlassCard key={agentId} padding="default">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: agentHexColor(agentId) }}
                  />
                  <span className="text-text-primary text-sm font-semibold">
                    {agentDisplayName(agentId)}
                  </span>
                </div>
                <AgentStatusBadge status={status as "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"} />
              </div>

              {exec ? (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-text-secondary">
                    <span>Duration</span>
                    <span>{exec.duration_ms != null ? `${exec.duration_ms}ms` : "—"}</span>
                  </div>
                  <div className="flex justify-between text-xs text-text-secondary">
                    <span>Model</span>
                    <span className="text-text-muted truncate max-w-[150px]">
                      {exec.model_used ?? (exec.llm_fallback ? "fallback" : "—")}
                    </span>
                  </div>
                  {exec.llm_fallback && (
                    <p className="text-simulated text-xs">⚠ LLM fallback (deterministic)</p>
                  )}
                  <div className="text-text-muted text-xs mt-1">
                    Session: {exec.session_id.slice(0, 8)}…
                  </div>
                </div>
              ) : (
                <p className="text-text-muted text-xs">
                  No execution recorded yet.
                </p>
              )}
            </GlassCard>
          );
        })}
      </div>

      {/* Recent executions table */}
      {executions.length > 0 && (
        <div>
          <h2 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-3">
            Recent Executions ({executions.length})
          </h2>
          <GlassCard padding="compact">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-text-secondary">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">Agent</th>
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">Status</th>
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">Duration</th>
                    <th className="text-left py-2 pr-4 text-text-muted font-medium">LLM</th>
                    <th className="text-left py-2 text-text-muted font-medium">Session</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.slice(0, 21).map((e) => (
                    <tr key={e.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="py-1.5 pr-4 font-medium" style={{ color: agentHexColor(e.agent_id) }}>
                        {agentDisplayName(e.agent_id)}
                      </td>
                      <td className="py-1.5 pr-4">
                        <AgentStatusBadge status={e.status as "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"} />
                      </td>
                      <td className="py-1.5 pr-4">{e.duration_ms != null ? `${e.duration_ms}ms` : "—"}</td>
                      <td className="py-1.5 pr-4">
                        {e.llm_fallback === true
                          ? <span className="text-simulated">fallback</span>
                          : e.llm_fallback === false
                          ? <span className="text-green-400">live</span>
                          : "—"}
                      </td>
                      <td className="py-1.5 text-text-muted">{e.session_id.slice(0, 8)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
