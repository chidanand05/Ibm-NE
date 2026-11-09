"use client";

import { useEffect, useState, useCallback } from "react";
import { SimulatedDataBanner } from "@/components/shared/SimulatedDataBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { MetricCard } from "@/components/shared/MetricCard";
import { LiveIndicator } from "@/components/shared/LiveIndicator";
import { AgentStatusBadge } from "@/components/shared/AgentStatusBadge";
import { Users, Train, Bus, Navigation, RefreshCw, AlertTriangle } from "lucide-react";
import { apiClient } from "@/lib/api";
import type { ForecastResponse } from "@/lib/api";

const DEMO_EVENT_ID = "20000000-0000-0000-0000-000000000001";

interface DashboardData {
  attendance: number;
  metroCapacity: number;
  bmtcBuses: number;
  autoCoverage: number;
  agentStatuses: Record<string, string>;
  forecastLoaded: boolean;
  pendingApprovals: number;
}

const AGENTS = [
  { id: "event_intelligence",  label: "Event Intel",        color: "text-agent-intel" },
  { id: "egress_forecast",     label: "Egress Forecast",    color: "text-agent-forecast" },
  { id: "supply",              label: "Supply",             color: "text-agent-supply" },
  { id: "police_coordination", label: "Police Coord.",      color: "text-agent-police" },
  { id: "planner",             label: "Planner",            color: "text-agent-planner" },
  { id: "citizen_guidance",    label: "Cit. Guidance",      color: "text-agent-citizen" },
  { id: "learning",            label: "Learning",           color: "text-agent-learning" },
];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData>({
    attendance: 0,
    metroCapacity: 0,
    bmtcBuses: 0,
    autoCoverage: 0,
    agentStatuses: {},
    forecastLoaded: false,
    pendingApprovals: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch in parallel: event data, forecast, transport, approvals
      const [eventRes, forecastRes, transportRes, approvalsRes] = await Promise.allSettled([
        apiClient.getEvent(DEMO_EVENT_ID),
        apiClient.getForecasts(DEMO_EVENT_ID, 20, 1),
        apiClient.getTransportSnapshots(DEMO_EVENT_ID, 20, undefined, 10),
        apiClient.getPendingApprovals(),
      ]);

      const attendance =
        eventRes.status === "fulfilled"
          ? (eventRes.value.estimated_attendance ?? 0)
          : 0;

      let metroCapacity = 0;
      let bmtcBuses = 0;
      if (transportRes.status === "fulfilled") {
        const snaps = transportRes.value.items ?? [];
        const metroSnap = snaps.find((s: Record<string, unknown>) => s.mode === "METRO");
        const bmtcSnap = snaps.find((s: Record<string, unknown>) => s.mode === "BMTC");
        metroCapacity = (metroSnap as Record<string, number> | undefined)?.capacity ?? 0;
        bmtcBuses = (bmtcSnap as Record<string, number> | undefined)?.vehicles_available ?? 0;
      }

      // Auto coverage = autos / demand at T+20 (as %)
      let autoCoverage = 0;
      if (transportRes.status === "fulfilled" && forecastRes.status === "fulfilled") {
        const snaps = transportRes.value.items ?? [];
        const autoSnap = snaps.find((s: Record<string, unknown>) => s.mode === "AUTO");
        const demand = forecastRes.value.items?.[0]?.total_demand ?? 1;
        const autoCapacity = (autoSnap as Record<string, number> | undefined)?.capacity ?? 0;
        autoCoverage = demand > 0 ? Math.min(100, Math.round((autoCapacity / demand) * 100)) : 0;
      }

      // Agent statuses from latest executions
      const execRes = await apiClient.getAgentExecutions().catch(() => ({ executions: [], total: 0 }));
      const agentStatuses: Record<string, string> = {};
      for (const exec of execRes.executions.slice(0, 14)) {
        // Latest status per agent
        if (!agentStatuses[exec.agent_id]) {
          agentStatuses[exec.agent_id] = exec.status;
        }
      }

      const pendingApprovals =
        approvalsRes.status === "fulfilled"
          ? approvalsRes.value.pending_count
          : 0;

      setData({
        attendance,
        metroCapacity,
        bmtcBuses,
        autoCoverage,
        agentStatuses,
        forecastLoaded: forecastRes.status === "fulfilled",
        pendingApprovals,
      });
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30_000);
    return () => clearInterval(interval);
  }, [loadData]);

  return (
    <div className="p-6 space-y-6">
      <SimulatedDataBanner />

      <PageHeader
        title="Command Centre"
        description="Real-time crowd exit prediction and transport coordination for Bengaluru."
        actions={
          <div className="flex items-center gap-3">
            {lastRefresh && (
              <span className="text-text-muted text-xs">
                Updated {lastRefresh.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={loadData}
              disabled={loading}
              className="p-1.5 rounded text-text-muted hover:text-text-primary transition-colors disabled:opacity-40"
              title="Refresh"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
            <LiveIndicator />
          </div>
        }
      />

      {error && (
        <GlassCard variant="warning" className="flex items-start gap-3">
          <AlertTriangle size={16} className="text-simulated mt-0.5 shrink-0" />
          <div>
            <p className="text-simulated text-sm font-semibold">API Unavailable</p>
            <p className="text-text-secondary text-xs mt-1">{error} — showing last known values.</p>
          </div>
        </GlassCard>
      )}

      {data.pendingApprovals > 0 && (
        <GlassCard className="flex items-center gap-3 border-yellow-500/30 bg-yellow-500/5">
          <AlertTriangle size={16} className="text-yellow-400 shrink-0" />
          <div>
            <p className="text-yellow-300 text-sm font-semibold">
              {data.pendingApprovals} action plan{data.pendingApprovals > 1 ? "s" : ""} awaiting officer approval
            </p>
            <a href="/approvals" className="text-yellow-400/70 text-xs underline hover:text-yellow-300">
              Review in Approval Centre →
            </a>
          </div>
        </GlassCard>
      )}

      {/* Metric overview from real simulator + DB data */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Expected Attendance"
          value={data.attendance}
          unit="pax"
          icon={<Users size={20} />}
          accentColor="text-agent-intel"
          isSimulated
        />
        <MetricCard
          label="Metro Capacity (T+20)"
          value={data.metroCapacity}
          unit="pph"
          icon={<Train size={20} />}
          accentColor="text-mode-metro"
          isSimulated
        />
        <MetricCard
          label="BMTC Buses"
          value={data.bmtcBuses}
          icon={<Bus size={20} />}
          accentColor="text-mode-bmtc"
          isSimulated
        />
        <MetricCard
          label="Auto Coverage"
          value={data.autoCoverage}
          unit="%"
          icon={<Navigation size={20} />}
          accentColor="text-mode-auto"
          isSimulated
        />
      </div>

      {/* Agent pipeline status — real execution data */}
      <div>
        <h2 className="text-text-secondary text-xs font-semibold uppercase tracking-wider mb-3">
          Agent Pipeline — {Object.keys(data.agentStatuses).length > 0 ? "Last Session" : "No active session"}
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {AGENTS.map((agent) => {
            const status = data.agentStatuses[agent.id];
            return (
              <GlassCard key={agent.id} padding="compact">
                <div className="flex items-center justify-between mb-1">
                  <div className={`text-xs font-semibold ${agent.color}`}>{agent.label}</div>
                  {status ? (
                    <AgentStatusBadge status={status as "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"} />
                  ) : null}
                </div>
                <div className="text-text-muted text-xs">
                  {status ? `Status: ${status}` : "No session active"}
                </div>
              </GlassCard>
            );
          })}
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Run Demo Replay", href: "/replay", color: "text-primary-400" },
          { label: "View Approvals", href: "/approvals", color: "text-yellow-400" },
          { label: "Agent Details", href: "/agents", color: "text-agent-intel" },
          { label: "Citizen Guidance", href: "/guidance", color: "text-agent-citizen" },
        ].map((link) => (
          <a
            key={link.href}
            href={link.href}
            className={`text-center px-3 py-2 rounded-md bg-bg-surface border border-white/[0.08] text-xs font-semibold ${link.color} hover:bg-white/5 transition-colors`}
          >
            {link.label}
          </a>
        ))}
      </div>
    </div>
  );
}
