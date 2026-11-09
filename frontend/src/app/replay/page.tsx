"use client";

import { useState, useCallback } from "react";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Play, Clock, CheckCircle, Loader2, AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api";
import type { ReplayStatusResponse } from "@/lib/api";

const DEMO_STEPS = [
  { phase: "Phase 1", agent: "Event Intelligence",  description: "Detects RCB match ending, estimates 33,000 attendees" },
  { phase: "Phase 2", agent: "Egress Forecast",      description: "Predicts H3 demand cells — peak at T+15 mins" },
  { phase: "Phase 2", agent: "Supply",               description: "Assesses metro, BMTC, auto availability" },
  { phase: "Phase 2", agent: "Police Coordination",  description: "Identifies MG Road congestion, recommends diversions" },
  { phase: "Phase 3", agent: "Planner",              description: "Compares strategies, recommends coordinated plan" },
  { phase: "Gate",    agent: "Officer Review",        description: "Human officer approves or rejects the plan" },
  { phase: "Phase 4", agent: "Citizen Guidance",     description: "Generates EN/KN/HI gate instructions" },
  { phase: "Phase 5", agent: "Learning",             description: "Stores outcome for future improvements" },
];

const PHASE_TO_AGENTS: Record<string, string[]> = {
  event_intel: ["event_intelligence"],
  parallel: ["egress_forecast", "supply", "police_coordination"],
  planner: ["planner"],
  approval: ["Officer Review"],
  guidance: ["citizen_guidance"],
  learning: ["learning"],
  done: ["learning"],
};

export default function ReplayPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState<ReplayStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoApproving, setAutoApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<ReturnType<typeof setInterval> | null>(null);

  const startReplay = useCallback(async () => {
    setLoading(true);
    setError(null);
    setStatus(null);
    if (pollInterval) clearInterval(pollInterval);

    try {
      const res = await apiClient.startReplay();
      setSessionId(res.session_id);

      // Poll for status
      const interval = setInterval(async () => {
        try {
          const s = await apiClient.getReplayStatus(res.session_id);
          setStatus(s);
          if (s.completed || s.approval_status === "PENDING_APPROVAL" && !s.completed) {
            // Don't stop polling until done
          }
          if (s.completed) {
            clearInterval(interval);
            setPollInterval(null);
          }
        } catch {
          // ignore transient
        }
      }, 2000);
      setPollInterval(interval);

      // Initial status fetch
      const initialStatus = await apiClient.getReplayStatus(res.session_id);
      setStatus(initialStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start replay");
    } finally {
      setLoading(false);
    }
  }, [pollInterval]);

  const autoApprove = useCallback(async () => {
    if (!sessionId) return;
    setAutoApproving(true);
    try {
      await apiClient.autoApproveReplay(sessionId);
      // Final status will come from polling
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auto-approve failed");
    } finally {
      setAutoApproving(false);
    }
  }, [sessionId]);

  const completedAgents = new Set(status?.agents_completed ?? []);
  const currentPhase = status?.current_phase ?? "";
  const activeAgents = new Set(PHASE_TO_AGENTS[currentPhase] ?? []);

  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />
      <PageHeader
        title="Demo Replay"
        description="One-click simulation of an RCB match exit scenario at M. Chinnaswamy Stadium."
      />

      {/* Big replay button */}
      <GlassCard className="flex flex-col items-center py-12 gap-4">
        <div className={`w-20 h-20 rounded-full border flex items-center justify-center transition-colors ${
          loading ? "bg-primary-500/20 border-primary-500/50" : "bg-primary-500/10 border-primary-500/30"
        }`}>
          {loading
            ? <Loader2 size={32} className="text-primary-400 animate-spin" />
            : status?.completed
            ? <CheckCircle size={32} className="text-green-400" />
            : <Play size={32} className="text-primary-400 ml-1" />
          }
        </div>
        <div className="text-center">
          <p className="text-text-primary font-semibold">Replay Chinnaswamy Match</p>
          <p className="text-text-muted text-sm mt-1">
            Simulates a full RCB match exit scenario — all 7 agents, human approval gate.
          </p>
          {sessionId && (
            <p className="text-text-muted text-xs mt-1">Session: {sessionId.slice(0, 16)}…</p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={startReplay}
            disabled={loading || (!!status && !status.completed)}
            className="px-6 py-2.5 rounded-md bg-primary-500/20 border border-primary-500/40 text-primary-400 text-sm font-semibold hover:bg-primary-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Starting…" : status?.completed ? "Replay Again" : "Start Replay"}
          </button>

          {status?.approval_status === "PENDING_APPROVAL" && !status.completed && (
            <button
              onClick={autoApprove}
              disabled={autoApproving}
              className="px-4 py-2.5 rounded-md bg-green-500/20 border border-green-500/40 text-green-400 text-sm font-semibold hover:bg-green-500/30 transition-colors disabled:opacity-50"
            >
              {autoApproving ? "Approving…" : "Auto-Approve (Demo)"}
            </button>
          )}
        </div>
      </GlassCard>

      {error && (
        <GlassCard variant="warning" className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-simulated shrink-0" />
          <p className="text-simulated text-xs">{error}</p>
        </GlassCard>
      )}

      {/* Live status */}
      {status && (
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-text-secondary text-xs font-semibold uppercase tracking-wider">
              Session Status
            </h3>
            <div className="flex items-center gap-3 text-xs">
              {status.decision_label && (
                <span className={`font-mono px-2 py-0.5 rounded ${
                  status.decision_label === "GREEN" ? "text-green-400 bg-green-500/10" :
                  status.decision_label === "AMBER" ? "text-yellow-400 bg-yellow-500/10" :
                  status.decision_label === "RED"   ? "text-orange-400 bg-orange-500/10" :
                  "text-red-400 bg-red-500/10"
                }`}>
                  {status.decision_label}
                </span>
              )}
              <span className={`text-xs font-mono ${status.completed ? "text-green-400" : "text-primary-400"}`}>
                {status.current_phase?.toUpperCase() ?? "—"}
              </span>
            </div>
          </div>
          {status.plan_summary && (
            <p className="text-text-secondary text-sm mb-2">{status.plan_summary}</p>
          )}
          {status.attendance && (
            <p className="text-text-muted text-xs">Attendance: {status.attendance.toLocaleString()} · Data: SIMULATED</p>
          )}
        </GlassCard>
      )}

      {/* Demo flow timeline */}
      <div>
        <h2 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-4">
          Demo Flow
        </h2>
        <div className="space-y-2">
          {DEMO_STEPS.map((step, i) => {
            const agentKey = step.agent.toLowerCase().replace(/ /g, "_");
            const isDone = completedAgents.has(agentKey);
            const isActive = activeAgents.has(agentKey) || activeAgents.has(step.agent);
            return (
              <div key={i} className="flex gap-3 items-start">
                <div className="flex flex-col items-center mt-1">
                  {isDone
                    ? <CheckCircle size={12} className="text-green-400" />
                    : isActive
                    ? <Loader2 size={12} className="text-primary-400 animate-spin" />
                    : <Clock size={12} className="text-text-muted" />
                  }
                  {i < DEMO_STEPS.length - 1 && (
                    <div className="w-px flex-1 bg-white/[0.06] mt-1 h-4" />
                  )}
                </div>
                <div className="flex-1 pb-2">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-mono ${isDone ? "text-green-500/70" : isActive ? "text-primary-400" : "text-primary-500/70"}`}>
                      {step.phase}
                    </span>
                    <span className={`text-xs font-semibold ${isDone ? "text-green-300" : isActive ? "text-text-primary" : "text-text-primary"}`}>
                      {step.agent}
                    </span>
                  </div>
                  <p className="text-text-muted text-xs mt-0.5">{step.description}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
